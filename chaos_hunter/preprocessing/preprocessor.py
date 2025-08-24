import os
import subprocess
import yaml
from typing import List, Tuple, Optional

import streamlit as st

from .llm_agents.k8s_summary_agent import K8sSummaryAgent
from .llm_agents.k8s_weakness_summary_agent import K8sWeaknessSummaryAgent
from .llm_agents.k8s_app_assuption_agent import K8sAppAssumptionAgent, K8sAppAssumption
from .llm_agents.ce_instruct_agent import CEInstructAgent
from ..utils.functions import (
    write_file,
    save_json,
    recursive_to_dict,
    run_command
)
from ..utils.wrappers import LLM, BaseModel
from ..utils.streamlit import StreamlitDisplayHandler, Spinner
from ..utils.schemas import File
from ..utils.k8s import wait_for_resources_ready
from ..utils.llms import LLMLog


INPUT_TEMPLATE = """\
K8s manifest: {k8s_yaml_name}
```yaml
{k8s_yaml}
```
Summary of {k8s_yaml_name}:
{k8s_summary}"""


class ChaosHunterInput(BaseModel):
    skaffold_yaml: File
    files: List[File]
    ce_instructions: Optional[str]

class ProcessedData(BaseModel):
    work_dir: str
    input: ChaosHunterInput
    k8s_yamls: List[File]
    k8s_summaries: List[str]
    # k8s_dependencies: K8sDependencies
    k8s_weakness_summary: str
    k8s_app: K8sAppAssumption
    ce_instructions: str

    def to_k8s_overview_str(self) -> str:
        user_input = "The system consists of the following K8s manifest(s):"
        # add k8s yamls and their summaries
        for k8s_yaml, k8s_summary in zip(self.k8s_yamls, self.k8s_summaries):
            user_input += INPUT_TEMPLATE.format(
                k8s_yaml=k8s_yaml.content,
                k8s_yaml_name=k8s_yaml.fname,
                k8s_summary=k8s_summary
            )
            user_input += "\n\n"
        # add weakness
        user_input += f"The resiliency issues/weaknesses in the system are as follows:\n{self.k8s_weakness_summary}"
        # add dependencies
        # user_input += "The intra/inter dependencies of the above K8s manifests are as follows:" 
        # for intra_dependency in self.k8s_dependencies.intra:
        #     user_input += f"- Dependencies within {intra_dependency.file}:\n{intra_dependency.dependency}\n\n"
        # for inter_dependency in self.k8s_dependencies.inter:
        #     user_input += f"- Dependencies from {inter_dependency.src_file} to {inter_dependency.dst_file}:\n{inter_dependency.dependency}\n\n"
        # add application
        user_input += f"The expected type of application on the system (i.e., K8s manfests):\n{self.k8s_app.k8s_application}; {self.k8s_app.thought}"
        return user_input

    def to_str(self) -> str:
        overview_str = self.to_k8s_overview_str() + "\n\n"
        if self.ce_instructions != "" and self.ce_instructions is not None:
            overview_str += f"Chaos-Engineering instructions for the system are as follows: {self.ce_instructions}"
        else:
            overview_str += f"No Chaos-Engineering instructions for the system are provided."
        return overview_str


class PreProcessor:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.k8s_summary_agent          = K8sSummaryAgent(llm)
        self.k8s_weakness_summary_agent = K8sWeaknessSummaryAgent(llm)
        self.k8s_app_assumption_agent   = K8sAppAssumptionAgent(llm)
        self.ce_instruct_agent          = CEInstructAgent(llm)

    def process(
        self,
        input: ChaosHunterInput,
        kube_context: str,
        work_dir: str,
        project_name: str = "chaos-hunter",
        is_new_deployment: bool = True
    ) -> Tuple[List[LLMLog], ProcessedData]:
        preprocess_dir = f"{work_dir}/inputs"
        log = []
        #------------------------------------------------------
        # save the input manifests, then deploy them if needed
        #------------------------------------------------------
        # save the skaffold configuration file
        skaffold_path = f"{preprocess_dir}/{input.skaffold_yaml.fname}"
        os.makedirs(os.path.dirname(skaffold_path), exist_ok=True)
        skaffold_content = input.skaffold_yaml.content
        write_file(skaffold_path, skaffold_content)
        new_skaffold_yaml = File(
            path=skaffold_path,
            content=skaffold_content,
            work_dir=preprocess_dir,
            fname=input.skaffold_yaml.fname
        )
        # save other files
        skaffold_root_dir = os.path.dirname(input.skaffold_yaml.fname)
        skaffold_dict = yaml.safe_load(skaffold_content)
        if kustomize_paths := self.get_kustomize_paths(skaffold_dict):
            kustomize_paths = [f"{skaffold_root_dir}/{kustomize_path}" for kustomize_path in kustomize_paths]
            files, k8s_yamls = self.process_kustomize_paths(input, input.skaffold_yaml.work_dir, kustomize_paths, preprocess_dir)
        elif raw_yaml_paths := self.get_raw_yaml_paths(skaffold_dict):
            raw_yaml_paths = [f"{skaffold_root_dir}/{raw_yaml_path}" for raw_yaml_path in raw_yaml_paths]
            files, k8s_yamls = self.process_raw_yaml_paths(input, raw_yaml_paths, preprocess_dir)
        else:
            assert False, "No Kustomize or Raw YAML paths found in skaffold.yaml"
        duplicated_input = ChaosHunterInput(
            skaffold_yaml=new_skaffold_yaml,
            files=files,
            ce_instructions=input.ce_instructions
        )

        # deploy the resources using skaffold
        st.write("##### K8s manifest(s) to be deployed:")
        for k8s_yaml in k8s_yamls:
            st.write(f"```{k8s_yaml.fname}```")
            st.code(k8s_yaml.content)
        if is_new_deployment:
            spinner = Spinner(f"##### Deploying resources...")
            try:
                run_command(
                    cmd=f"skaffold run --kube-context {kube_context} -l project={project_name}",
                    cwd=os.path.dirname(new_skaffold_yaml.path),
                    display_handler=StreamlitDisplayHandler()
                )
            except subprocess.CalledProcessError as e:
                raise RuntimeError("K8s resource deployment failed.")
            spinner.end(f"##### Deploying resources... Done")

        # wait for all the resources to be deployed
        wait_for_resources_ready(label_selector=f"project={project_name}", context=kube_context)
        # display each resouce status
        st.write("##### Resource statuses")
        run_command(
            cmd=f"kubectl get all --all-namespaces --context {kube_context} --selector=project={project_name}",
            display_handler=StreamlitDisplayHandler()
        )

        #-----------------------------
        # summarize each k8s manifest
        #-----------------------------
        st.write("##### Summary of each manifest:")
        summary_log, k8s_summaries = self.k8s_summary_agent.summarize_manifests(k8s_yamls=k8s_yamls)
        log.append(summary_log)

        #-----------------------------------------
        # summarize weakness points in the system
        #-----------------------------------------
        st.write("##### Resiliency issuses/weaknesses in the manifests:")
        weakness_log, k8s_weakness_summary = self.k8s_weakness_summary_agent.summarize_weaknesses(k8s_yamls=k8s_yamls)
        log.append(weakness_log)

        #---------------------------
        # analyze file dependencies
        #---------------------------
        # pseudo_streaming_text("##### Dependencies between the manifests:")
        # depdency_token_usage, k8s_dependencies = self.k8s_analysis_agent.analyze_manifest_dependencies(
        #     k8s_yamls=k8s_yamls,
        #     k8s_summaries=k8s_summaries,
        #     kube_context=kube_context,
        #     project_name=project_name,
        #     work_dir=work_dir
        # )
        # log.append(depdency_token_usage)

        st.write("##### Application of the manifests:")
        #---------------------------------------------
        # assume the application of the k8s manifests
        #---------------------------------------------
        app_token_usage, k8s_application = self.k8s_app_assumption_agent.assume_app(
            k8s_yamls=k8s_yamls,
            k8s_summaries=k8s_summaries
        )
        log.append(app_token_usage)

        st.write("##### Summary of your instructions for Chaos Engineering:")
        #----------------------------------------------
        # summarize instructions for Chaos Engineering
        #----------------------------------------------
        if input.ce_instructions is not None and input.ce_instructions != "":
            instruct_token_usage, ce_instructions = self.ce_instruct_agent.summarize_ce_instructions(input.ce_instructions)
            log.append(instruct_token_usage)
        else:
            ce_instructions = ""
            st.write("No Chaos-Engineering instructions are provided.")

        #----------
        # epilogue
        #----------
        processed_data = ProcessedData(
            work_dir=preprocess_dir,
            input=duplicated_input,
            k8s_yamls=k8s_yamls,
            k8s_summaries=k8s_summaries,
            k8s_weakness_summary=k8s_weakness_summary,
            k8s_app=k8s_application,
            ce_instructions=ce_instructions
        )
        save_json(f"{preprocess_dir}/processed_data.json", processed_data.dict())
        save_json(f"{preprocess_dir}/preprcessing_log.json", recursive_to_dict(log))
        return log, processed_data
    
    def get_kustomize_paths(self, skaffold_config: dict) -> List[str]:
        manifests = skaffold_config.get("manifests", {})
        kustomize = manifests.get("kustomize", {})
        return kustomize.get("paths", [])
    
    def get_raw_yaml_paths(self, skaffold_config: dict) -> List[str]:
        manifests = skaffold_config.get("manifests", {})
        return manifests.get("rawYaml", [])
    
    def process_raw_yaml_paths(
        self,
        input: ChaosHunterInput,
        raw_yaml_paths: List[str],
        work_dir: str
    ) -> Tuple[List[File], List[File]]:
        files = []
        k8s_yamls = []
        # save files
        for file in input.files:
            path = f"{work_dir}/{file.fname}"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            new_file = File(
                path=path,
                content=file.content,
                work_dir=work_dir,
                fname=file.fname
            )
            write_file(path, file.content)
            files.append(new_file)
            # if the file is the K8s yamls specified in the skaffold configuration file
            if new_file.fname in raw_yaml_paths:
                k8s_yamls.append(new_file)
        # sort the yaml w.r.t their fnames
        k8s_yamls.sort(key=lambda x: x.fname or '')
        return files, k8s_yamls

    def process_kustomize_paths(
        self,
        input: ChaosHunterInput,
        skaffold_workdir: str,
        kustomize_paths: List[str],
        work_dir: str
    ) -> Tuple[List[File], List[File]]:
        files = []
        k8s_yamls = []
        kustomize_yaml_paths = self.get_kustomize_yaml_paths(skaffold_workdir, kustomize_paths)
        # save files
        for file in input.files:
            path = f"{work_dir}/{file.fname}"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            new_file = File(
                path=path,
                content=file.content,
                work_dir=work_dir,
                fname=file.fname
            )
            write_file(path, file.content)
            files.append(new_file)
            # if the file is the K8s yamls specified in the skaffold configuration file
            if new_file.fname in kustomize_yaml_paths:
                k8s_yamls.append(new_file)
        # sort the yaml w.r.t their fnames
        k8s_yamls.sort(key=lambda x: x.fname or '')
        return files, k8s_yamls

    def get_kustomize_yaml_paths(
        self, 
        skaffold_workdir: str,
        kustomization_paths: List[str]
    ) -> List[str]:
        kustomization_paths = [f"{skaffold_workdir}/{kustomization_path}" for kustomization_path in kustomization_paths]
        for kustomization_path in kustomization_paths:
            if not os.path.exists(kustomization_path):
                print(f"Skipping: {kustomization_path} (File not found)")
                continue
            # Get the list of resources
            with open(f"{kustomization_path}/kustomization.yaml", "r", encoding="utf-8") as f:
                kustomization = yaml.safe_load(f)
            resources = kustomization.get("resources", [])
            base_dir = kustomization_path
            kustomize_yaml_paths = []
            for resource in resources:
                resource_path = os.path.join(base_dir, resource)
                if os.path.exists(resource_path):
                    kustomize_yaml_paths.append(resource_path.removeprefix(f"{skaffold_workdir}/"))
                else:
                    print(f"Warning: {resource_path} not found")
        return kustomize_yaml_paths

    def split_and_save_yaml(
        self,
        yaml_content: str, 
        base_resources: List[str],
        base_path: str
    ) -> List[str]:
        documents = yaml.safe_load_all(yaml_content)
        output_dir = os.path.join(base_path, "rendered_output")
        os.makedirs(output_dir, exist_ok=True)

        for doc in documents:
            kind = doc["kind"]
            name = doc["metadata"]["name"]
            matching_base = next((base for base in base_resources if base.endswith(f"{kind.lower()}.yaml")), None)
            if matching_base:
                output_filename = os.path.join(output_dir, os.path.basename(matching_base))
            else:
                output_filename = os.path.join(output_dir, f"{kind.lower()}-{name}.yaml")
            with open(output_filename, "w") as f:
                yaml.dump(doc, f)
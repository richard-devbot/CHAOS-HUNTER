import os
import yaml
import json
import time
from typing import Dict, List, Tuple

import streamlit as st

from .llm_agents.experiment_plan_agent import ExperimentPlanAgent
from .llm_agents.experiment_replan_agent import ExperimentRePlanAgent
from .algorithms.plan2workflow_converter import Plan2WorkflowConverter
from ..preprocessing.preprocessor import ProcessedData
from ..hypothesis.hypothesizer import Hypothesis
from ..ce_tools.ce_tool_base import CEToolBase
from ..utils.functions import pseudo_streaming_text, type_cmd, save_json, recursive_to_dict, limit_string_length
from ..utils.schemas import File
from ..utils.wrappers import LLM, BaseModel
from ..utils.llms import LLMLog


CHAOS_EXPERIMENT_PLAN_TEMPALTE = """\
The entire time schedule of the Chaos-Engineering experiment is as follows (The experiment is divided into three phases: pre-validation, fault-injection, and post-validation phases):
{time_schedule_description}
- Total experiment phase: {total_time}
- Pre-validation phase: {pre_validation_time}
- Fault-injection phase: {fault_injection_time}
- Post-validation phase: {post_validation_time}

The details of the three phases are as follows:
Pre-validation Phase ({pre_validation_time}):
{pre_validation_description}

Fault-injection Phase ({fault_injection_time}):
{fault_injection_description}

Post-validation Phase ({post_validation_time}):
{post_validation_description}

The summary of the above experiment plan:
{summary}

To automatically conduct the above experiment plan with {ce_tool_name}, the following {ce_tool_workflow_file} was created (by applying it to the cluster, the experiment plan will be automatically executed according to the {ce_tool_workflow_file}):
```yaml
{workflow_file}
```"""


class ChaosExperiment(BaseModel):
    plan: dict
    workflow_name: str
    workflow: File

    def to_str(self):
        time_schedule = self.plan["time_schedule"]
        pre_validation = self.plan["pre_validation"]
        fault_injection = self.plan["fault_injection"]
        post_validation = self.plan["post_validation"]
        return CHAOS_EXPERIMENT_PLAN_TEMPALTE.format(
            total_time=time_schedule["total_time"],
            pre_validation_time=time_schedule["pre_validation_time"],
            fault_injection_time=time_schedule["fault_injection_time"],
            post_validation_time=time_schedule["post_validation_time"],
            time_schedule_description=time_schedule["thought"],
            pre_validation_description=pre_validation["thought"],
            fault_injection_description=fault_injection["thought"],
            post_validation_description=post_validation["thought"],
            ce_tool_name="Chaos Mesh",
            ce_tool_workflow_file="Chaos-Mesh-Worfklow file",
            workflow_file=self.workflow.content,
            summary=self.plan["summary"]
        )


class Status(BaseModel):
    exitcode: int
    logs: str

class ChaosExperimentResult(BaseModel):
    pod_statuses: Dict[str, Status]

    @property
    def all_tests_passed(self) -> bool:
        return sum([pod_status.exitcode for pod_status in self.pod_statuses.values()]) == 0

    def to_str(self) -> str:
        passed_tests = [workflow_name for workflow_name, pod_status in self.pod_statuses.items() if pod_status.exitcode == 0]
        failed_tests = [(workflow_name, pod_status.logs) for workflow_name, pod_status in self.pod_statuses.items() if pod_status.exitcode != 0]
        passed_tests_str = "\n".join([f"- {item}" for item in passed_tests]) 
        failed_tests_str = "\n".join([f"- {item[0]}\n```log\n{limit_string_length(item[1], max_length=1000)}\n```\n" for item in failed_tests])
        return f"Passed unittests:\n{passed_tests_str}\nFailed unittests:\n{failed_tests_str}"


class Experimenter:
    def __init__(
        self,
        llm: LLM,
        ce_tool: CEToolBase,
        test_dir: str = "sandbox/unit_test",
        chaos_dir: str = "sandbox/",
        namespace: str = "chaos-hunter",
    ) -> None:
        # llm
        self.llm = llm
        # CE tool
        self.ce_tool = ce_tool
        # params
        self.test_dir = test_dir
        self.chaos_dir = chaos_dir
        self.namespace = namespace
        self.experiment_plan = None
        self.workflow = None
        # agents
        self.experiment_plan_agent = ExperimentPlanAgent(llm, test_dir, namespace)
        self.experiment_replan_agent = ExperimentRePlanAgent(llm, test_dir, namespace)
        # algortihms
        self.plan2workflow_converter = Plan2WorkflowConverter()

    def plan_experiment(
        self,
        data: ProcessedData,
        hypothesis: Hypothesis,
        work_dir: str
    ) -> Tuple[List[LLMLog], ChaosExperiment]:
        logs = []
        # prepare a working directory
        experiment_dir = f"{work_dir}/experiment"
        os.makedirs(experiment_dir, exist_ok=True)

        #----------------------------------------------------------
        # 1. plan a CE experiment with the steady state and faults
        #----------------------------------------------------------
        plan_log, experiment_plan = self.experiment_plan_agent.plan(data=data, hypothesis=hypothesis)
        logs.append(plan_log)
        save_json(f"{experiment_dir}/experiment_plan.json", experiment_plan.dict())

        #-----------------------------------------------------------
        # 2. convert the plan into the format of a specific CE tool 
        #-----------------------------------------------------------
        workflow_name, workflow = self.plan2workflow_converter.convert(experiment_plan.dict(), experiment_dir)

        chaos_experiment = ChaosExperiment(
            plan=experiment_plan.dict(),
            workflow_name=workflow_name,
            workflow=workflow
        )
        save_json(f"{experiment_dir}/experiment.json", chaos_experiment.dict())
        save_json(f"{experiment_dir}/experiment_log.json", recursive_to_dict(logs))
        return logs, chaos_experiment

    def replan_experiment(
        self,
        prev_k8s_yamls: List[File],
        prev_experiment: ChaosExperiment,
        curr_k8s_yamls: List[File],
        kube_context: str,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[List[LLMLog], ChaosExperiment]:
        logs = []
        # prepare a working directory
        experiment_dir = f"{work_dir}/experiment"
        os.makedirs(experiment_dir, exist_ok=True)

        #----------------------------------------------------------
        # 1. replan a CE experiment with the steady state and faults
        #----------------------------------------------------------
        replan_log, experiment_replan = self.experiment_replan_agent.replan(
            prev_k8s_yamls,
            prev_experiment,
            curr_k8s_yamls,
            kube_context,
            work_dir=work_dir,
            max_retries=max_retries
        )
        logs.append(replan_log)

        #-----------------------------------------------------------
        # 2. convert the plan into the format of a specific CE tool 
        #-----------------------------------------------------------
        workflow_name, workflow = self.plan2workflow_converter.convert(
            experiment_replan.dict(),
            experiment_dir
        )

        chaos_experiment = ChaosExperiment(
            plan=experiment_replan.dict(),
            workflow_name=workflow_name,
            workflow=workflow
        )
        return logs, chaos_experiment

    def run(
        self,
        experiment: ChaosExperiment,
        kube_context: str,
        namespace: str = None,
        check_interval: int = 5 # sec
    ) -> ChaosExperimentResult:
        if namespace is None:
            namespace = self.namespace
        #-----------------------------------
        # run the valid chaos workflow
        #-----------------------------------
        execution_msg = st.empty()
        pseudo_streaming_text("##### Running the experiment... See http://localhost:2333 for more details.", obj=execution_msg)
        # self.ce_tool.run_experiment() # TODO
        # reset the experiment
        type_cmd(f"kubectl delete --context {kube_context} -n {namespace} -f {experiment.workflow.path} --ignore-not-found")
        type_cmd(f'kubectl delete workflownode --context {kube_context} -n {namespace} --selector="chaos-mesh.org/workflow={experiment.workflow_name}" --ignore-not-found')
        type_cmd(f'kubectl delete po --context {kube_context} -n {namespace} --selector="chaos-mesh.org/workflow={experiment.workflow_name}" --ignore-not-found')
        # run the experiment
        type_cmd(f"kubectl apply --context {kube_context} -n {namespace} -f {experiment.workflow.path}")
        st.components.v1.iframe("http://localhost:2333/#/workflows", height=500, scrolling=True)

        #--------------------------
        # wait for workflow to end
        #--------------------------
        workflow_running = True
        while(workflow_running):
            # is_running = self.ce_tool.status_check() # TODO
            # https://chaos-mesh.org/docs/check-workflow-status/
            entry_node_name = type_cmd(f'kubectl get workflownode --context {kube_context} -n {namespace} --selector="chaos-mesh.org/workflow={experiment.workflow_name}" -o custom-columns=:metadata.name | grep "^the-entry"', widget=False)
            entry_node_name = entry_node_name.strip()
            json_res = json.loads(type_cmd(f"kubectl get workflownode {entry_node_name} --context {kube_context} -n {namespace} -o json", widget=False))
            conditions = json_res["status"]["conditions"]
            status_accomplished = next((c["status"] for c in conditions if c["type"] == "Accomplished"), None)
            workflow_running = (status_accomplished == "False")
            time.sleep(check_interval)
        pseudo_streaming_text("##### Completed the chaos experiment!", obj=execution_msg)

        #-----------------------
        # organize the resullts
        #-----------------------
        yaml_dict = yaml.safe_load(experiment.workflow.content)
        prefixes = (
            "pre-unittest-",
            "fault-unittest-",
            "post-unittest-"
        )
        pod_prefixes= []
        for elm in yaml_dict["spec"]["templates"]:
            if elm["name"].startswith(prefixes):
                pod_prefixes.append(elm["name"])
        # get pod names
        pod_names = [
            type_cmd(f'kubectl get pod -o custom-columns=:metadata.name --context {kube_context} -n {namespace} --selector="chaos-mesh.org/workflow={experiment.workflow_name}" | grep "{pod_prefix + "-"}"').strip()
            for pod_prefix in pod_prefixes
        ]
        missed_idx =  [i for i, x in enumerate(pod_names) if x == ""]
        pod_names = list(filter(None, pod_names)) # If experiment exceeds deadline, we cannot find the pod
        assert len(pod_prefixes) == len(pod_names), f"WORKFLOW_DEADLINE_EXCEEDED: {len(pod_prefixes) - len(pod_names)} task(s) missed due to deadline exceeding.\nMissed task(s): {[pod_prefixes[idx] for idx in missed_idx]}"
        # get status
        pod_statuses = {}
        for pod_prefix, pod_name in zip(pod_prefixes, pod_names):
            pod_statuses[pod_prefix] = self.get_pod_status(
                pod_name=pod_name,
                kube_context=kube_context,
                namespace=namespace
            )
        return ChaosExperimentResult(
            pod_statuses=pod_statuses,
        )

    def get_pod_status(
        self,
        pod_name: str,
        kube_context: str,
        namespace: str
    ) -> Status:
        logs = type_cmd(f"kubectl logs {pod_name} --context {kube_context} -n {namespace}", widget=False)
        summary = type_cmd(f"kubectl get pod {pod_name} --context {kube_context} -n {namespace} -o json")
        # check container status
        pod_info = json.loads(summary)
        container_statuses = pod_info.get("status", {}).get("containerStatuses", [])
        assert len(container_statuses) > 0, f"Cannot find containerStatuses in the json summary: {container_statuses}."
        for container_status in container_statuses:
            state = container_status.get("state", {})
            terminated = state.get("terminated")
            if terminated:
                return Status(exitcode=int(terminated.get("exitCode")), logs=limit_string_length(logs))
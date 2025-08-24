import os
from chaos_hunter.preprocessing.preprocessor import PreProcessor, ChaosHunterInput
from chaos_hunter.utils.functions import is_binary
from chaos_hunter.utils.schemas import File
from chaos_hunter.utils.llms import load_llm


def test_kustomize_input() -> None:
    #---------------------------
    # prepare a kustomize input 
    #---------------------------
    EXAMPLE_DIR = "tests/data"
    example_dir = f"{EXAMPLE_DIR}/kustomize_example"
    instructions = "test"

    skaffold_yaml = None
    project_files_tmp = []
    for root, _, files in os.walk(example_dir):
        for entry in files:
            fpath = os.path.join(root, entry)
            if os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    file_content = f.read()
                if is_binary(file_content):
                    content = file_content
                else:
                    content = file_content.decode('utf-8')
                if os.path.basename(fpath) == "skaffold.yaml":
                    skaffold_yaml = File(
                        path=fpath,
                        content=content,
                        work_dir=EXAMPLE_DIR,
                        fname=fpath.removeprefix(f"{EXAMPLE_DIR}/")
                    )
                else:
                    project_files_tmp.append(File(
                            path=fpath,
                            content=content,
                            work_dir=EXAMPLE_DIR,
                            fname=fpath.removeprefix(f"{EXAMPLE_DIR}/")
                    ))
    input = ChaosHunterInput(
        skaffold_yaml=skaffold_yaml,
        files=project_files_tmp,
        ce_instructions=instructions
    )
    
    #---------------
    # preprocessing
    #---------------
    llm = load_llm(
        model_name="openai/gpt-4o-2024-08-06", 
        temperature=0.0,
        seed=42
    )
    preprocesser = PreProcessor(llm)
    preprocess_logs, data = preprocesser.process(
        input=input,
        kube_context="kind-chaos-hunter-cluster",
        work_dir="sandbox/kustomize_test",
        project_name="kustomize-test",
        is_new_deployment=True
    )
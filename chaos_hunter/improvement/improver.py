import os
from typing import List, Tuple

from .llm_agents.reconfiguration_agent import ReconfigurationAgent, ReconfigurationResult
from ..analysis.analyzer import Analysis
from ..ce_tools.ce_tool_base import CEToolBase
from ..experiment.experimenter import ChaosExperiment, ChaosExperimentResult
from ..hypothesis.hypothesizer import Hypothesis
from ..preprocessing.preprocessor import ProcessedData
from ..utils.wrappers import LLM
from ..utils.llms import LLMLog
from ..utils.functions import save_json, recursive_to_dict
from ..utils.schemas import File


class Improver:
    def __init__(
        self,
        llm: LLM,
        ce_tool: CEToolBase,
        work_dir: str = "sandbox"
    ) -> None:
        # llm
        self.llm = llm
        self.ce_tool = ce_tool
        self.work_dir = work_dir
        # modify k8s yaml
        self.agent = ReconfigurationAgent(llm)

    def reconfigure(
        self,
        input_data: ProcessedData,
        hypothesis: Hypothesis,
        experiment: ChaosExperiment,
        k8s_yamls_history: List[List[File]],
        mod_dir_history: List[str],
        result_history: List[ChaosExperimentResult],
        analysis_history: List[Analysis],
        reconfig_history: List[ReconfigurationResult],
        kube_context: str,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[List[LLMLog], ReconfigurationResult]:
        improvement_dir = f"{work_dir}/improvement"
        os.makedirs(improvement_dir, exist_ok=True)
        logs = []

        log, mod_k8s_yamls = self.agent.reconfigure(
            input_data=input_data,
            hypothesis=hypothesis,
            experiment=experiment,
            k8s_yamls_history=k8s_yamls_history,
            mod_dir_history=mod_dir_history,
            result_history=result_history,
            analysis_history=analysis_history,
            reconfig_history=reconfig_history,
            kube_context=kube_context,
            work_dir=improvement_dir,
            max_retries=max_retries
        )
        logs.append(log)

        mod_count = len(reconfig_history)
        reconfig_result = ReconfigurationResult(mod_k8s_yamls=mod_k8s_yamls)
        save_json(f"{improvement_dir}/improvment{mod_count}.json", reconfig_result.dict())
        save_json(f"{improvement_dir}/improvment_log{mod_count}.json", recursive_to_dict(logs))
        return logs, reconfig_result
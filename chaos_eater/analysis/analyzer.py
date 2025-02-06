import os
from typing import List, Tuple

from .llm_agents.analysis_agent import AnalysisAgent
from ..preprocessing.preprocessor import ProcessedData
from ..hypothesis.hypothesizer import Hypothesis
from ..experiment.experimenter import ChaosExperiment, ChaosExperimentResult
from ..utils.wrappers import BaseModel, LLM
from ..utils.llms import LLMLog
from ..utils.functions import save_json, recursive_to_dict


class Analysis(BaseModel):
    report: str 


class Analyzer:
    def __init__(
        self,
        llm: LLM,
        namespace: str = "chaos-eater"
    ) -> None:
        # llm
        self.llm = llm
        # general
        self.namespace = namespace
        # analysis
        self.analysis_agent = AnalysisAgent(llm)

    def analyze(
        self,
        mod_count: int,
        input_data: ProcessedData,
        hypothesis: Hypothesis,
        experiment: ChaosExperiment,
        reconfig_history,
        experiment_result: ChaosExperimentResult,
        work_dir
    ) -> Tuple[List[LLMLog], Analysis]:
        analysis_dir = f"{work_dir}/analysis"
        os.makedirs(analysis_dir, exist_ok=True)
        logs = []

        report_log, report = self.analysis_agent.analyze(
            input_data=input_data,
            hypothesis=hypothesis,
            experiment=experiment,
            reconfig_history=reconfig_history,
            experiment_result=experiment_result
        )
        logs.append(report_log)

        analysis = Analysis(report=report)
        save_json(f"{analysis_dir}/analysis{mod_count}.json", analysis.dict())
        save_json(f"{analysis_dir}/analysis{mod_count}_log.json", recursive_to_dict(logs))
        return logs, Analysis(report=report)
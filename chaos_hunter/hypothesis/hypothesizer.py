import os
from typing import List, Tuple

from .steady_states.steady_state_definer import SteadyStateDefiner, SteadyStates
from .faults.fault_definer import FaultDefiner, FaultScenario
from ..utils.wrappers import LLM, BaseModel
from ..utils.functions import save_json, recursive_to_dict
from ..utils.llms import LLMLog
from ..ce_tools.ce_tool_base import CEToolBase
from ..preprocessing.preprocessor import ProcessedData


HYPOTHESIS_OVERVIEW_TEMPLATE = """\
The hypothesis is "The steady states of the sytem are maintained even when the fault scenario occurs (i.e., when the faults are injected)".
The steady states here are as follows:
{steady_state_overview}

The fault scenario here is as follows:
{fault_scenario_overview}"""


class Hypothesis(BaseModel):
    steady_states: SteadyStates
    fault: FaultScenario

    def to_str(self) -> str:
        return HYPOTHESIS_OVERVIEW_TEMPLATE.format(
            steady_state_overview=self.steady_states.to_str(),
            fault_scenario_overview=self.fault.to_str()
        )


class Hypothesizer:
    def __init__(
        self,
        llm: LLM,
        ce_tool: CEToolBase,
        test_dir: str = "sandbox/unit_test",
        namespace: str = "chaos-hunter",
        max_mod_loop: int = 3
    ) -> None:
        self.llm = llm
        self.ce_tool = ce_tool
        # params
        self.test_dir = test_dir
        self.namespace = namespace
        self.max_mod_loop = max_mod_loop
        # agents
        self.steady_state_definer = SteadyStateDefiner(llm, test_dir, namespace, max_mod_loop)
        self.fault_definer = FaultDefiner(llm, ce_tool, test_dir, namespace)

    def hypothesize(
        self,
        data: ProcessedData,
        kube_context: str,
        work_dir: str,
        max_num_steady_states: int = 2,
        max_retries: int = 3
    ) -> Tuple[List[LLMLog], Hypothesis]:
        #----------------
        # initialization
        #----------------
        hypothesis_dir = f"{work_dir}/hypothesis"
        os.makedirs(hypothesis_dir, exist_ok=True)
        logs = []

        #-------------------------
        # 1. define steady states
        #-------------------------
        steady_state_logs, steady_states = self.steady_state_definer.define_steady_states(
            input_data=data, 
            kube_context=kube_context,
            work_dir=hypothesis_dir,
            max_num_steady_states=max_num_steady_states,
            max_retries=max_retries
        )
        logs += steady_state_logs
        save_json(f"{hypothesis_dir}/steady_states.json", steady_states.dict())
        save_json(f"{hypothesis_dir}/steady_states.json", recursive_to_dict(steady_state_logs))

        #------------------
        # 2. define faults
        #------------------
        fault_logs, fault = self.fault_definer.define_faults(
            data=data,
            steady_states=steady_states,
            work_dir=hypothesis_dir,
            max_retries=max_retries
        )
        logs += fault_logs
        save_json(f"{hypothesis_dir}/faults.json", fault.dict())
        save_json(f"{hypothesis_dir}/faults_log.json", recursive_to_dict(fault_logs))

        #-------------------
        # make a hypothesis
        #-------------------
        hypothesis = Hypothesis(steady_states=steady_states, fault=fault)
        save_json(f"{hypothesis_dir}/hypothesis.json", hypothesis.dict())
        save_json(f"{hypothesis_dir}/hypothesis_log.json", recursive_to_dict(logs))
        return logs, hypothesis
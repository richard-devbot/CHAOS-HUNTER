import os
from typing import List, Dict, Tuple

import streamlit as st

from .llm_agents.fault_scenario_agent import FaultScenarioAgent
from .llm_agents.fault_refinement_agent import FaultRefiner, FaultScenario
from ..steady_states.steady_state_definer import SteadyStates
from ...ce_tools.ce_tool_base import CEToolBase
from ...preprocessing.preprocessor import ProcessedData
from ...utils.llms import LLM, LLMLog


class FaultDefiner:
    def __init__(
        self,
        llm: LLM,
        ce_tool: CEToolBase,
        test_dir: str = "sandbox/unit_test",
        namespace: str = "chaos-hunter"
    ) -> None:
        self.llm = llm
        self.ce_tool = ce_tool
        self.test_dir = test_dir
        self.namespace = namespace
        # agents
        self.fault_scenario_agent = FaultScenarioAgent(llm, ce_tool)
        self.refiner = FaultRefiner(llm, ce_tool)

    def convert_steady_state_to_str(self, steady_states: List[Dict[str, str]]) -> str:
        steady_state_str = ""
        for i, steady_state in enumerate(steady_states):
            steady_state_str += f"Steady state #{i}: {steady_state.name}\nDescription: {steady_state.description}\nThreshold: {steady_state.threshold['threshold']}; {steady_state.threshold['reason']}"
        return steady_state_str

    def define_faults(
        self,
        data: ProcessedData,
        steady_states: SteadyStates,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[LLMLog, FaultScenario]:
        #-------------------
        # 0. initialization
        #-------------------
        st.write("##### Fault definition")
        st.session_state.fault_container = []
        fault_dir = f"{work_dir}/faults"
        os.makedirs(fault_dir, exist_ok=True)
        logs = []

        #----------------------------
        # 1. assume a fault scenario
        #----------------------------
        scenario_log, fault_scenario = self.fault_scenario_agent.assume_scenario(
            user_input=data.to_k8s_overview_str(),
            ce_instructions=data.ce_instructions,
            steady_states=steady_states
        )
        logs.append(scenario_log)

        #---------------------------------------------
        # refine the faults: determine the parameters
        #---------------------------------------------
        fault_log, faults = self.refiner.refine_faults(
            user_input=data.to_k8s_overview_str(),
            ce_instructions=data.ce_instructions,
            steady_states=steady_states,
            fault_scenario=fault_scenario,
            work_dir=fault_dir,
            max_retries=max_retries
        )
        logs.append(fault_log)
        return logs, faults
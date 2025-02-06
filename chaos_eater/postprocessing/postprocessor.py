import os
from typing import List, Tuple

import streamlit as st

from .llm_agents.summary_agent import SummaryAgent, ChaosCycle
from ..utils.wrappers import LLM
from ..utils.llms import LLMLog
from ..utils.functions import save_json, recursive_to_dict


class PostProcessor:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.summary_agent = SummaryAgent(llm)

    def process(
        self,
        ce_cycle: ChaosCycle,
        work_dir: str
    ) -> Tuple[List[LLMLog], str]:
        logs = []

        with st.expander("##### Summary of your k8s yaml", expanded=True):
            summary_log, summary = self.summary_agent.summarize(ce_cycle)
        logs.append(summary_log)

        os.makedirs(work_dir, exist_ok=True)
        with open(f"{work_dir}/summary.dat", "w") as f:
            f.write(summary)
        save_json(f"{work_dir}/summary_log.json", recursive_to_dict(logs))
        return logs, summary
    
    def generate_intermediate_summary(self):
        pass
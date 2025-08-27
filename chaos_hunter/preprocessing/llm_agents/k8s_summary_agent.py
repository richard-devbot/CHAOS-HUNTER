from typing import List, Tuple

import streamlit as st

from ...utils.wrappers import LLM, BaseModel, Field
from ...utils.llms import build_json_agent, LoggingCallback, LLMLog
from ...utils.schemas import File
from ...utils.functions import file_to_str


#---------
# prompts
#---------
SYS_SUMMARIZE_K8S = """\
You are a professional kubernetes (K8s) engineer.
Given a K8s manifest, please summarize it according to the following rules:
- Summary must be written in bullet points.
- Summarize the functions of the K8s manifest in a way that is understandable to even beginners.
- {format_instructions}"""

USER_SUMMARIZE_K8S = """\
# K8s manifest
{k8s_yaml}

Please summarize the above K8s manifest."""


#--------------------
# JSON output format
#--------------------
class K8sSummary(BaseModel):
    k8s_summary: str = Field(description="Summary of the K8s manifest. Summarize it in bullet points like '- the 1st line\n- the second line...'")


#------------------
# agent definition
#------------------
class K8sSummaryAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_SUMMARIZE_K8S), ("human", USER_SUMMARIZE_K8S)],
            pydantic_object=K8sSummary,
            is_async=False
        )

    def summarize_manifests(self, k8s_yamls: List[File]) -> Tuple[LLMLog, List[str]]:
        self.logger = LoggingCallback(name="k8s_summary", llm=self.llm)
        summaries = []
        for k8s_yaml in k8s_yamls:
            st.write(f"```{k8s_yaml.fname}```")
            container = st.empty()
            summary_str = ""  # Initialize summary_str variable
            for summary in self.agent.stream(
                {"k8s_yaml": file_to_str(k8s_yaml)}, 
                {"callbacks": [self.logger]}
            ):
                if (summary_str := summary.get("k8s_summary")) is not None:
                    pass
                    # container.write(summary_str)
            summaries.append(summary_str)
            container.write(summary_str)
        return self.logger.log, summaries
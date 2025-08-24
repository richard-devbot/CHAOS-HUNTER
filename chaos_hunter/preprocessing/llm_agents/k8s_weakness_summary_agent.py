from typing import List, Tuple

import streamlit as st

from ...utils.wrappers import LLM, BaseModel, Field
from ...utils.llms import build_json_agent, LoggingCallback, LLMLog
from ...utils.schemas import File


#---------
# prompts
#---------
SYS_SUMMARIZE_K8S_WEAKNESSES = """\
You are a professional Kubernetes (K8s) engineer.
Given K8s manifests for a system, you will identify their potential issues related to resiliency and redundancy that may arise during system failures.
Always adhere to the following rules:
- For each issue, provide a name for the issue, the associated K8s manifest(s), description of the potential issues caused by fault injection, and the configuration leading to the issue (no need to suggest improvements).
- If the same issue is present in multiple manifests, merge it into a single issue, specifying all relevant manifest names.
- {format_instructions}"""

USER_SUMMARIZE_K8S_WEAKNESSES = """\
# Here is the K8s manifests for my system.
{k8s_yamls}

Please list issues for each K8s manifest."""


#--------------------
# JSON output format
#--------------------
class K8sIssue(BaseModel):
    issue_name: str = Field(description="Issue name")
    issue_details: str = Field(description="potential issues due to fault injection")
    manifests: List[str] = Field(description="manifest names having the issues")
    problematic_config: str = Field(description="problematic configuration causing the issues (no need to suggest improvements).")

class K8sIssues(BaseModel):
    issues: List[K8sIssue] = Field(description="List issues with its name, potential issues due to fault injection, and manifest configuration causing the issues (no need to suggest improvements).")


#------------------
# agent definition
#------------------
class K8sWeaknessSummaryAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_SUMMARIZE_K8S_WEAKNESSES), ("human", USER_SUMMARIZE_K8S_WEAKNESSES)],
            pydantic_object=K8sIssues,
            is_async=False
        )

    def summarize_weaknesses(self, k8s_yamls: List[File]) -> Tuple[LLMLog, str]:
        self.logger = LoggingCallback(name="k8s_summary", llm=self.llm)
        container = st.empty()
        for output in self.agent.stream(
            {"k8s_yamls": self.get_k8s_yamls_str(k8s_yamls)},
            {"callbacks": [self.logger]}
        ):
            if (issues := output.get("issues")) is not None:
                text = ""
                for i, issue in enumerate(issues):
                    if (name := issue.get("issue_name")) is not None:
                        text += f"Issue #{i}: {name}\n"
                    if (details := issue.get("issue_details")) is not None:
                        text += f"  - details: {details}\n"
                    if (manifests := issue.get("manifests")) is not None:
                        text += f"  - manifests having the issues: {manifests}\n"
                    if (config := issue.get("problematic_config")) is not None:
                        text += f"  - problematic config: {config}\n\n"
                    container.write(text)
            container.write(text)
        return self.logger.log, text
    
    def get_k8s_yamls_str(self, k8s_yamls: List[File]) -> str:
        input_str = ""
        for k8s_yaml in k8s_yamls:
            input_str += f"```{k8s_yaml.fname}```\n```yaml\n{k8s_yaml.content}\n```\n\n"
        return input_str
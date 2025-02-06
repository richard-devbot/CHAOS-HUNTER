from typing import Dict, Tuple
import streamlit as st
from ....preprocessing.preprocessor import ProcessedData
from ....utils.wrappers import LLM, BaseModel, Field
from ....utils.llms import build_json_agent, LoggingCallback, LLMLog


#---------
# prompts
#---------
SYS_CHECK_STEADY_STATE_COMPLETION = """\
You are a helpful AI assistant for Chaos Engineering.
Given K8s manifests for a system, user's instructions, and steady states already defined, you will determine whether an additional steady state needs to be defined.
Always keep the following rules:
- Clearly describe the reason for determining whether an additional steady state is needed.
- You may also cite the user's instructions as the reason.
- {format_instructions}"""

USER_CHECK_STEADY_STATE_COMPLETION = """\
# Here is the overview of my system:
{user_input}

# Please follow the instructions below regarding Chaos Engineering:
{ce_instructions}

# Steady states already defined are as follows:
{predefined_steady_states}

Now, determine whether an additional steady state needs to be defined."""

#--------------------
# json output format
#--------------------
class SteadyStateCompletionCheck(BaseModel):
    thought: str = Field(description="Describe your thought process of determing whether an additional steady states is needed.")
    requires_addition: bool = Field(description="The necessity of an additional steady state. If it is needed, select 'True'; otherwise select 'False'.")

#------------------
# agent definition
#------------------
class SteadyStateCompletionCheckAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_CHECK_STEADY_STATE_COMPLETION), ("human", USER_CHECK_STEADY_STATE_COMPLETION)],
            pydantic_object=SteadyStateCompletionCheck,
            is_async=False
        )

    def check_steady_state_completion(
        self,
        input_data: ProcessedData,
        predefined_steady_states: list,
    ) -> Tuple[LLMLog, Dict[str, str]]:
        logger = LoggingCallback(name="steady_state_completion_check", llm=self.llm)
        
        with st.container(border=True):
            st.write("##### Steady state completion check")
            thought_empty = st.empty()
            check_empty = st.empty()

        for completion_check in self.agent.stream({
            "user_input": input_data.to_k8s_overview_str(), 
            "ce_instructions": input_data.ce_instructions,
            "predefined_steady_states": predefined_steady_states.to_str()},
            {"callbacks": [logger]}
        ):
            if (thought := completion_check["thought"]) is not None:
                thought_empty.write(thought)
            if (check := completion_check["requires_addition"]) is not None:
                check_empty.write(f"An additional steady state is needed?: ```{check}```")
        return logger.log, completion_check
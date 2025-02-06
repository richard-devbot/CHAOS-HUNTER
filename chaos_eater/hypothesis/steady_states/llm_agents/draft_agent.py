from typing import Dict, Tuple

from ....preprocessing.preprocessor import ProcessedData
from ....utils.wrappers import LLM, BaseModel, Field
from ....utils.llms import build_json_agent, LoggingCallback, LLMLog
from ....utils.streamlit import StreamlitContainer


#---------
# prompts
#---------
SYS_DRAFT_STEADY_STATE = """\
You are a helpful AI assistant for Chaos Engineering.
Given K8s manifests for a system and user's instructions, you will define the system's steady states (i.e., normal behaviors) that are related to potential issues of the system.
Always keep the following rules:
- Define steady states one by one, starting with the steady state related to the K8s resource that is easiest to encounter issues when certain failures occur.
- Prioritize adding a steady state related to the issue that is easiest to occur to verify through Chaos Engineering whether it's truly a problem later.
- An added steady state must be a measurable output, such as the number of pods, throughput, error rates, latency percentiles, etc.
- An added steady state must be specific to a SINGLE K8s resource (i.e., manifest) having potential issues for resilency and redundancy.
- An added steady state must be different from the already defined ones.
- {format_instructions}"""

USER_DRAFT_STEADY_STATE = """\
# Here is the overview of my system:
{user_input}

# Please follow the instructions below regarding Chaos Engineering:
{ce_instructions}

# Steady states already defined are as follows:
{predefined_steady_states}

# The plan for defining the next state is as follows:
{prev_check_thought}

Now, define a steady state that are different from the already defined steady states."""

#--------------------
# json output format
#--------------------
class SteadyStateDraft(BaseModel):
    thought: str = Field(description="Describe your thought process of determing the steady state of a SINGLE K8s resource (i.e., manifest) that is easiest to encounter the issues. Describe also the details of the steady state itself.")
    manifest: str = Field(description="The targeted K8s-manifest name. Specify a SINGLE manifest.")
    name: str = Field(description="Steady state name including the target K8s resource (manifest) name. Please write it using a-z, A-Z, and 0-9.")


#------------------
# agent definition
#------------------
class SteadyStateDraftAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm
        self.agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_DRAFT_STEADY_STATE), ("human", USER_DRAFT_STEADY_STATE)],
            pydantic_object=SteadyStateDraft,
            is_async=False
        )

    def draft_steady_state(
        self,
        input_data: ProcessedData,
        predefined_steady_states: list,
        prev_check_thought: str,
        display_container: StreamlitContainer
    ) -> Tuple[LLMLog, Dict[str, str]]:
        logger = LoggingCallback(name="steady_state_draft", llm=self.llm)
        container_id = "description"
        display_container.create_subcontainer(id=container_id, header=f"##### 💬 Description")
        display_container.create_subsubcontainer(subcontainer_id=container_id, subsubcontainer_id=container_id)
        prev_check_thought = prev_check_thought if prev_check_thought != "" else "No steady states have been defined, so a new steady state needs to be defined."
        for steady_state in self.agent.stream({
            "user_input": input_data.to_k8s_overview_str(), 
            "ce_instructions": input_data.ce_instructions,
            "predefined_steady_states": predefined_steady_states.to_str(),
            "prev_check_thought": prev_check_thought},
            {"callbacks": [logger]}
        ):
            if (thought := steady_state["thought"]) is not None:
                display_container.update_subsubcontainer(thought, container_id)
            if (name := steady_state["name"]) is not None:
                display_container.update_header(f"##### Steady state #{predefined_steady_states.count+1}: {name}", expanded=True)
        return logger.log, steady_state
from collections import Counter
from typing import List, Dict, Any, Tuple, Literal

import streamlit as st

from ...preprocessing.preprocessor import ProcessedData
from ...hypothesis.hypothesizer import Hypothesis
from ...ce_tools.ce_tool_base import CEToolBase
from ...utils.wrappers import LLM, LLMBaseModel, LLMField, BaseModel
from ...utils.llms import build_json_agent, LLMLog, LoggingCallback
from ...utils.functions import pseudo_streaming_text, parse_time, add_timeunit, sanitize_k8s_name


SYS_DETERMINE_TIME_SCHEDULE = """\
You are a helpful AI assistant for Chaos Engineering.
Given k8s manifests that defines a network system, its steady states, and faults that may affect the steady states in the system, you will design a Chaos Engineering experiment for them.
First, you will determine the time schedule for the Chaos Engineering experiment.
Always keep the following rules:
- IMPORTANT: All resources for this application are deployed in the 'chaos-hunter' namespace. Assume interactions and references use the 'chaos-hunter' namespace unless explicitly instructed otherwise.
- The experiment is divided into three phases: pre-validation, fault-injection, and post-validation phases: pre-validation to ensure that the system satisfy the steady states fault injection; fault-injection to observe the system's behavior during fault injection; post-validation to ensure that the system has returned to its steady states after fault injection.
- {format_instructions}"""

USER_DETERMINE_TIME_SCHEDULE = """\
# Here is the overview of my system:
{user_input}

# Steady states of my system:
{steady_states}

# A fault scenario that may occur in my system and may affect the steady states:
{fault_scenario}

# Please follow the instructions below regarding Chaos Engineering as necessary:
{ce_instructions}

Now, please plan a Chaos Engineering experiment to check the network system's resiliency that the steady states are remained during fault injection."""

SYS_DETERMINE_PHASE = """\
You are a helpful AI assistant for Chaos Engineering.
Given k8s manifests that defines a network system, its steady states, and faults that may affect the steady states in the system, you will design a Chaos Engineering experiment for them.
The experiment is divided into three phases: pre-validation, fault-injection, and post-validation phases: pre-validation to ensure that the system satisfy the steady states fault injection; fault-injection to observe the system's behavior during fault injection; post-validation to ensure that the system has returned to its steady states after fault injection.
Here, you will detail the {phase_name}.
Always keep the following rules:
- IMPORTANT: All resources for this application are deployed in the 'chaos-hunter' namespace. Assume interactions and references use the 'chaos-hunter' namespace unless explicitly instructed otherwise.
- {format_instructions}"""

USER_DETERMINE_PHASE = """\
# Here is the overview of my system:
{user_input}

# Steady states of my system:
{steady_states}

# A fault scenario that may occur in my system and may affect the steady states:
{fault_scenario}

# Please follow the instructions below regarding Chaos Engineering as necessary:
{ce_instructions}

Now, please detail the {phase_name}. Note that the phase's total time is {phase_total_time}."""

SYS_SUMMARIZE_PLAN = """\
You are a helpful AI assistant for Chaos Engineering.
Given a Chaos-Engineering-experiment plan, you will summarize it in detail according to the following rules:
- IMPORTANT: All resources for this application are deployed in the 'chaos-hunter' namespace. Assume interactions and references use the 'chaos-hunter' namespace unless explicitly instructed otherwise.
- In each phase, describe in detail the timeline for when each fault injection/unit test (for verifying steady-state) will be executed. For example, summarize which fault injections/unit tests will be executed simultaneously, and whether certain fault injections/unit tests will be executed at staggered timings. 
- Be sure to specify both each fault injection/unit test and their corresponding workflow names.
- When explaining the timeline, provide a detailed description using specific values for duration, grace period, etc. Rephrase the specific values in a way that everyone can easily understand.
- The meanings of each value are as follows:
  - Grace Period: Time elapsed from the start of the current phase to the beginning of the fault injection/unit test.
  - Duration: Duration of the fault injection/unit test. (grace_period + duration) should not exceed the corresponding phase's total time.
- Never output bullet points.
- {format_instructions}
"""

USER_SUMMARIZE_PLAN = """\
# Here is my Chaos-Engineering-experiment plan:
## Time Schedule
{time_schedule_overview}

## Pre-validation Phase
{pre_validation_overview}

## Fault-injection Phase 
{fault_injection_overview}

## Post-validation phase
{post_validation_overview}

Please summarize the above plan.
"""

DEADLINE_MARGIN = 300 # sec

class TimeSchedule(LLMBaseModel):
    thought: str = LLMField(describe="Think about the total time and the reasonable time allocation for each phase that you are about to design, and explain your thought process in detail.")
    total_time: str = LLMField(example="10m", description="Total time of the entire chaos experiment. total_time should equal to the sum of pre_validation_time, fault_injection_time, and post_validation_time.")
    pre_validation_time: str  = LLMField(example="2m", description="Total time of validation before fault injection.")
    fault_injection_time: str = LLMField(example="6m", description="Total time of fault injection.")
    post_validation_time: str = LLMField(example="2m", description="Total time of validation after fault injection.")

class UnitTest(LLMBaseModel):
    name: str = LLMField(description="Steady state name to be verified by a unit test.")
    grace_period: str = LLMField(example="0s", description="Time elapsed from the start of the current phase to the beginning of the unit test.")
    duration: str   = LLMField(example="2m", description="Duration of the unit test. (grace_period + duration) should not exceed the current phase's total time.")

class FaultInjection(LLMBaseModel):
    name: Literal["PodChaos", "NetworkChaos", "DNSChaos", "HTTPChaos", "StressChaos", "IOChaos", "TimeChaos"] = LLMField(description='Select a fault type from ["PodChaos", "NetworkChaos", "DNSChaos", "HTTPChaos", "StressChaos", "IOChaos", "TimeChaos"]')
    name_id: int = LLMField(description="An identifier to prevent name conflicts when the same Fault appears. Assign numbers starting from 0 in sequential order to prevent name conflicts.")
    grace_period: str = LLMField(example="0s", description="Time elapsed from the start of the current phase to the beginning of the fault injection.")
    duration: str   = LLMField(example="2m", description="Duration of the unit test. (grace_period + duration) should not exceed the current phase's total time.")

class FaultInjectionPlan(LLMBaseModel):
    thought: str = LLMField(description="Describe in detail the timeline for when each fault injection and each unit test (for verifying steady-state) will be executed. For example, explain which fault injections/unit tests will be executed simultaneously, and whether certain fault injections/unit tests will be executed at staggered timings. Additionally, explain the thought process that led you to this approach.")
    fault_injection: List[FaultInjection] = LLMField(description="The list of fault injection schedules.")
    unit_tests: List[UnitTest] = LLMField(description="The list of unit test schedule.")

class ValidationPlan(LLMBaseModel):
    thought: str = LLMField(description="Describe in detail the timeline for when each fault injection and each unit test (for verifying steady-state) will be executed. For example, explain which fault injections/unit tests will be executed simultaneously, and whether certain fault injections/unit tests will be executed at staggered timings. Additionally, explain the thought process that led you to this approach.")
    unit_tests: List[UnitTest] = LLMField(description="The list of unit test schedule.")

class Summary(LLMBaseModel):
    summary: str = LLMField(description="The summary of the given Chaos-Engineering-experiment plan.")

class ChaosExperimentPlan(BaseModel):
    time_schedule: dict # TimeSchedule
    pre_validation: dict # ValidationPlan
    fault_injection: dict # FaultInjectionPlan
    post_validation: dict # ValidationPlan
    summary: str


class ExperimentPlanAgent:
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
        self.time_schedule_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_DETERMINE_TIME_SCHEDULE), ("human", USER_DETERMINE_TIME_SCHEDULE)],
            pydantic_object=TimeSchedule,
            is_async=False,
        )
        self.pre_validation_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_DETERMINE_PHASE), ("human", USER_DETERMINE_PHASE)],
            pydantic_object=ValidationPlan,
            is_async=False,
        )
        self.fault_injection_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_DETERMINE_PHASE), ("human", USER_DETERMINE_PHASE)],
            pydantic_object=FaultInjectionPlan,
            is_async=False,
        )
        self.post_validation_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_DETERMINE_PHASE), ("human", USER_DETERMINE_PHASE)],
            pydantic_object=ValidationPlan,
            is_async=False,
        )
        self.summary_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_SUMMARIZE_PLAN), ("human", USER_SUMMARIZE_PLAN)],
            pydantic_object=Summary,
            is_async=False,
        )

    def plan(
        self,
        data: ProcessedData,
        hypothesis: Hypothesis
    ) -> Tuple[LLMLog, dict]:
        #-------------------
        # initialization
        #-------------------
        plan_msg = st.empty()
        st.session_state.plan_container = self.get_plan_items()
        pseudo_streaming_text("##### Planning a CE experiment...", obj=plan_msg)
        logger = LoggingCallback(name="experiment_plan", llm=self.llm)

        #----------------------
        # plan a time schedule
        #----------------------
        for time_schedule in self.time_schedule_agent.stream({
            "user_input": data.to_k8s_overview_str(),
            "ce_instructions": data.ce_instructions,
            "steady_states": hypothesis.steady_states.to_overview_str(),
            "fault_scenario": hypothesis.fault.to_overview_str()},
            {"callbacks": [logger]}
        ):
            if (time_schedule_thought := time_schedule.get("thought")) is not None:
                st.session_state.plan_container["time_schedule_thought"].write(time_schedule_thought)
            if (total_time := time_schedule.get("total_time")) is not None:
                st.session_state.plan_container["total_time"].write(f"Total experiment time: ```{total_time}```")
            if (pre_validation_time := time_schedule.get("pre_validation_time")) is not None:
                st.session_state.plan_container["pre_validation_time"].write(f"Pre-validation Phase: ```{pre_validation_time}```")
                st.session_state.plan_container["pre_validation_header"].write(f"###### :blue-background[Pre-validation Phase ({pre_validation_time})]")
            if (fault_injection_time := time_schedule.get("fault_injection_time")) is not None:
                st.session_state.plan_container["fault_injection_time"].write(f"Fault-injection Phase: ```{fault_injection_time}```")
                st.session_state.plan_container["fault_injection_header"].write(f"###### :red-background[Fault-injection Phase ({fault_injection_time})]")
            if (post_validation_time := time_schedule.get("post_validation_time")) is not None:
                st.session_state.plan_container["post_validation_time"].write(f"Post-validation Phase: ```{post_validation_time}```")
                st.session_state.plan_container["post_validation_header"].write(f"###### :green-background[Post-validation Phase ({post_validation_time})]")

        #---------------------------------------------------------------------------
        # plan pre-validation, fault-injection, post-validation phases sequentially
        #---------------------------------------------------------------------------
        for pre_validation_plan in self.pre_validation_agent.stream({
            "user_input": data.to_k8s_overview_str(),
            "ce_instructions": data.ce_instructions,
            "steady_states": hypothesis.steady_states.to_overview_str(),
            "fault_scenario": hypothesis.fault.to_overview_str(),
            "phase_name": "pre-validation phase",
            "phase_total_time": pre_validation_time},
            {"callbacks": [logger]}
        ):
            self.display_phase_overview(pre_validation_plan, "pre_validation")

        for fault_injection_plan in self.fault_injection_agent.stream({
            "user_input": data.to_k8s_overview_str(),
            "ce_instructions": data.ce_instructions,
            "steady_states": hypothesis.steady_states.to_overview_str(),
            "fault_scenario": hypothesis.fault.to_overview_str(),
            "phase_name": "fault-injection phase",
            "phase_total_time": fault_injection_time},
            {"callbacks": [logger]}
        ):
            self.display_phase_overview(fault_injection_plan, "fault_injection")
        
        for post_validation_plan in self.post_validation_agent.stream({
            "user_input": data.to_k8s_overview_str(),
            "ce_instructions": data.ce_instructions,
            "steady_states": hypothesis.steady_states.to_overview_str(),
            "fault_scenario": hypothesis.fault.to_overview_str(),
            "phase_name": "post-validation phase",
            "phase_total_time": post_validation_time},
            {"callbacks": [logger]}    
        ):
            self.display_phase_overview(post_validation_plan, "post_validation")

        #-------------------
        # add workflow name
        #-------------------
        self.add_workflowname_and_deadline(pre_validation_plan, "pre_validation", "unittest")
        self.add_workflowname_and_deadline(fault_injection_plan, "fault_injection", "unittest")
        self.add_workflowname_and_deadline(fault_injection_plan, "fault_injection", "fault_injection")
        self.add_workflowname_and_deadline(post_validation_plan, "post_validation", "unittest")
        pre_validation_overview = self.display_phase_overview(pre_validation_plan, "pre_validation")
        fault_injection_overview = self.display_phase_overview(fault_injection_plan, "fault_injection")
        post_validation_overview = self.display_phase_overview(post_validation_plan, "post_validation")

        #---------------------------------------
        # summary (used for the analysis phase)
        #---------------------------------------
        for summary in self.summary_agent.stream({
            "time_schedule_overview": time_schedule_thought,
            "pre_validation_overview": pre_validation_overview,
            "fault_injection_overview": fault_injection_overview,
            "post_validation_overview": post_validation_overview},
            {"callbacks": [logger]}
        ):
            if (summary_str := summary.get("summary")) is not None:
                st.session_state.plan_container["summary"].write(summary_str)

        #----------
        # epilogue
        #----------
        # add file path to unit test and add params details to faults
        self.add_fpath_to_unittests([pre_validation_plan, fault_injection_plan, post_validation_plan], hypothesis)
        # for faults
        self.add_params_to_faults([fault_injection_plan], hypothesis)
        pseudo_streaming_text("##### CE experiment Planning Completed!", obj=plan_msg)
        return (
            logger.log, 
            ChaosExperimentPlan(
                time_schedule=time_schedule,
                pre_validation=pre_validation_plan,
                fault_injection=fault_injection_plan,
                post_validation=post_validation_plan,
                summary=summary_str
            )
        )

    def add_workflowname_and_deadline(
        self,
        phase,
        phase_name: Literal["pre_validation", "fault_injection", "post_validation"],
        type: Literal["unittest", "fault_injection"]
    ) -> None:
        name_counter = Counter()
        tasks = phase["unit_tests"] if type == "unittest" else phase["fault_injection"]
        header = f"{phase_name.split('_')[0]}-unittest" if type == "unittest" else "fault"
        for task in tasks:
            workflow_name = f'{header}-{sanitize_k8s_name(task["name"])}'
            name_counter[workflow_name] += 1
            if name_counter[workflow_name] == 1:
                task["workflow_name"] = workflow_name
            else:
                task["workflow_name"] = f"{workflow_name}{name_counter[workflow_name]}"
            if type == "unittest":
                duration = parse_time(task["duration"])
                if duration == 0:
                    task["deadline"] = "10s"
                else:
                    task["deadline"] = add_timeunit(duration + DEADLINE_MARGIN)
            else:
                task["deadline"] = task["duration"]

    def add_fpath_to_unittests(
        self,
        plans: List[dict],
        hypothesis: Hypothesis
    ) -> None:
        for plan in plans:
            for unit_test in plan["unit_tests"]:
                for steady_state in hypothesis.steady_states.elems:
                    if unit_test["name"] == steady_state.name:
                        unit_test["file_path"] = steady_state.unittest.path

    def add_params_to_faults(
        self,
        plans: List[dict],
        hypothesis: Hypothesis
    ) -> None:
        for plan in plans:
            for fault_injection in plan["fault_injection"]:
                for para_faults in hypothesis.fault.faults:
                    for fault in para_faults:
                        if fault_injection["name"] == fault.name and fault_injection["name_id"] == fault.name_id:
                            fault_injection["params"] = fault.params

    def get_plan_items(self) -> Dict[str, Any]:
        plan_items = {}
        plan_items["header"] = st.empty()
        expander = plan_items["header"].expander("##### Chaos Engineering Experiment Plan", expanded=True)
        with expander:
            # time schedule
            with st.container(border=True):
                st.write("###### :grey-background[Time Schedule]")
                plan_items["time_schedule_thought"] = st.empty()
                plan_items["total_time"] = st.empty()
                plan_items["pre_validation_time"] = st.empty()
                plan_items["fault_injection_time"] = st.empty()
                plan_items["post_validation_time"] = st.empty()
            # pre-validation
            with st.container(border=True):
                plan_items["pre_validation_header"] = st.empty()
                plan_items["pre_validation_header"].write("###### :blue-background[Pre-validation Phase]")
                plan_items["pre_validation_thought"] = st.empty()
                plan_items["pre_validation_unittests"] = st.empty()
            # fault-injection
            with st.container(border=True):
                plan_items["fault_injection_header"] = st.empty()
                plan_items["fault_injection_header"].write("###### :red-background[Fault-injection Phase]")
                plan_items["fault_injection_thought"] = st.empty()
                plan_items["fault_injection_unittests"] = st.empty()
                plan_items["fault_injection_faults"] = st.empty()
            # post-validation
            with st.container(border=True):
                plan_items["post_validation_header"] = st.empty()
                plan_items["post_validation_header"].write("###### :green-background[Post-validation Phase]")
                plan_items["post_validation_thought"] = st.empty()
                plan_items["post_validation_unittests"] = st.empty()
            # summary
            with st.container(border=True):
                st.write("###### :gray-background[Summary]")
                plan_items["summary"] = st.empty()
        return plan_items
    
    def display_phase_overview(
        self,
        plan: dict,
        phase_name: Literal["pre_validation", "fault_injection", "post_validation"]
    ) -> str:
        unittests_str = ""
        fault_str = ""
        if (thought := plan.get("thought")) is not None:
            st.session_state.plan_container[f"{phase_name}_thought"].write(thought)
        if (unittests := plan.get("unit_tests")) is not None:
            unittests_str = self.get_task_overview_str(unittests, "unittest")
            st.session_state.plan_container[f"{phase_name}_unittests"].write(unittests_str)
        if phase_name != "fault_injection":
            return f"{thought}\n{unittests_str}"
        if (fault_injections := plan.get("fault_injection")) is not None:
            fault_str = self.get_task_overview_str(fault_injections, "fault_injection")
            st.session_state.plan_container["fault_injection_faults"].write(fault_str)
        return f"{thought}\n{unittests_str}\n\n{fault_str}"

    def get_task_overview_str(
        self,
        tasks: List[dict],
        task_name: Literal["unittest", "fault_injection"]
    ) -> str:
        header = "Verified Steady State" if task_name == "unittest" else "Injected Faults"
        tasks_str = ""
        for i, task in enumerate(tasks):
            if (name := task.get("name")) is not None:
                tasks_str += f"- {header} #{i}: ```{name}```  \n"
            if (workflow_name := task.get("workflow_name")) is not None:
                tasks_str += f"  - Workflow Name: ```{workflow_name}```  \n"
            if (grace_period := task.get("grace_period")) is not None:
                tasks_str += f"  - Grace Period: ```{grace_period}```  \n"
            if (duration := task.get("duration")) is not None:
                tasks_str += f"  - Duration: ```{duration}```  \n"
        return tasks_str
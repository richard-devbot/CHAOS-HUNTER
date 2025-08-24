import os
import copy
from typing import List, Tuple, Literal, Optional

import streamlit as st

from .experiment_plan_agent import ChaosExperimentPlan
from ...ce_tools.ce_tool_base import CEToolBase
from ...ce_tools.chaosmesh.faults.selectors import Selectors
from ...hypothesis.steady_states.llm_agents.utils import Inspection, run_pod
from ...utils.wrappers import LLM, LLMBaseModel, LLMField
from ...utils.llms import build_json_agent, LLMLog, LoggingCallback
from ...utils.functions import (
    pseudo_streaming_text,
    file_list_to_str,
    dict_to_str,
    read_file,
    write_file,
    copy_file,
    get_file_extension,
    sanitize_filename,
    remove_curly_braces
)
from ...utils.schemas import File
from ...utils.constants import UNITTEST_BASE_PY_PATH


#---------------------------------------------
# prompts & output for adjusting fault scopes
#---------------------------------------------
SYS_ADJUST_SCOPE = """\
You are a helpful AI assistant for Chaos Engineering.
Given a previous K8s manifests, a Chaos-Engineering-experiment plan for it, and the current K8s manifests, you will determine whether we need to adujst the scope of fault injections for the current K8s manifests.
Always keep the following rules:
- Cosider how you must change or keep the scope (i.e., target) of the fault injecttion comparing the previous K8s manifests and the current K8s manifests.
- You only make minor adjustments related to resource changes, metadata change, etc, so NEVER make any scope changes that alter the original goal of the chaos experiment.
- {format_instructions}"""

USER_ADJUST_SCOPE = """\
# Here is the previous K8s manifests of my system:
{prev_k8s_yamls}

# Here is a planned Chaos Engineering:
{experiment_plan}

# Here is the current K8s menifests of my system:
{curr_k8s_yamls}

# Here is the scope of a fault injection for the previous manifests.
{curr_fault_injection}

Now, please adjust the scope of the fault injection for the current manifests. Note that you here focus on the 'selector' parameter (i.e., scope).
{format_instructions}"""

class NewScope(LLMBaseModel):
    thought: str = LLMField(description="Describe why you need to change/keep the scope of the fault injection for the current K8s manifests.")
    selector: Selectors = LLMField(description="Adjust the scope (target) of the fault injection comparing the differeneces between the current and previous manifests. ")


#-------------------------------------------
# prompts & output for adjusting unit tests
#-------------------------------------------
SYS_ADJUST_UNITTEST = """\
You are a helpful AI assistant for Chaos Engineering.
Given the previous K8s manifests, a previous unit test to verify whether the steady state satisfies the threshold, and the reconfigured K8s manifests, you will determine whether the unit test requires adjustment to account for the changes in the reconfigured manifests, and adjust it as necessary.
Always keep the following rules:
- First, consider which K8s manifest resource is the target of the unit test. If there are changes to that manifest, update the unit test as necessary. If there are no changes, the unit test should not require modification.
- You may only make minor adjustments to K8s API, HTTP, or DNS request to account for changes in resource types, parameter seetings, metadata, etc.
- The reconfiguration was made so that the system satisfy the threshold value in the previous unit test, so the threshold value or other parameters must remain unchanged in the new unit test. For example, suppose the number of replicas was reconfigured from 1 to 3 in order to maintain a steady state with more than 1 active pod at all times. In such cases, changing the threshold value from 1 to 3 would alter the intent of this steady state, so the threshold value must remain unchanged (i.e., more than 1 active pod)."
- If redundancy has been newly added, the unit test should verify whether the steady state is maintained by the entire redundancy.
- If the unit test's content needs no changes and only function or variable names need to be changed, leave them as they are to save output costs.
- {format_instructions}"""

USER_ADJUST_UNITTEST = """\
# Here is the previous K8s manifests of my system:
{prev_k8s_yamls}

# Here is the reconfigured K8s manifests of my system:
{curr_k8s_yamls}

# Here is the unit test for the previous manifests.
{prev_unittest}

Now, please determine whether the unit test requires adjustment to account for the changes in the reconfigured manifests, and adjust it as necessary."""

USER_READJUST_UNITTEST = """\
Your current unittest cause errors when coducted.
The error message is as follows:
{error_message}

This unit test should be succeeded.
Please analyze the reason why the errors occur, then fix the errors.
Always keep the following rules:
- NEVER repeat the same fixes that have been made in the past.
- Fix only the parts related to the errors without changing the original intent.
- {format_instructions}"""

class AdjustedUnittest(LLMBaseModel):
    thought: str = LLMField(description="Describe your thought process for determining whether the unit test requires adjustment to account for the changes in the reconfigured manifests: First, consider which K8s manifest resource is the target of the unit test. If there are changes to that manifest, update the unit test as necessary. If there are no changes, the unit test should not require modification. If the unit test needs updating, describe also how you modify the inspection method according to the differences between the previous and reconfigured manifests. If the modification is not required, describe the reason.")
    code: Optional[str] = LLMField(description="If the unit test needs updating, write a new unit test code with the inspection method modified. Write only the content of the code without enclosing it in a code block. If not, this field is not required.")


#------------------
# agent definition
#------------------
class ExperimentRePlanAgent:
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
        self.scope_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_ADJUST_SCOPE), ("human", USER_ADJUST_SCOPE)],
            pydantic_object=NewScope,
            is_async=False,
        )
        self.unittest_agent = build_json_agent(
            llm=llm,
            chat_messages=[("system", SYS_ADJUST_UNITTEST), ("human", USER_ADJUST_UNITTEST)],
            pydantic_object=AdjustedUnittest,
            is_async=False,
        )

    def replan(
        self,
        prev_k8s_yamls: List[File],
        prev_experiment,
        curr_k8s_yamls: List[File],
        kube_context: str,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[LLMLog, dict]:
        #-----------------
        # initialization
        #-----------------
        logger = LoggingCallback(name="experiment_replan", llm=self.llm)
        new_experiment_plan = copy.deepcopy(prev_experiment.plan)

        #------------------------
        # replan the fault scope
        #------------------------
        plan_msg = st.empty()
        pseudo_streaming_text("##### Adjusting the scope of fault injection...", obj=plan_msg)
        self.replan_scope(
            experiment=prev_experiment,
            experiment_plan=new_experiment_plan,
            prev_k8s_yamls=prev_k8s_yamls,
            curr_k8s_yamls=curr_k8s_yamls,
            logger=logger
        )
        pseudo_streaming_text("##### The fault-scope adjustment Completed!", obj=plan_msg)

        #----------------------
        # replan the unit test
        #----------------------
        self.replan_unittests(
            experiemnt_plan=new_experiment_plan,
            prev_k8s_yamls=prev_k8s_yamls,
            curr_k8s_yamls=curr_k8s_yamls,
            logger=logger,
            kube_context=kube_context,
            work_dir=work_dir,
            max_retries=max_retries
        )

        return (
            logger.log, 
            ChaosExperimentPlan(**new_experiment_plan)
        )
    
    def replan_scope(
        self,
        experiment,
        experiment_plan: dict,
        prev_k8s_yamls: List[File],
        curr_k8s_yamls: List[File],
        logger: LoggingCallback
    ) -> None:
        fault_injections = experiment_plan["fault_injection"]["fault_injection"]
        for fault_injection in fault_injections:
            st.write("Current fault injection settings:")
            st.write(f"{self.get_fault_str(fault_injection)}")
            thought_empty = st.empty()
            st.write("Next fault injection scope:")
            selector_empty = st.empty()
            for token in self.scope_agent.stream({
                "prev_k8s_yamls": file_list_to_str(prev_k8s_yamls),
                "experiment_plan": experiment.to_str(),
                "curr_k8s_yamls": file_list_to_str(curr_k8s_yamls),
                "curr_fault_injection": self.get_fault_str(fault_injection)},
                {"callbacks": [logger]}
            ):
                if (thought := token.get("thought")) is not None:
                    thought_empty.write(thought)
                if (selector := token.get("selector")) is not None:
                    selector_empty.write(selector)
            # change the scope
            fault_injection["params"]["selector"] = selector

    def get_fault_str(self, fault_injection: dict) -> str:
        fault_overview = self.get_task_overview_str([fault_injection], "fault_injection")
        params = dict_to_str(fault_injection["params"])
        return fault_overview + "\nParameters\n" + params

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
    
    def replan_unittests(
        self,
        experiemnt_plan: dict,
        prev_k8s_yamls: List[File],
        curr_k8s_yamls: List[File],
        logger: LoggingCallback,
        kube_context: str,
        work_dir: str,
        max_retries: int = 3, 
    ) -> None:
        # copy the base class
        copy_file(UNITTEST_BASE_PY_PATH, f"{work_dir}/unittest_base.py")

        # gather unittests
        unittests = []
        for phase_name in ["pre_validation", "fault_injection", "post_validation"]:
            unittests.extend(experiemnt_plan[phase_name]["unit_tests"])

        # adjust each unit test
        adjusted_result = {}
        for unittest in unittests:
            unittest_code = read_file(unittest["file_path"])
            #---------------------
            # adjust the unittest
            #---------------------
            if unittest["name"] not in adjusted_result:
                #----------------
                # initialization
                #----------------
                output_history = []
                error_history = []
                fname_prefix = f'unittest_{sanitize_filename(unittest["name"])}'
                tool_type = "k8s" if get_file_extension(unittest["file_path"]) == ".py" else "k6"

                #-----------------------------------------------------
                # generate an adjusted unittest if needed (first try)
                #-----------------------------------------------------
                st.write("Adjusted unittest")
                self.thought_empty = st.empty()
                self.code_empty = st.empty()
                for token in self.unittest_agent.stream({
                    "prev_k8s_yamls": file_list_to_str(prev_k8s_yamls),
                    "prev_unittest": unittest_code,
                    "curr_k8s_yamls": file_list_to_str(curr_k8s_yamls)},
                    {"callbacks": [logger]}
                ):
                    if (thought := token.get("thought")) is not None:
                        self.thought_empty.write(thought)
                    if (code := token.get("code")) is not None:
                        self.code_empty.code(code)

                #-----------------------
                # validate the unittest
                #-----------------------
                mod_count = 0
                while(1):
                    assert mod_count < max_retries, f"MAX_MOD_COUNTS_EXCEEDED: {max_retries}"

                    # save the new unit test
                    file_path = f"{work_dir}/{fname_prefix}_mod{mod_count}"
                    file_path += ".py" if tool_type == "k8s" else ".js"
                    if code is not None and len(code) > 0 and code != "None" and code != "none" and code != "null":
                        unittest_code = code
                        write_file(file_path, code)
                        inspection_ = Inspection(
                            tool_type=tool_type,
                            duration="5s",
                            script=File(
                                path=file_path,
                                content=code,
                                work_dir=work_dir,
                                fname=os.path.basename(file_path)
                            )
                        )
                        output_history.append(token)
                    else:
                        write_file(file_path, unittest_code)
                        inspection_ = Inspection(
                            tool_type=tool_type,
                            duration="5s",
                            script=File(
                                path=file_path,
                                content=unittest_code,
                                work_dir=work_dir,
                                fname=os.path.basename(file_path)
                            )
                        )
                        output_history.append(f"The unit test remains unchanged and is as follows:\n{unittest_code}")

                    # run the unit test and validate it
                    returncode, console_log = run_pod(
                        inspection=inspection_,
                        work_dir=work_dir,
                        kube_context=kube_context,
                        namespace="chaos-hunter"
                    )
                    
                    # validation
                    if returncode == 0:
                        break
                    error_history.append(console_log)
                    print(console_log)

                    # rewrite the unit test
                    token = self.debug_unittest(
                        unittest_code=unittest_code,
                        prev_k8s_yamls=prev_k8s_yamls,
                        curr_k8s_yamls=curr_k8s_yamls,
                        output_history=output_history,
                        error_history=error_history,
                        logger=logger
                    )
                    code = token["code"]

                    # increment count
                    mod_count += 1
                unittest["file_path"] = file_path
                adjusted_result[unittest["name"]] = file_path
            else:
                unittest["file_path"] = adjusted_result[unittest["name"]]
    
    def debug_unittest(
        self,
        unittest_code: str,
        prev_k8s_yamls: List[File],
        curr_k8s_yamls: List[File],
        output_history: List[dict | str],
        error_history: List[str],
        logger: LoggingCallback
    ) -> dict:
        #------------------------------------------
        # update chat messages & build a new agent
        #------------------------------------------
        # update chat messages
        chat_messages=[("system", SYS_ADJUST_UNITTEST), ("human", USER_ADJUST_UNITTEST)]
        for output, error in zip(output_history, error_history):
            if isinstance(output, dict):
                chat_messages.append(("ai", dict_to_str(output)))
            else:
                chat_messages.append(("human", remove_curly_braces(output)))
            chat_messages.append(("human", USER_READJUST_UNITTEST.replace("{error_message}", error.replace('{', '{{').replace('}', '}}'))))
        # build a new agent
        debugging_agent = build_json_agent(
            llm=self.llm,
            chat_messages=chat_messages,
            pydantic_object=AdjustedUnittest,
            is_async=False,
        )

        #----------------------------------
        # debugging the adjusted unit test
        #----------------------------------
        st.write("Debugging:")
        self.error_handling_empty = st.empty()
        for token in debugging_agent.stream({
            "prev_k8s_yamls": file_list_to_str(prev_k8s_yamls),
            "prev_unittest": unittest_code,
            "curr_k8s_yamls": file_list_to_str(curr_k8s_yamls)},
            {"callbacks": [logger]}
        ):
            if (thought := token.get("thought")) is not None:
                self.error_handling_empty.write(thought)
            if (code := token.get("code")) is not None:
                self.code_empty.code(code)
        return token
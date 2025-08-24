import os
import json
from typing import List, Dict, Tuple

from .utils import run_pod, Inspection
from ....preprocessing.preprocessor import ProcessedData
from ....utils.wrappers import LLM, LLMBaseModel, LLMField
from ....utils.llms import build_json_agent, LLMLog, LoggingCallback
from ....utils.schemas import File
from ....utils.functions import write_file, read_file, copy_file, sanitize_filename
from ....utils.constants import UNITTEST_BASE_PY_PATH
from ....utils.streamlit import StreamlitContainer


#---------
# prompts
#---------
SYS_WRITE_K8S_UNITTEST = """\
You are a helpful AI assistant for writing unit tests in Python.
Given the steady state, python script to inspect it, and its threshold, please write a Python unit test (including for-loop for certain duration) to verify if the steady state satisfies the threshold by adding assertion.
Always keep the following rules:
- Include as many comments as possible in your code so that humans can easily understand what you did later.
- Use the Kubernetes Python API.
- If there is an explicitly defined values to be satisfied, hardcode that value and use it for threshold assertion.
- Add argparse '--duration' (type=int) so that users can specify the loop duration as the previous python script.
- NEVER use "unittest" module to use argparse.
- Create a unit test by inheriting from the 'K8sAPIBase' class below (available via ```from unittest_base import K8sAPIBase```):
```python
{unittest_base_py}
```
- Add a entry point at the bottom to allow the test to be run from the command line, as follows:
```
if __name__ == '__main__':
    main()
```
- {format_instructions}""".replace("{unittest_base_py}", read_file(UNITTEST_BASE_PY_PATH))

USER_WRITE_K8S_UNITTEST = """\
The steady state:
{steady_state_name}: {steady_state_thought}

The steady state was inspected with the following python code of k8s client libraries:
{command}

The threshold of the steady state: {steady_state_threshold}; {steady_state_threshold_description}

Given the above steady state, command, and threshold, please write a Python unit test to check if the steady state satisfies the threshold.
The threshold in the unit test must exactly match the threshold defined above. Implement it to support variable durations. Use a representative value (e.g., percentage, ratio, etc.) for the threshold. NEVER use any fixed absolute values for the threshold."""

SYS_WRITE_K6_UNITTEST = """\
You are a helpful AI assistant for writing unit tests in k6.
Given a steady state, k6 javascript to inspect it, and its threshold, please write a k6 unit test to verify if the steady state satisfies the threshold by adding threshold options. 
Always keep the following rules:
- Include as many comments as possible in your code so that humans can easily understand what you did later.
- Add "thresholds" in "options" section to the given k6 javascript.
- {format_instructions}"""

USER_WRITE_K6_UNITTEST = """\
The steady state:
{steady_state_name}: {steady_state_thought}

The steady state can be inspected with the following k6 javascript:
{command}

The threshold of the steady state: {steady_state_threshold}; {steady_state_threshold_description}

Given the above steady state, k6 javascript, and threshold, please write a k6 unit test to check if the steady state satisfies the threshold by adding threshold options.
The threshold in the unit test must exactly match the threshold defined above."""

USER_REWRITE_UNITTEST = """\
Your current unittest cause errors when coducted.
The error message is as follows:
{error_message}

Please analyze the reason why the errors occur, then fix the errors.
Always keep the following rules:
- Ensure that the implementation supports variable durations again.
- NEVER repeat the same fixes that have been made in the past.
- Fix only the parts related to the errors without changing the original content.
- {format_instructions}"""


#--------------------
# json output format
#--------------------
class PythonUnitTest(LLMBaseModel):
    thought: str = LLMField(description="Describe how you add the threshold assersion to the inspection Python script.")
    code: str = LLMField(description='Python unit test code. Implement a for loop that checks the status every second for the duration, and implement summary output at the end for both success and failure cases (i.e., print and assertion).\n- Please add an entry point at the bottom to allow the test to be run from the command line.\n- Please add argparse \'--duration\' (type=int) so that users can specify the loop duration. Write only the content of the code, and for dictionary values, enclose them within a pair of single double quotes (\").')

class K6UnitTest(LLMBaseModel):
    thought: str = LLMField(description="Describe how you add the threshold check to the inspection K6 script.")
    code: str = LLMField(description='K6 unit test code (javascript). Write only the content of the code, and for dictionary values, enclose them within a pair of single double quotes (\").')


#------------------
# agent definition
#------------------
class UnittestAgent:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def write_unittest(
        self,
        input_data: ProcessedData,
        steady_state_draft: List[Dict[str, str]],
        inspection: List[Inspection],
        threshold: List[Dict[str, str]],
        predefined_steady_states: list,
        display_container: StreamlitContainer,
        kube_context: str,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[LLMLog, File]:
        self.logger = LoggingCallback(name="unittest_writing", llm=self.llm)
        copy_file(UNITTEST_BASE_PY_PATH, f"{work_dir}/unittest_base.py")
        
        #----------------
        # initialization
        #----------------
        output_history = []
        error_history = []
        fname_prefix = f'unittest_{sanitize_filename(steady_state_draft["name"])}'
        display_container.create_subcontainer(id="unittest", header="##### 📄 Unit test to validate the steady state")

        #---------------
        # first attempt
        #---------------
        unittest = self.generate_unittest(
            steady_state_draft=steady_state_draft,
            inspection=inspection,
            threshold=threshold,
            predefined_steady_states=predefined_steady_states,
            display_container=display_container
        )

        #---------------------------------------------------------
        # validattion loop: rewrite the unit test until it passes
        #---------------------------------------------------------
        mod_count = 0
        while(1):
            # save the unit test
            file_path = f"{work_dir}/{fname_prefix}_mod{mod_count}"
            file_path += ".py" if inspection.tool_type == "k8s" else ".js"
            write_file(file_path, unittest["code"])
            output_history.append(unittest)

            # run the unit test and validate it
            inspection_ = Inspection(
                tool_type=inspection.tool_type,
                duration=inspection.duration,
                script=File(
                    path=file_path,
                    content=unittest["code"],
                    work_dir=work_dir,
                    fname=os.path.basename(file_path)
                )
            )
            
            subsubcontainer_id = f"unittest_result{mod_count}"
            display_container.create_subsubcontainer(
                subcontainer_id="unittest",
                subsubcontainer_id=subsubcontainer_id
            )
            returncode, console_log = run_pod(
                inspection=inspection_,
                work_dir=work_dir,
                kube_context=kube_context,
                namespace="chaos-hunter",
                display_container=display_container.get_subsubcontainer(subsubcontainer_id)
            )
            display_container.create_subsubcontainer(
                subcontainer_id="unittest",
                subsubcontainer_id=f"unittest_value{mod_count}",
                text=console_log,
                is_code=True,
                language="powershell"
            )
            print(console_log)

            # validation
            if returncode == 0:
                break
            error_history.append(console_log)

            # assert mod_count and increment count
            assert mod_count < max_retries, f"MAX_MOD_COUNT_EXCEEDED: {max_retries}"
            mod_count += 1

            # rewrite the unit test
            unittest = self.generate_unittest(
                steady_state_draft=steady_state_draft,
                inspection=inspection,
                threshold=threshold,
                predefined_steady_states=predefined_steady_states,
                display_container=display_container,
                mod_count=mod_count,
                output_history=output_history,
                error_history=error_history
            )
        
        #----------
        # epilogue
        #----------
        display_container.update_header(f"##### ✅ Steady state #{predefined_steady_states.count+1}: {steady_state_draft['name']}", expanded=True)
        return (
            self.logger.log,
            File(
                path=file_path,
                content=output_history[-1]["code"],
                work_dir=work_dir,
                fname=os.path.basename(file_path)
            )
        )

    def generate_unittest(
        self,
        steady_state_draft: Dict[str, str],
        inspection: Inspection,
        threshold: Dict[str, str],
        predefined_steady_states: list,
        display_container: StreamlitContainer,
        mod_count: int = -1,
        output_history: List[Dict[str, str]] = [],
        error_history: List[str] = []
    ) -> Dict[str, str]:
        # update chat messages
        if inspection.tool_type == "k8s":
            chat_messages = [("system", SYS_WRITE_K8S_UNITTEST), ("human", USER_WRITE_K8S_UNITTEST)]
        else:
            chat_messages = [("system", SYS_WRITE_K6_UNITTEST), ("human", USER_WRITE_K6_UNITTEST)]
        for output, error in zip(output_history, error_history):
            chat_messages.append(("ai", json.dumps(output).replace('{', '{{').replace('}', '}}')))
            chat_messages.append(("human", USER_REWRITE_UNITTEST.replace("{error_message}", error.replace('{', '{{').replace('}', '}}'))))
        # build agent with the updated chat messages
        agent = build_json_agent(
            llm=self.llm,
            chat_messages=chat_messages,
            pydantic_object=PythonUnitTest if inspection.tool_type == "k8s" else K6UnitTest,
            is_async=False
        )

        # generate a unit test
        display_container.create_subsubcontainer(subcontainer_id="unittest", subsubcontainer_id=f"unittest_thought{mod_count}")
        display_container.create_subsubcontainer(subcontainer_id="unittest", subsubcontainer_id=f"unittest{mod_count}")
        for token in agent.stream({
            "steady_state_name": steady_state_draft["name"],
            "steady_state_thought": steady_state_draft["thought"],
            "command": inspection.script.content,
            "steady_state_threshold": threshold["threshold"],
            "steady_state_threshold_description": threshold["reason"]},
            {"callbacks": [self.logger]}
        ):
            if (thought := token.get("thought")) is not None:
                display_container.update_subsubcontainer(thought, f"unittest_thought{mod_count}")
            if (code := token.get("code")) is not None:
                display_container.update_subsubcontainer(
                    code,
                    f"unittest{mod_count}",
                    is_code=True,
                    language="python" if inspection.tool_type == "k8s" else "javascript"
                )
        return {"thought": thought, "code": code}
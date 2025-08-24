from typing import List, Dict, Tuple, Literal

from .utils import Inspection, run_pod
from ....preprocessing.preprocessor import ProcessedData
from ....utils.wrappers import LLM, BaseModel, Field
from ....utils.llms import build_json_agent, LLMLog, LoggingCallback
from ....utils.schemas import File
from ....utils.functions import write_file, dict_to_str, sanitize_filename
from ....utils.streamlit import StreamlitContainer


INTERVAL_SEC = "1s"
MAX_DURATION = "5s"


#---------
# prompts
#---------
SYS_DEFINE_CMD = """\
You are a helpful AI assistant for Chaos Engineering.
Given Kubernetes (K8s) manifests for a network system and its state type, you will inspect the current value of the state type.
Always keep the following rules:
- You can use either K8s API (Python) or k6 (Javascript) to inspect the state.
- Use the K8s API for checking the current state of K8s resources
- Use k6 for checking communication statuses/metrics, such as request sending, response time, latency, etc.
- If you use K8s API, consider appropriate test duration. If you use k6, consider not only appropriate test duration but also an appropriate number of virtual users in the load test.
- Pay attention to namespace specification. If the namespace is specified in the manifest, it is deployed with the namespace. If not, it is deployed with the 'default' namespace.
- When sending requests to a K8s resources, use their internal DNS names in the format: ```service-name.namespace.svc.cluster.local:port```. For the port setting, use the service port, not the targetPort or nodePort. Ensure that the port matches the service port defined in the manifest.
- If other request formats are provided by the user, follow the user's format.
- {format_instructions}"""

USER_DEFINE_CMD = """\
# Here is the overview of my system:
{user_input}

# You will inspect the following state of my system:
{steady_state_name}: {steady_state_thought}

# Please follow the instructions below regarding Chaos Engineering:
{ce_instructions}

Please define the way to inspect "{steady_state_name}" in the system defined by the above k8s manifest(s)."""

USER_REWRITE_INSPECTION = """\
Your current inspection script causes errors when executed.
The error messages are as follows:
{error_message}

Please analyze the reason why the errors occur, then fix the errors.
Always keep the following rules:
- NEVER repeat the same fixes that have been made in the past.
- Fix only the parts related to the errors without changing the original content.
- If requests failed, double-check if the service port is correct.
- You can change the tool (k8s -> k6 or k6 -> k8s) if it can keep the original intention.
- {format_instructions}"""


#--------------------
# json output format
#--------------------
class K8sAPI(BaseModel):
    duration: str = Field(description=f"Duration of the status check every second in a for loop. Set appropriate duration to check the current state of the system. The maximum duration is {MAX_DURATION}.")
    script: str = Field(description="Python script with K8s client libraries to inspect the current status of a K8s resource. Write only the content of the code, and for dictionary values, enclose them within a pair of single double quotes (\"). Implement a for loop that checks the status every second for the duration, and print a summary of the results at the end.\n- To support docker env, please configure the client as follows: ```\n# Load Kubernetes configuration based on the environment\n    if os.getenv('KUBERNETES_SERVICE_HOST'):\n        config.load_incluster_config()\n    else:\n        config.load_kube_config()\n```\n- Please add a Add a entry point at the bottom to allow the test to be run from the command line.\n- Please add argparse '--duration' (type=int) so that users can specify the loop duration.")

class K6JS(BaseModel):
    vus: int = Field(description="The number of virtual users. You can run a load test with the number of virutal users.")
    duration: str = Field(description=f"Duration of the load test. Set appropriate duration to check the current state of the system. The maximum duration is {MAX_DURATION}.")
    script: str = Field(description=f"k6 javascript to inspect the current state. Write only the content of the code, and for dictionary values, enclose them within a pair of single double quotes (\"). In options in the javascript, set the same 'vus' and 'duration' options as the above. The interval of status check must be {INTERVAL_SEC} second(s). Set a threshold that triggers an error when a request failure is clearly occurring.")

class _Inspection(BaseModel):
    thought: str = Field(description="Describe your thoughts for the tool usage. e.g., the reason why you choose the tool and how to use.")
    tool_type: Literal["k8s", "k6"] = Field(description="Tool to inspect the steady state. Select from ['k8s', 'k6'].")
    tool: K8sAPI | K6JS = Field(description="If tool_tyepe='k8s', write here K8sAPI. If tool_tyepe='k6', write here K6JS.")


#------------------
# agent definition
#------------------
class InspectionAgent:
    def __init__(
        self,
        llm: LLM,
        namespace: str = "chaos-hunter"
    ) -> None:
        self.llm = llm
        self.namespace = namespace
    
    def inspect_current_state(
        self,
        input_data: ProcessedData,
        steady_state_draft: Dict[str, str],
        predefined_steady_states: list,
        display_container: StreamlitContainer,
        kube_context: str,
        work_dir: str,
        max_retries: int = 3
    ) -> Tuple[LLMLog, Inspection]:
        #---------------
        # intialization
        #---------------
        self.logger = LoggingCallback(name="tool_command_writing", llm=self.llm)
        display_container.create_subcontainer(id="inspection", header="##### 🔍 Current state inspection")
        output_history = []
        error_history = []

        #---------------
        # first attempt
        #---------------
        raw_output, inspection = self.generate_inspection(
            input_data=input_data,
            steady_state_draft=steady_state_draft,
            display_container=display_container,
            work_dir=work_dir
        )
        output_history.append(raw_output)

        #-----------------------------------------
        # validate loop for the inspection script
        #-----------------------------------------
        mod_count = 0
        while (1):
            # run the inspection script
            subsubcontainer_id = f"inspection_status{mod_count}"
            display_container.create_subsubcontainer(
                subcontainer_id="inspection",
                subsubcontainer_id=subsubcontainer_id
            )
            returncode, console_log = run_pod(
                inspection,
                work_dir,
                kube_context,
                self.namespace,
                display_container.get_subsubcontainer(subsubcontainer_id)
            )
            inspection.result = console_log
            display_container.create_subsubcontainer(
                subcontainer_id="inspection",
                subsubcontainer_id=f"inspection_value{mod_count}",
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

            # modify the inspections
            raw_output, inspection = self.generate_inspection(
                input_data=input_data,
                steady_state_draft=steady_state_draft,
                display_container=display_container,
                work_dir=work_dir,
                mod_count=mod_count,
                output_history=output_history,
                error_history=error_history,
            )
            output_history.append(raw_output)

        return self.logger.log, inspection
    
    def generate_inspection(
        self,
        input_data: ProcessedData,
        steady_state_draft: Dict[str, str],
        display_container: StreamlitContainer,
        work_dir: str,
        mod_count: int = -1,
        output_history: List[dict] = [],
        error_history: List[str] = [],
    ) -> Tuple[dict, Inspection]:
        #---------------------------------------
        # update chat messages & build an agent
        #---------------------------------------
        # update chat messages
        chat_messages = [("system", SYS_DEFINE_CMD), ("human", USER_DEFINE_CMD)]
        for output, error in zip(output_history, error_history):
            chat_messages.append(("ai", dict_to_str(output)))
            chat_messages.append(("human", USER_REWRITE_INSPECTION.replace("{error_message}", error.replace('{', '{{').replace('}', '}}'))))
        # build an agent
        agent = build_json_agent(
            llm=self.llm,
            chat_messages=chat_messages,
            pydantic_object=_Inspection,
            is_async=False
        )

        #------------------------------
        # generate a inspection script
        #------------------------------
        display_container.create_subsubcontainer(subcontainer_id="inspection", subsubcontainer_id=f"inspection_description{mod_count}")
        display_container.create_subsubcontainer(subcontainer_id="inspection", subsubcontainer_id=f"inspection_script{mod_count}")
        for cmd in agent.stream({
            "user_input": input_data.to_k8s_overview_str(),
            "ce_instructions": input_data.ce_instructions,
            "steady_state_name": steady_state_draft["name"],
            "steady_state_thought": steady_state_draft["thought"]},
            {"callbacks": [self.logger]}
        ):
            if (thought := cmd.get("thought")) is not None:
                display_container.update_subsubcontainer(thought, f"inspection_description{mod_count}")
            if (tool := cmd.get("tool")) is not None:
                if (tool_type := cmd.get("tool_type")) is not None:
                    if tool_type == "k8s":
                        if (code := tool.get("script")) is not None:
                            duration = tool.get("duration")
                            fname = "k8s_" + sanitize_filename(steady_state_draft["name"])
                            fname = f"{fname}_mod{mod_count}.py" if mod_count >= 0 else f"{fname}.py"
                            display_container.update_subsubcontainer(
                                f"{thought}  \ntool: ```{tool_type}``` duration: ```{duration}```  \nInspection script (Python) ```{fname}```:",
                                f"inspection_description{mod_count}"
                            )
                            display_container.update_subsubcontainer(
                                code,
                                f"inspection_script{mod_count}",
                                is_code=True,
                                language="python"
                            )
                    elif tool_type == "k6":
                        if (code := tool.get("script")) is not None:
                            vus = tool.get("vus")
                            duration = tool.get("duration")
                            fname = "k6_" + sanitize_filename(steady_state_draft["name"])
                            fname = f"{fname}_mod{mod_count}.js" if mod_count >= 0 else f"{fname}.js"
                            display_container.update_subsubcontainer(
                                f"{thought}  \ntool: ```{tool_type}``` vus: ```{vus}``` duration: ```{duration}```  \nInspection script (Javascript) ```{fname}```:",
                                f"inspection_description{mod_count}"
                            )
                            display_container.update_subsubcontainer(
                                code,
                                f"inspection_script{mod_count}",
                                is_code=True,
                                language="javascript"
                            )
        
        #----------
        # epilogue
        #----------
        if tool_type not in ["k8s", "k6"]:
            raise TypeError(f"Invalid tool type selected: {tool_type}. Select either 'k8s' or 'k6'.")
        fpath = f"{work_dir}/{fname}"
        write_file(fpath, code)
        return (
            cmd,
            Inspection(
                tool_type=tool_type,
                duration=duration,
                script=File(
                    path=fpath,
                    content=code,
                    work_dir=work_dir,
                    fname=fname
                )
            )
        )

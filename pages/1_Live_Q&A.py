import os
import time
import json
import streamlit as st
from streamlit_extras.bottom_container import bottom

from ChaosHunter_demo import WORK_DIR, NAMESPACE, CHAOSHUNTER_ICON, CHAOSHUNTER_IMAGE
from chaos_hunter.utils.app_utils import (
    apply_hide_st_style,
    apply_hide_height0_components,
    apply_centerize_components_vertically,
    apply_remove_sidebar_topspace,
    add_chashunter_icon,
    apply_remove_example_bottomspace
)
from chaos_hunter.ce_tools.ce_tool import CEToolType, CETool
from chaos_hunter.utils.llms import load_llm
from chaos_hunter.utils.functions import (
    remove_files_in,
    remove_all_resources_in,
    remove_all,
    save_json,
    load_json,
    get_timestamp
)
from chaos_hunter.preprocessing.preprocessor import ProcessedData
from chaos_hunter.hypothesis.llm_agents.steady_states.steady_state_agent import SteadyStateAgent, SteadyStates
from chaos_hunter.hypothesis.llm_agents.faults.fault_agent import FaultAgent
from chaos_hunter.hypothesis.hypothesizer import Hypothesis


def init_agent(
    model_name: str = "openai/gpt-4o",
    temperature: float = 0.0,
    port: int = 8000,
    seed: int = 42
) -> None:
    llm = load_llm(
        model_name=model_name, 
        temperature=temperature,
        port=port,
        model_kwargs={"seed": seed}
    )
    st.session_state.steady_state_agent = SteadyStateAgent(
        llm=llm,
        test_dir="",
        namespace=NAMESPACE,
        max_mod_loop=3
    )
    st.session_state.fault_agent = FaultAgent(
        llm=llm,
        ce_tool=CETool.init(CEToolType.chaosmesh),
        test_dir=f"{WORK_DIR}/unit_test",
        namespace=NAMESPACE
    )
    st.session_state.model_name = model_name

def main():
    #---------------------------
    # initialize session states
    #---------------------------
    if "state_list" not in st.session_state:
        st.session_state.state_list = {}
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "count" not in st.session_state:
        st.session_state.count = 0
    if "instructions" not in st.session_state:
        st.session_state.instructions = None
    if "is_first_run" not in st.session_state:
        st.session_state.is_first_run = True
    if "steady_states" not in st.session_state:
        st.session_state.steady_states = None
    if "processed_data" not in st.session_state:
        st.session_state.processed_data = None

    #--------------
    # CSS settings
    #--------------
    st.set_page_config(
        page_title="Hypohesis demo",
        page_icon=CHAOSHUNTER_IMAGE,
    )
    # st.set_page_config(layout="wide")
    apply_hide_st_style()
    apply_hide_height0_components()
    apply_centerize_components_vertically()
    apply_remove_sidebar_topspace()

    #---------
    # sidebar
    #---------
    # Only show logo if the image file exists
    logo_path = "static/chashunter_icon.png"
    if os.path.exists(logo_path):
        st.logo(logo_path)
    else:
        st.title("ChaosHunter")
    with st.sidebar:
        # settings
        with st.expander("Settings", expanded=True):
            model_name = st.selectbox(
                "Model", 
                (
                    "openai/gpt-4o-2024-08-06",
                    "openai/gpt-4o-2024-05-13",
                    "google/gemini-1.5-pro",
                    "anthropic/claude-3-5-sonnet-20240620",
                    "meta-llama/Meta-Llama-3-70B-Instruct"
                )
            )
            if model_name.startswith("openai"):
                st.text_input(
                    label="API keys",
                    key="openai_key",
                    placeholder="OpenAI API key",
                    type="password"
                )
            else:
                st.text_input(
                    label="Token",
                    key="hf_token",
                    placeholder="Hugging Face token",
                    type="password"
                )

            subphase_type = st.selectbox(
                "Sub-phase", 
                (
                    "Steady-state definition", 
                    "Failure definition"
                )
            )

        # clean sandbox
        clean1, clean2, clean3 = st.columns(3)
        with clean1:
            st.button("Clean sandbox", key="clean_sandbox", on_click=remove_files_in, args=(WORK_DIR, ))
        with clean2:
            st.button("Clean k8s cluster", key="clean_k8s", on_click=remove_all_resources_in, args=(NAMESPACE, ))
        with clean3:
            st.button("Clean both", key="clean_both", on_click=remove_all, args=(WORK_DIR, NAMESPACE, ))
        
        # command history
        if not st.session_state.is_first_run:
            st.write("Command history")

    #--------------------------------
    # initialize plan2workflow agent
    #--------------------------------
    if "fault_agent" not in st.session_state or model_name != st.session_state.model_name:
        init_agent(model_name=model_name)

    # greeding 
    if len(st.session_state.chat_history) == 0 and st.session_state.is_first_run:
        add_chashunter_icon()
        greeding = "Here is a demo space for the Hypothesis Phase. You can start from the Hypothesis pahse by inputting result files (JSON format) so far."
        if st.session_state.count == 0: # streaming
            elem = st.empty()
            words = ""
            for word in list(greeding):
                words += word
                elem.markdown(f'<center> <h3> {words} </h3> </center>', unsafe_allow_html=True)
                time.sleep(0.02)
        else:
            st.markdown(f'<center> <h3> {greeding} </h3> </center>', unsafe_allow_html=True)

    #----------
    # examples
    #----------    
    def submit_example(number: int, example_dir: str) -> None:
        decorated_func = st.experimental_dialog(f"Example input #{number}")(submit_example_internal)
        decorated_func(example_dir)

    def submit_example_internal(example_dir: str) -> None:
        # load the example
        processed_data_dict = load_json(f"{example_dir}/processed_data.json")
        processed_data = ProcessedData(**processed_data_dict)
        steady_states_dict = load_json(f"{example_dir}/steady_states.json")
        steady_states = SteadyStates(**steady_states_dict)
        # display the example
        st.write("### Processed Data (dict):")
        st.write(processed_data_dict)
        st.write("### Steady States (dict):")
        st.write(steady_states_dict)
        with st.columns(3)[1]:
            # submit the example
            if st.button("Try this one"):
                st.session_state.processed_data = processed_data
                st.session_state.steady_states = steady_states
                st.rerun()

    st.session_state.bottom_container = bottom()
    with st.session_state.bottom_container:
        if st.session_state.is_first_run:
            apply_remove_example_bottomspace(px=-30)
            # examples
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("example #1", key="example1", use_container_width=True):
                    submit_example(
                        number=1,
                        example_dir="./examples/hypothesizer_inputs/nginx"
                    )
            with col2:
                if st.button("example #2", key="example2", use_container_width=True):
                    submit_example(
                        number=2,
                        example_dir="./examples/hypothesizer_inputs/nginx"
                    )
            with col3:
                if st.button("example#3", key="example3", use_container_width=True):
                    submit_example(
                        number=3,
                        example_dir="./examples/hypothesizer_inputs/nginx"
                    )
        else:
            apply_remove_example_bottomspace()
        # inputs
        upload_col, submit_col = st.columns([10, 2], vertical_alignment="bottom")
        with upload_col:
            if files := st.file_uploader(
                "upload an experiment plan",
                type="JSON",
                accept_multiple_files=True,
                label_visibility="hidden"
            ):
                for file in files:
                    if file.name.startswith("steady_states"):
                        st.session_state.steady_states_tmp = SteadyStates(**json.loads(file.read().decode("utf-8")))
                    elif file.name.startswith("processed_data"):
                        st.session_state.processed_data_tmp = ProcessedData(**json.loads(file.read().decode("utf-8")))
        with submit_col:
            st.text("")
            if st.button("Submit", key="submit"):
                if st.session_state.processed_data_tmp is not None:
                    st.session_state.processed_data = st.session_state.processed_data_tmp
                if st.session_state.steady_states_tmp is not None:
                    st.session_state.steady_states = st.session_state.experiment_plan_tmp
                if st.session_state.processed_data_tmp is None and st.session_state.steady_states_tmp is None:
                    st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖").write("Please input intermediate result data!")
            st.text("")

    #--------------
    # current chat
    #--------------
    if st.session_state.processed_data is not None:
        if st.session_state.steady_states is None and subphase_type == "Failure definition":
                            st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖").write("Please input steady state data when subphase is 'Failure definition'.")
        else:
            if st.session_state.is_first_run:
                st.session_state.is_first_run = False
                st.rerun()
            with st.chat_message("user"):
                st.write("### Processed Data (dict):")
                st.write(st.session_state.processed_data.dict())
                if subphase_type == "Failure definition":
                    st.write("### Steady States (dict):")
                    st.write(st.session_state.steady_states.dict())
            with st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖"):
                steady_states = st.session_state.steady_states
                processed_data = st.session_state.processed_data
                st.session_state.processed_data = None
                st.session_state.steady_states = None
                work_dir = f"{WORK_DIR}/hypothesis_{get_timestamp()}"
                os.makedirs(work_dir, exist_ok=True)
                if subphase_type == "Failure definition":
                    faults = st.session_state.fault_agent.define_faults(
                        data=processed_data,
                        steady_states=steady_states,
                        namespace=NAMESPACE
                    )
                    save_json(f"{work_dir}/faults.json", faults.dict())
                    save_json(f"{work_dir}/hypothesis.json", Hypothesis(steady_states=steady_states, faults=faults).dict())
                else:
                    steady_states = st.session_state.steady_state_agent.define_steady_states(
                        data=processed_data,
                        namespace=NAMESPACE,
                        work_dir=work_dir
                    )
                    save_json(f"{work_dir}/steady_states.json", steady_states.dict())
    st.session_state.count += 1

if __name__ == "__main__":
    main()
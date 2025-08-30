import os
import time
import yaml
import zipfile

import streamlit as st
import redis
from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx
from streamlit_extras.bottom_container import bottom
from langchain.schema import HumanMessage

from chaos_hunter.chaos_hunter import ChaosHunter, ChaosHunterInput
from chaos_hunter.ce_tools.ce_tool import CEToolType, CETool
import chaos_hunter.utils.app_utils as app_utils
from chaos_hunter.utils.llms import load_llm
from chaos_hunter.utils.functions import get_timestamp, type_cmd, is_binary, run_command
from chaos_hunter.utils.streamlit import StreamlitDisplayHandler
from chaos_hunter.utils.k8s import remove_all_resources_by_namespace
from chaos_hunter.utils.schemas import File
from chaos_hunter.utils.constants import CHAOSHUNTER_IMAGE_PATH, CHAOSHUNTER_LOGO_PATH, CHAOSHUNTER_ICON, CHAOSHUNTER_IMAGE

# for debug
from langchain.globals import set_verbose
import langchain
langchain.debug = True
set_verbose(True)

WORK_DIR  = "sandbox"
NAMESPACE = "chaos-hunter"
EXAMPLE_DIR = "./examples"

# Ensure we're in the correct working directory
import os
if os.getcwd() != os.path.dirname(os.path.abspath(__file__)):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


REQUEST_URL_INSTRUCTIONS = """
- When using k6 in steady-state definition, always select a request URL from the following options (other requests are invalid):
  1. http://front-end.sock-shop.svc.cluster.local/
  2. http://front-end.sock-shop.svc.cluster.local/catalogue?size=10
  3. http://front-end.sock-shop.svc.cluster.local/detail.html?id=<ID>
  Replace <ID> with an available ID: [`03fef6ac-1896-4ce8-bd69-b798f85c6e0b`, `3395a43e-2d88-40de-b95f-e00e1502085b`, `510a0d7e-8e83-4193-b483-e27e09ddc34d`, `808a2de1-1aaa-4c25-a9b9-6612e8f29a38`, `819e1fbf-8b7e-4f6d-811f-693534916a8b`, `837ab141-399e-4c1f-9abc-bace40296bac`, `a0a4f044-b040-410d-8ead-4de0446aec7e`, `d3588630-ad8e-49df-bbd7-3167f7efb246`, `zzz4f044-b040-410d-8ead-4de0446aec7e`]
  4. http://front-end.sock-shop.svc.cluster.local/category/
  5. http://front-end.sock-shop.svc.cluster.local/category?tags=<TAG>
  Replace <TAG> with an available tag: [`magic`, `action`, `blue`, `brown`, `black`, `sport`, `formal`, `red`, `green`, `skin`, `geek`]
  6. http://front-end.sock-shop.svc.cluster.local/basket.html"""


def init_chashunter(
    model_name: str = "openai/gpt-4o",
    temperature: float = 0.0,
    port: int = 8000,
    seed: int = 42,
    github_token: str = None,
    github_base_url: str = "https://models.github.ai/inference"
) -> None:
    # TODO: comment out when publish this code
    # if st.session_state.openai_key == "":
    #     return
    # os.environ['OPENAI_API_KEY'] = st.session_state.openai_key
    
    # Set AWS credentials for Bedrock models
    aws_region = None
    if model_name.startswith("bedrock"):
        if hasattr(st.session_state, 'aws_access_key_id') and st.session_state.aws_access_key_id:
            os.environ['AWS_ACCESS_KEY_ID'] = st.session_state.aws_access_key_id
        if hasattr(st.session_state, 'aws_secret_access_key') and st.session_state.aws_secret_access_key:
            os.environ['AWS_SECRET_ACCESS_KEY'] = st.session_state.aws_secret_access_key
        if hasattr(st.session_state, 'aws_session_token') and st.session_state.aws_session_token:
            os.environ['AWS_SESSION_TOKEN'] = st.session_state.aws_session_token
        if hasattr(st.session_state, 'aws_region') and st.session_state.aws_region:
            os.environ['AWS_DEFAULT_REGION'] = st.session_state.aws_region
            aws_region = st.session_state.aws_region
    
    llm = load_llm(
        model_name=model_name, 
        temperature=temperature,
        port=port,
        seed=seed,
        aws_region=aws_region,
        github_token=st.session_state.github_token if model_name.startswith("github/") else None,
        github_base_url=st.session_state.github_base_url if model_name.startswith("github/") else None
    )
    st.session_state.chashunter = ChaosHunter(
        llm=llm,
        ce_tool=CETool.init(CEToolType.chaosmesh),
        work_dir=WORK_DIR,
        namespace=NAMESPACE
    )
    st.session_state.model_name = model_name
    st.session_state.seed = seed


def main():
    #---------------------------
    # initialize session states
    #---------------------------
    if "state_list" not in st.session_state:
        st.session_state.state_list = {}
    if "session_id" not in st.session_state:
        session_ctx = get_script_run_ctx()
        st.session_state.session_id = session_ctx.session_id
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "count" not in st.session_state:
        st.session_state.count = 0
    if "is_first_run" not in st.session_state:
        st.session_state.is_first_run = True
    if "input" not in st.session_state:
        st.session_state.input = None
    if "submit" not in st.session_state:
        st.session_state.submit = False
    if "model_name" not in st.session_state:
        st.session_state.model_name = "openai/gpt-4o-2024-08-06"
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = st.session_state.model_name
    if "seed" not in st.session_state:
        st.session_state.seed = 42
    if "temperature" not in st.session_state:
        st.session_state.temperature = 0.0
    if "github_token" not in st.session_state:
        st.session_state.github_token = ""
    if "github_base_url" not in st.session_state:
        st.session_state.github_base_url = "https://models.github.ai/inference"
    if "github_token" not in st.session_state:
        st.session_state.github_token = ""
    if "github_base_url" not in st.session_state:
        st.session_state.github_base_url = "https://models.github.ai/inference"

    #--------------
    # CSS settings
    #--------------
    st.set_page_config(
        page_title="ChaosHunter",
        page_icon=CHAOSHUNTER_IMAGE,
        # layout="wide"
    )
    app_utils.apply_hide_st_style()
    app_utils.apply_hide_height0_components()
    app_utils.apply_centerize_components_vertically()
    app_utils.apply_remove_sidebar_topspace()
    app_utils.apply_enable_auto_scroll()
    
    #-----------------
    # helpers & phase overview
    #-----------------
    def _summarize_llm_logs(logs):
        try:
            items = logs or []
            names = []
            in_tok = out_tok = tot_tok = 0
            for it in items:
                obj = it
                if hasattr(it, 'dict'):
                    obj = it.dict()
                names.append(obj.get('name', ''))
                tu = obj.get('token_usage', {})
                in_tok += int(tu.get('input_tokens', 0) or 0)
                out_tok += int(tu.get('output_tokens', 0) or 0)
                tot_tok += int(tu.get('total_tokens', 0) or 0)
            return names, in_tok, out_tok, tot_tok
        except Exception:
            return [], 0, 0, 0

    def _render_llm_logs(logs):
        names, in_tok, out_tok, tot_tok = _summarize_llm_logs(logs)
        cols = st.columns(3)
        cols[0].metric("LLMs", f"{len(set([n for n in names if n]))}")
        cols[1].metric("In/Out (k)", f"{in_tok/1000:.2f} / {out_tok/1000:.2f}")
        cols[2].metric("Total (k)", f"{tot_tok/1000:.2f}")
        with st.expander("Detailed logs"):
            for idx, it in enumerate(logs or []):
                obj = it
                if hasattr(it, 'dict'):
                    obj = it.dict()
                st.write(f"[{idx+1}] {obj.get('name','')} ")
                st.code("\n".join([str(x) for x in obj.get('message_history', [])])[:4000])

    def render_phase_tabs(output):
        if not output:
            return
        tabs = st.tabs(["Preprocess","Hypothesis","Experiment","Analysis","Improvement","Postprocess"])
        with tabs[0]:
            with st.container(border=True):
                st.write("Cluster & Inputs")
                st.metric("Elapsed", f"{output.run_time.get('preprocess', 0):.1f}s")
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("preprocess", []))
        with tabs[1]:
            with st.container(border=True):
                st.write("Steady States & Failure Assumptions")
                st.metric("Elapsed", f"{output.run_time.get('hypothesis', 0):.1f}s")
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("hypothesis", []))
        with tabs[2]:
            with st.container(border=True):
                st.write("Plan & Execution")
                st.metric("Plan time", f"{output.run_time.get('experiment_plan', 0):.1f}s")
                if isinstance(output.run_time.get('experiment_execution', []), list) and len(output.run_time.get('experiment_execution', []))>0:
                    st.metric("Exec time (last)", f"{output.run_time['experiment_execution'][-1]:.1f}s")
                # pass/fail metrics from last result
                try:
                    if hasattr(output, 'ce_cycle') and len(output.ce_cycle.result_history) > 0:
                        last_res = output.ce_cycle.result_history[-1]
                        pod_statuses = getattr(last_res, 'pod_statuses', {}) or {}
                        pass_count = sum(1 for s in pod_statuses.values() if getattr(s, 'exitcode', 1) == 0)
                        fail_count = sum(1 for s in pod_statuses.values() if getattr(s, 'exitcode', 1) != 0)
                        app_utils.render_badges([
                            ("Passed", str(pass_count), "success"),
                            ("Failed", str(fail_count), "danger"),
                        ])
                        try:
                            import pandas as _pd
                            st.bar_chart(_pd.DataFrame({"count": [pass_count, fail_count]}, index=["passed","failed"]))
                        except Exception:
                            pass
                except Exception:
                    pass
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("experiment_plan", []))
            # quick copy commands
            app_utils.render_copy_button("Copy kubectl context cmd", f"kubectl config use-context {st.session_state.get('cluster_name','kind-chaos-hunter-cluster')}", key="kubectl_ctx")
            app_utils.render_copy_button("Copy skaffold run", f"skaffold run --kube-context {st.session_state.get('cluster_name','kind-chaos-hunter-cluster')} -l project=chaos-hunter", key="skaffold_run")
        with tabs[3]:
            with st.container(border=True):
                st.write("Findings")
                if isinstance(output.run_time.get('analysis', []), list) and len(output.run_time.get('analysis', []))>0:
                    st.metric("Elapsed (last)", f"{output.run_time['analysis'][-1]:.1f}s")
                # failed details table
                try:
                    if hasattr(output, 'ce_cycle') and len(output.ce_cycle.result_history) > 0:
                        last_res = output.ce_cycle.result_history[-1]
                        pod_statuses = getattr(last_res, 'pod_statuses', {}) or {}
                        rows = []
                        for name, s in pod_statuses.items():
                            exitcode = getattr(s, 'exitcode', None)
                            if exitcode is None:
                                exitcode = getattr(s, 'exitcode', 1)
                            if exitcode != 0:
                                snippet = getattr(s, 'logs', '')[:300]
                                rows.append({"workflow": name, "exitcode": exitcode, "log": snippet})
                        if rows:
                            app_utils.render_badges([(f"Failed workflows", str(len(rows)), "danger")])
                            try:
                                import pandas as _pd
                                st.dataframe(_pd.DataFrame(rows))
                            except Exception:
                                for r in rows:
                                    st.write(r)
                except Exception:
                    pass
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("analysis", []))
        with tabs[4]:
            with st.container(border=True):
                st.write("Proposed Changes")
                if isinstance(output.run_time.get('improvement', []), list) and len(output.run_time.get('improvement', []))>0:
                    st.metric("Elapsed (last)", f"{output.run_time['improvement'][-1]:.1f}s")
                # Inline YAML editor (safe apply/rollback)
                try:
                    if hasattr(output, 'ce_cycle') and len(output.ce_cycle.reconfig_history) > 0:
                        last_reconfig = output.ce_cycle.reconfig_history[-1]
                        mods = last_reconfig.mod_k8s_yamls.get('modified_k8s_yamls', [])
                        if mods:
                            st.write("Edit YAML before apply:")
                            # select file to edit
                            fnames = [m.get('fname') for m in mods if m.get('mod_type') in ('create','replace')]
                            if fnames:
                                sel = st.selectbox("File", fnames, key="inline_yaml_fname")
                                sel_mod = next((m for m in mods if m.get('fname') == sel), None)
                                original = sel_mod.get('code', '') if sel_mod else ''
                                edited = st.text_area("YAML", value=original, height=240, key=f"inline_yaml_{sel}")
                                # validation status
                                is_valid = True
                                err_msg = ""
                                try:
                                    yaml.safe_load(edited)
                                except Exception as _e:
                                    is_valid = False
                                    err_msg = str(_e)
                                if is_valid:
                                    st.success("YAML is valid")
                                else:
                                    st.error(f"YAML invalid: {err_msg}")
                                col_apply, col_rollback, col_redeploy = st.columns(3)
                                with col_apply:
                                    if st.button("Apply changes", key=f"apply_{sel}"):
                                        if not is_valid:
                                            st.error("Fix YAML errors before applying.")
                                        else:
                                            def _confirm_apply(fname: str, before: str, after: str):
                                                app_utils.render_yaml_diff(before, after, title=fname)
                                                c1, c2 = st.columns(2)
                                                with c1:
                                                    if st.button("Confirm apply", key=f"confirm_apply_{fname}"):
                                                        try:
                                                            from chaos_hunter.utils.functions import write_file
                                                            mod_dir_ = output.output_dir or output.work_dir
                                                            dest_ = os.path.join(mod_dir_, fname)
                                                            os.makedirs(os.path.dirname(dest_), exist_ok=True)
                                                            write_file(dest_, after)
                                                            st.toast(f"Applied {fname}", icon="✅")
                                                        except Exception as e:
                                                            st.error(f"Failed to apply: {e}")
                                                with c2:
                                                    st.button("Cancel", key=f"cancel_apply_{fname}")
                                            dialog = st.experimental_dialog("Confirm changes")(_confirm_apply)
                                            dialog(sel, original, edited)
                                with col_rollback:
                                    if st.button("Rollback to original", key=f"rollback_{sel}"):
                                        try:
                                            from chaos_hunter.utils.functions import write_file
                                            mod_dir = output.output_dir or output.work_dir
                                            dest = os.path.join(mod_dir, sel)
                                            os.makedirs(os.path.dirname(dest), exist_ok=True)
                                            write_file(dest, original)
                                            st.toast(f"Rolled back {sel}", icon="↩️")
                                        except Exception as e:
                                            st.error(f"Failed to rollback: {e}")
                                with col_redeploy:
                                    if st.button("Apply & Redeploy", key=f"apply_redeploy_{sel}"):
                                        if not is_valid:
                                            st.error("Fix YAML errors before applying.")
                                        else:
                                            def _confirm_apply_redeploy(fname: str, before: str, after: str):
                                                app_utils.render_yaml_diff(before, after, title=fname)
                                                c1, c2 = st.columns(2)
                                                with c1:
                                                    if st.button("Confirm apply & redeploy", key=f"confirm_apply_redeploy_{fname}"):
                                                        try:
                                                            from chaos_hunter.utils.functions import write_file
                                                            mod_dir_ = output.output_dir or output.work_dir
                                                            dest_ = os.path.join(mod_dir_, fname)
                                                            os.makedirs(os.path.dirname(dest_), exist_ok=True)
                                                            write_file(dest_, after)
                                                            skaffold_path = os.path.join(mod_dir_, os.path.basename(output.ce_cycle.processed_data.input.skaffold_yaml.path)) if hasattr(output.ce_cycle, 'processed_data') else None
                                                            if not skaffold_path:
                                                                skaffold_path = os.path.join(mod_dir_, 'skaffold.yaml')
                                                            run_command(
                                                                cmd=f"skaffold run --kube-context {st.session_state.get('cluster_name','kind-chaos-hunter-cluster')} -l project=chaos-hunter",
                                                                cwd=os.path.dirname(skaffold_path),
                                                                display_handler=StreamlitDisplayHandler(header="Apply & Redeploy")
                                                            )
                                                            st.toast("Redeployed", icon="🚀")
                                                        except Exception as e:
                                                            st.error(f"Redeploy failed: {e}")
                                                with c2:
                                                    st.button("Cancel", key=f"cancel_apply_redeploy_{fname}")
                                            dialog2 = st.experimental_dialog("Confirm changes & redeploy")(_confirm_apply_redeploy)
                                            dialog2(sel, original, edited)
                except Exception:
                    pass
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("improvement", []))
        with tabs[5]:
            with st.container(border=True):
                st.write("Summary")
                st.metric("Total time", f"{output.run_time.get('cycle', 0):.1f}s")
                # artifacts
                output_dir = output.work_dir
                import os as _os
                _os.makedirs("./temp", exist_ok=True)
                zip_path = f"./temp/{_os.path.basename(output_dir)}.zip"
                st.write(type_cmd(f"zip -r {zip_path} {output_dir}"))
                with st.columns(3)[1]:
                    with open(zip_path, "rb") as fp:
                        st.download_button(
                            label="Download output (.zip)",
                            data=fp,
                            file_name=f"{_os.path.basename(zip_path)}",
                            mime=f"output/zip"
                        )
                # actions
                if st.button("Re-run experiment") and st.session_state.get("last_input") is not None:
                    st.session_state.input = st.session_state.last_input
                    st.session_state.submit = True
                    st.rerun()
            with st.expander("Logs"):
                _render_llm_logs(output.logs.get("summary", []))

        # overall durations chart
        try:
            import pandas as _pd
            phases = []
            values = []
            rt = output.run_time or {}
            for key in ["preprocess","hypothesis","experiment_plan","analysis","improvement","summary","cycle"]:
                val = rt.get(key)
                if isinstance(val, list):
                    val = val[-1] if val else 0
                if val is None:
                    val = 0
                phases.append(key)
                values.append(float(val))
            st.write("### Phase durations")
            st.bar_chart(_pd.DataFrame({"seconds": values}, index=phases))
        except Exception:
            pass

    #---------
    # sidebar
    #---------
    # Only show logo if the image file exists
    if os.path.exists(CHAOSHUNTER_LOGO_PATH):
        st.logo(CHAOSHUNTER_LOGO_PATH)
    else:
        st.title("ChaosHunter")
    dark = st.toggle("Dark mode", value=False)
    app_utils.apply_dark_mode(dark)
    with st.sidebar:
        #----------
        # settings
        #----------
        with st.container(border=True):
            #-----------------
            # model selection
            #-----------------
            
            # Import Bedrock utilities
            from chaos_hunter.utils.bedrock_utils import (
                get_available_bedrock_models, 
                PREDEFINED_BEDROCK_MODELS,
                get_model_display_name,
                validate_bedrock_credentials
            )
            
            # Base model options
            base_models = [
                "openai/gpt-4o-2024-08-06",
                "google/gemini-2.5-pro",
                "google/gemini-2.0-flash-lite",
                "anthropic/claude-3-5-sonnet-20241022",
                "github/gpt-5",
            ]
            
            # Model selection
            st.session_state.selected_model = st.selectbox(
                "Select Model",
                options=base_models,
                index=base_models.index(st.session_state.model_name)
            )
            
            # GitHub settings if GitHub model is selected
            if st.session_state.selected_model.startswith("github/"):
                st.write("### GitHub Settings")
                st.session_state.github_token = st.text_input(
                    "GitHub Token",
                    value=st.session_state.github_token,
                    type="password",
                    help="Enter your GitHub token for model access"
                )
                st.session_state.github_base_url = st.text_input(
                    "GitHub Base URL",
                    value=st.session_state.github_base_url,
                    help="The base URL for GitHub model inference"
                )
            
            # Get available Bedrock models if credentials are provided
            available_bedrock_models = []
            if (hasattr(st.session_state, 'aws_access_key_id') and st.session_state.aws_access_key_id and
                hasattr(st.session_state, 'aws_secret_access_key') and st.session_state.aws_secret_access_key):
                
                # Set environment variables temporarily for validation
                original_env = os.environ.copy()
                os.environ['AWS_ACCESS_KEY_ID'] = st.session_state.aws_access_key_id
                os.environ['AWS_SECRET_ACCESS_KEY'] = st.session_state.aws_secret_access_key
                if hasattr(st.session_state, 'aws_session_token') and st.session_state.aws_session_token:
                    os.environ['AWS_SESSION_TOKEN'] = st.session_state.aws_session_token
                if hasattr(st.session_state, 'aws_region') and st.session_state.aws_region:
                    os.environ['AWS_DEFAULT_REGION'] = st.session_state.aws_region
                
                try:
                    region = getattr(st.session_state, 'aws_region', 'us-east-1')
                    if validate_bedrock_credentials(region):
                        available_bedrock_models = get_available_bedrock_models(region)
                        # Convert to bedrock/ prefixed format
                        available_bedrock_models = [f"bedrock/{model['model_id']}" for model in available_bedrock_models]
                except Exception as e:
                    st.warning(f"Could not fetch available Bedrock models: {e}")
                finally:
                    # Restore original environment
                    os.environ.clear()
                    os.environ.update(original_env)
            
            # Use available models if found, otherwise fall back to predefined
            if available_bedrock_models:
                bedrock_models = available_bedrock_models
                st.success(f"✅ Found {len(available_bedrock_models)} available Bedrock models")
            else:
                bedrock_models = PREDEFINED_BEDROCK_MODELS
                st.info("ℹ️ Using predefined Bedrock models. Enter AWS credentials to see available models.")
            
            # Combine all models
            all_models = base_models + bedrock_models
            
            # Create display names for selectbox
            model_display_names = []
            for model in all_models:
                if model.startswith("bedrock/"):
                    display_name = get_model_display_name(model)
                    model_display_names.append(f"🤖 {display_name}")
                elif model.startswith("openai/"):
                    model_display_names.append(f"🔵 {model.split('/')[1]}")
                elif model.startswith("google/"):
                    model_display_names.append(f"🟢 {model.split('/')[1]}")
                elif model.startswith("anthropic/"):
                    model_display_names.append(f"🟣 {model.split('/')[1]}")
                else:
                    model_display_names.append(model)
            
            # Model selection with display names
            selected_display = st.selectbox(
                "Model", 
                model_display_names,
                index=0
            )
            
            # Map back to actual model name
            model_name = all_models[model_display_names.index(selected_display)]
            
            # Add custom model option
            if model_name.startswith("bedrock/"):
                st.write("---")
                st.write("**Add Custom Bedrock Model**")
                custom_model_id = st.text_input(
                    "Custom Model ID",
                    placeholder="e.g., anthropic.claude-3-5-sonnet-20241022-v1:0",
                    help="Enter a custom Bedrock model ID (without 'bedrock/' prefix)"
                )
                if custom_model_id:
                    if not custom_model_id.startswith("bedrock/"):
                        custom_model_id = f"bedrock/{custom_model_id}"
                    if custom_model_id not in all_models:
                        model_name = custom_model_id
                        st.success(f"✅ Using custom model: {custom_model_id}")
                    else:
                        st.info("This model is already in the list.")
            if model_name.startswith("openai"):
                st.text_input(
                    label="API keys",
                    key="openai_key",
                    placeholder="OpenAI API key",
                    type="password"
                )
            elif model_name.startswith("bedrock"):
                st.text_input(
                    label="AWS Access Key ID",
                    key="aws_access_key_id",
                    placeholder="AWS Access Key ID",
                    type="password"
                )
                st.text_input(
                    label="AWS Secret Access Key",
                    key="aws_secret_access_key",
                    placeholder="AWS Secret Access Key",
                    type="password"
                )
                st.text_input(
                    label="AWS Session Token (optional)",
                    key="aws_session_token",
                    placeholder="AWS Session Token (for temporary credentials)",
                    type="password"
                )
                st.text_input(
                    label="AWS Region",
                    key="aws_region",
                    placeholder="us-east-1",
                    value="us-east-1"
                )
            else:
                st.text_input(
                    label="Token",
                    key="hf_token",
                    placeholder="Hugging Face token",
                    type="password"
                )
            
            #-------------------
            # cluster selection
            #-------------------
            avail_cluster_list = app_utils.get_available_clusters()
            FULL_CAP_MSG = "No clusters available right now. Please wait until a cluster becomes available."
            if len(avail_cluster_list) == 0:
                avail_cluster_list = (FULL_CAP_MSG,)
            cluster_name = st.selectbox(
                "Cluster selection",
                avail_cluster_list,
                key="cluster_name"
            )
            if cluster_name == FULL_CAP_MSG:
                st.info("No free clusters detected. Check Redis key 'cluster_usage' and kubectl contexts. See terminal logs for details.")
                st.button(
                    "Release my cluster reservation",
                    key="release_cluster_reservation",
                    on_click=app_utils.release_my_reserved_cluster
                )
            app_utils.monitor_session(st.session_state.session_id)
            st.button(
                "Clean the cluster",
                key="clean_k8s",
                on_click=remove_all_resources_by_namespace,
                args=(cluster_name, NAMESPACE, ),
                disabled=(cluster_name == FULL_CAP_MSG)
            )

            #--------------------
            # parameter settings
            #--------------------
            clean_cluster_before_run = st.checkbox("Clean the cluster before run", value=True)
            clean_cluster_after_run = st.checkbox("Clean the cluster after run", value=True)
            is_new_deployment = st.checkbox("New deployment", value=True)
            seed = st.number_input("Seed for LLMs (GPTs only)", 42)
            temperature = st.number_input("Temperature for LLMs", 0.0)
            max_num_steadystates = st.number_input("Max. number of steady states", 3)
            max_retries = st.number_input("Max retries", 3)


        #---------------------------
        # usage: tokens and billing
        #---------------------------
        with st.container(border=True):
            st.write("Token usage:")
            colA, colB = st.columns(2)
            with colA:
                st.session_state.usage = st.empty()
                st.session_state.usage.write(f"Total billing: $0  \nTotal tokens: 0  \nInput tokens: 0  \nOuput tokens: 0")
            with colB:
                total_billing = 0.0
                total_tokens = 0
                input_tokens = 0
                output_tokens = 0
                if "total_tokens" in st.session_state:
                    total_tokens = st.session_state.total_tokens
                if "input_tokens" in st.session_state:
                    input_tokens = st.session_state.input_tokens
                if "output_tokens" in st.session_state:
                    output_tokens = st.session_state.output_tokens
                # billing is computed in display_usage and written into usage text; keep metric display simple
                st.metric("Tokens (k)", f"{total_tokens/1000:.2f}")
                st.metric("In/Out (k)", f"{input_tokens/1000:.2f} / {output_tokens/1000:.2f}")
        #-----------------
        # command history
        #-----------------
        if not st.session_state.is_first_run:
            st.write("Command history")

    #------------------------
    # initialize chaos eater
    #------------------------
    # initialization
    # Check if we need to reinitialize (model changed, seed changed, temperature changed, or AWS credentials changed for Bedrock)
    aws_credentials_changed = False
    selected_model = st.session_state.selected_model
    if selected_model.startswith("bedrock"):
        current_aws_region = getattr(st.session_state, 'aws_region', None)
        stored_aws_region = getattr(st.session_state, 'stored_aws_region', None)
        current_aws_session_token = getattr(st.session_state, 'aws_session_token', None)
        stored_aws_session_token = getattr(st.session_state, 'stored_aws_session_token', None)
        aws_credentials_changed = (current_aws_region != stored_aws_region or 
                                 current_aws_session_token != stored_aws_session_token)
    
    if ("chashunter" not in st.session_state or 
        selected_model != st.session_state.model_name or 
        seed != st.session_state.seed or 
        temperature != st.session_state.temperature or
        aws_credentials_changed):
        init_chashunter(
            model_name=selected_model,
            seed=seed,
            temperature=temperature,
            github_token=st.session_state.github_token if selected_model.startswith("github/") else None,
            github_base_url=st.session_state.github_base_url if selected_model.startswith("github/") else None
        )
        # Store the current AWS credentials to detect changes
        if model_name.startswith("bedrock"):
            st.session_state.stored_aws_region = getattr(st.session_state, 'aws_region', None)
            st.session_state.stored_aws_session_token = getattr(st.session_state, 'aws_session_token', None)

    # greeding 
    if len(st.session_state.chat_history) == 0 and st.session_state.is_first_run:
        app_utils.add_chashunter_icon(CHAOSHUNTER_IMAGE_PATH)
        if st.session_state.count == 0: # streaming
            greeding = "Let's dive into Chaos together :)"
            elem = st.empty()
            words = ""
            for word in list(greeding):
                if word == "C":
                    words += "<font color='#7fff00'>" + word
                elif word == "s":
                    words += word + "</font>"
                else:
                    words += word
                elem.markdown(f'<center> <h3> {words} </h3> </center>', unsafe_allow_html=True)
                time.sleep(0.06)
        else:
            greeding = "Let's dive into <font color='#7fff00'>Chaos</font> together :)"
            st.markdown(f'<center> <h3> {greeding} </h3> </center>', unsafe_allow_html=True)

    #----------
    # examples
    #----------
    def submit_example(number: int, example_dir: str, instructions: str) -> None:
        decorated_func = st.experimental_dialog(f"Example input #{number}")(submit_example_internal)
        decorated_func(example_dir, instructions)

    def submit_example_internal(example_dir: str, instructions: str) -> None:
        # load the project
        skaffold_yaml = None
        project_files_tmp = []
        for root, _, files in os.walk(example_dir):
            for entry in files:
                fpath = os.path.join(root, entry)
                if os.path.isfile(fpath):
                    with open(fpath, "rb") as f:
                        file_content = f.read()
                    if is_binary(file_content):
                        content = file_content
                    else:
                        content = file_content.decode('utf-8')
                    if os.path.basename(fpath) == "skaffold.yaml":
                        skaffold_yaml = File(
                            path=fpath,
                            content=content,
                            work_dir=EXAMPLE_DIR,
                            fname=fpath.removeprefix(f"{EXAMPLE_DIR}/")
                        )
                    else:
                        project_files_tmp.append(File(
                                path=fpath,
                                content=content,
                                work_dir=EXAMPLE_DIR,
                                fname=fpath.removeprefix(f"{EXAMPLE_DIR}/")
                        ))
        input_tmp = ChaosHunterInput(
            skaffold_yaml=skaffold_yaml,
            files=project_files_tmp,
            ce_instructions=instructions
        )
        skaffold_yaml_dir = os.path.dirname(skaffold_yaml.path)
        k8s_yamls_tmp = []
        for k8s_yaml_fname in yaml.safe_load(skaffold_yaml.content)["manifests"]["rawYaml"]:
            for file in project_files_tmp:
                if f"{skaffold_yaml_dir}/{k8s_yaml_fname}" == file.path:
                    k8s_yamls_tmp.append(File(
                        path=file.path,
                        content=file.content,
                        fname=file.fname
                    ))
        # display the example
        st.write("### Input K8s manifest(s):")
        for k8s_yaml in k8s_yamls_tmp:
            st.write(f"```{k8s_yaml.fname}```")
            st.code(k8s_yaml.content)
        st.write("### Instructions:")
        st.write(instructions)
        with st.columns(3)[1]:
            # submit the example
            if st.button("Try this one"):
                st.session_state.input = input_tmp
                st.session_state.submit = True
                st.rerun()

    if st.session_state.is_first_run:
        app_utils.apply_remove_example_bottomspace(px=0)
        st.session_state.bottom_container = bottom()
        with st.session_state.bottom_container:
            #----------
            # examples
            #----------
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("example#1:  \nNginx w/ detailed CE instructions", key="example1", use_container_width=True):
                    submit_example(
                        number=1,
                        example_dir=f"{EXAMPLE_DIR}/nginx",
                        instructions="- The Chaos-Engineering experiment must be completed within 1 minute.\n- List ONLY one steady state about Pod Count.\n- Conduct pod-kill"
                    )
            with col2:
                if st.button("example#2:  \nNginx w/ limited experiment duration", key="example2", use_container_width=True):
                    submit_example(
                        number=2,
                        example_dir=f"{EXAMPLE_DIR}/nginx",
                        instructions="The Chaos-Engineering experiment must be completed within 1 minute."
                    )
            with col3:
                if st.button("example#3:  \nSock shop w/ limited experiment duration", key="example3", use_container_width=True):
                    submit_example(
                        number=3,
                        example_dir=f"{EXAMPLE_DIR}/sock-shop-2",
                        instructions=f"- The Chaos-Engineering experiment must be completed within 1 minute.\n{REQUEST_URL_INSTRUCTIONS}"
                    )
            #----------------
            # file uploading
            #----------------
            upload_col, submit_col = st.columns([10, 2], vertical_alignment="bottom")
            with upload_col:
                file = st.file_uploader(
                    "upload your project",
                    type="zip",
                    accept_multiple_files=False,
                    label_visibility="hidden"
                )
                if file is not None:
                    project_files_tmp = []
                    with zipfile.ZipFile(file, "r") as z:
                        for file_info in z.infolist():
                            # only process files, skip directories
                            if not file_info.is_dir():
                                with z.open(file_info) as file:
                                    file_content = file.read()
                                    if is_binary(file_content):
                                        content = file_content
                                    else:
                                        content = file_content.decode('utf-8')
                                    fpath = file_info.filename
                                    if os.path.basename(fpath) == "skaffold.yaml":
                                        skaffold_yaml = File(
                                            path=fpath,
                                            content=content,
                                            work_dir=EXAMPLE_DIR,
                                            fname=fpath.removeprefix(EXAMPLE_DIR)
                                        )
                                    else:
                                        project_files_tmp.append(File(
                                                path=fpath,
                                                content=content,
                                                work_dir=EXAMPLE_DIR,
                                                fname=fpath.removeprefix(EXAMPLE_DIR)
                                        ))
                    st.session_state.input = ChaosHunterInput(
                        skaffold_yaml=skaffold_yaml,
                        files=project_files_tmp
                    )
            with submit_col:
                st.text("")
                if st.button("Submit w/o instructions", key="submit_"):
                    if st.session_state.input != None:
                        st.session_state.input.ce_instructions = ""
                        st.session_state.submit = True
                        st.rerun()
                st.text("")
    else:
        app_utils.apply_remove_example_bottomspace()

    #--------------
    # right-rail live logs + phase tabs (if last output exists)
    #--------------
    rail, main = st.columns([1, 4], vertical_alignment="top")
    with rail:
        st.write("Live logs")
        st.session_state.live_log_container = st.empty()
    with main:
        # Show timeline at the top of main area
        if st.session_state.get("last_output") is not None:
            # Determine current phase based on output
            current_phase = -1  # idle
            if hasattr(st.session_state.get("last_output"), 'ce_cycle'):
                ce_cycle = st.session_state.get("last_output").ce_cycle
                if hasattr(ce_cycle, 'summary') and ce_cycle.summary:
                    current_phase = 5  # completed
                elif hasattr(ce_cycle, 'reconfig_history') and len(ce_cycle.reconfig_history) > 0:
                    current_phase = 4  # improvement phase
                elif hasattr(ce_cycle, 'analysis_history') and len(ce_cycle.analysis_history) > 0:
                    current_phase = 3  # analysis phase
                elif hasattr(ce_cycle, 'result_history') and len(ce_cycle.result_history) > 0:
                    current_phase = 2  # experiment phase
                elif hasattr(ce_cycle, 'hypothesis') and ce_cycle.hypothesis:
                    current_phase = 1  # hypothesis phase
                elif hasattr(ce_cycle, 'processed_data') and ce_cycle.processed_data:
                    current_phase = 0  # preprocess phase
            
            app_utils.render_phase_timeline(current_phase)
            render_phase_tabs(st.session_state.get("last_output"))
        else:
            # skeleton loaders for initial empty state
            ph1, ph2 = st.columns(2)
            with ph1:
                st.write("### Preparing...")
                st.progress(10)
            with ph2:
                st.write("### Waiting for input...")
                st.progress(0)

    #--------------
    # current chat
    #--------------
    if (prompt := st.chat_input(placeholder="Input instructions for your Chaos Engineering", key="chat_input")) or st.session_state.submit:        
        if "chashunter" in st.session_state and cluster_name != FULL_CAP_MSG:
            if st.session_state.input:
                if st.session_state.is_first_run:
                    st.session_state.is_first_run = False
                    if prompt:
                        st.session_state.input.ce_instructions = prompt
                        st.session_state.submit = True
                    st.rerun()
                #--------------------
                # TODO: chat history
                #--------------------
                # st.session_state.chat_history.append(HumanMessage(content=st.session_state.k8s_yaml))
                # st.session_state.chat_history.append(HumanMessage(content=prompt))
                input = st.session_state.input
                if prompt:
                    input.ce_instructions = prompt
                st.session_state.input = None
                st.session_state.submit = False
                #-------------
                # user inputs
                #-------------
                with st.chat_message("user"):
                    st.write("##### Your instructions for Chaos Engineering:")
                    st.write(input.ce_instructions)
                #---------------------
                # chashunter response
                #---------------------
                # set the currrent cluster
                if len(avail_cluster_list) > 0 and avail_cluster_list[0] != FULL_CAP_MSG:
                    r = redis.Redis(host='localhost', port=6379, db=0)
                    r.hset("cluster_usage", st.session_state.session_id, cluster_name)
                with st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖"):
                    output = st.session_state.chashunter.run_ce_cycle(
                        input=input,
                        work_dir=f"{WORK_DIR}/cycle_{get_timestamp()}",
                        kube_context=cluster_name,
                        is_new_deployment=is_new_deployment,
                        clean_cluster_before_run=clean_cluster_before_run,
                        clean_cluster_after_run=clean_cluster_after_run,
                        max_num_steadystates=max_num_steadystates,
                        max_retries=max_retries
                    )
                    # store for tabs
                    st.session_state.last_output = output
                    st.session_state.last_input = input
                    # download output
                    output_dir = output.work_dir
                    os.makedirs("./temp", exist_ok=True) 
                    zip_path = f"./temp/{os.path.basename(output_dir)}.zip"
                    print(type_cmd(f"zip -r {zip_path} {output_dir}"))
                    with st.columns(3)[1]:
                        with open(zip_path, "rb") as fp:
                            btn = st.download_button(
                                label="Download output (.zip)",
                                data=fp,
                                file_name=f"{os.path.basename(zip_path)}",
                                mime=f"output/zip"
                            )
                    # st.session_state.chat_history.append(AIMessage(content=response["response"]))
            else:
                print(st.session_state.k8s_yamls)
                st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖").write("Please input your k8s mainfests!")
        else:
            if cluster_name == FULL_CAP_MSG:
                st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖").write(FULL_CAP_MSG)
            else:
                st.chat_message("assistant", avatar=CHAOSHUNTER_ICON if CHAOSHUNTER_ICON is not None else "🤖").write("Please set your API key!")
                st.session_state.chat_history.append(HumanMessage(content="test"))

    st.session_state.count += 1

if __name__ == "__main__":
    main()
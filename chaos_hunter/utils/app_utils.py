from typing import Tuple

import redis
import streamlit as st
import streamlit.components.v1 as components

from .functions import type_cmd


#----------------
# util functions
#----------------
def apply_html(html: str, **kwargs) -> None:
    st.markdown(html, unsafe_allow_html=True, **kwargs)


# ref: https://discuss.streamlit.io/t/st-logo-image-size/71085/3
REMOVE_SIDEBAR_TOPSPACE = """\
<style>
    div[data-testid="stSidebarHeader"] > img, div[data-testid="collapsedControl"] > img {
        height: 3rem;
        width: auto;
    }
    div[data-testid="stSidebarHeader"], div[data-testid="stSidebarHeader"] > *,
    div[data-testid="collapsedControl"], div[data-testid="collapsedControl"] > * {
        display: flex;
        align-items: center;
    }
    .st-emotion-cache-ocqkz7.e1f1d6gn5 {
        margin-bottom: -30px;
    }
</style>
"""
def apply_remove_sidebar_topspace() -> None:
    apply_html(REMOVE_SIDEBAR_TOPSPACE)


REMOVE_EXAMPLE_BOTTOMSPACE = """\
<style>
    .st-emotion-cache-ocqkz7.e1f1d6gn5 {{
        margin-bottom: {px}px;
    }}
</style>
"""
def apply_remove_example_bottomspace(px: int = 0) -> None:
    apply_html(REMOVE_EXAMPLE_BOTTOMSPACE.format(px=px))


ADD_CHAOS_HUNTER_ICON = """\
<style>
    .relative{
        position: relative;
        width: 140px;
    }
    .frame {
        display: inline-block;
        background-color: transparent;
        border-radius: 50%;
        width: 140px;
        height: 140px;
    }
    .eye {
        display: inline-block;
        position: absolute;
        right: 45.5px;
        bottom: 53.5px;
        background-color: white;
        border-radius: 50%;
        width: 45px;
        height: 45px;
        z-index: 1;
    }
    .mask {
        overflow: hidden;
        position: absolute;
        right: 45.5px;
        bottom: 53.5px;
        border-radius: 50%;
        width: 46px;
        height: 46px;
        z-index: 4;
    }
    .eyelid {
        display: inline-block;
        position: absolute;
        right: 0px;
        bottom: 1px;
        background-color: black;
        border-radius: 50% 50% 0% 0%;
        width: 45px;
        height: 45px;
        z-index: 5;
        animation-name: blink, blink2;
        animation-duration: 5s, 10s;
        animation-timing-function: linear, linear;
        animation-iteration-count: 1, infinite;
        animation-direction: normal, normal;
    }
    .pupil {
        display: inline-block;
        position: absolute;
        right: 14px;
        bottom: 14px;
        background-color: black;
        border-radius: 50%;
        width: 18px;
        height: 18px;
        z-index: 2;
    }
    .pupil_highlight {
        display: inline-block;
        position: absolute;
        right: 17px;
        bottom: 22px;
        background-color: white;
        border-radius: 50%;
        width: 6px;
        height: 6px;
        z-index: 3;
    }
    .chashunter {
        position: absolute;
        right: -2px;
        bottom: 6px;
        z-index: 0;
        animation-name: rotation;
        animation-duration: 30s;
        animation-timing-function: linear;
        animation-iteration-count: infinite;
        animation-direction: normal;
    }
    @keyframes rotation{
        0%{ transform:rotate(0);}
        100%{ transform:rotate(-360deg); }
    }
    @keyframes blink {
        0% { transform: translateY(-100%);} 
        96%{ transform: translateY(-100%);}
        98%{ transform: translateY(0%);}
        100%{ transform: translateY(-100%);}
    }
    @keyframes blink2 {
        0% { transform: translateY(-100%);} 
        96%{ transform: translateY(-100%);}
        98%{ transform: translateY(0%);}
        100%{ transform: translateY(-100%);}
    }
</style>
<div class="stApp stAppEmbeddingId-s6iibfbv121p st-emotion-cache-ffhzg2 erw9t6i1">

<script>
    document.addEventListener('mousemove', function(event) {
        const eyes = document.querySelectorAll('.eye');
        eyes.forEach(eye => {                      
            const rect = eye.getBoundingClientRect();
            const eyeCenterX = rect.left + rect.width / 2;
            const eyeCenterY = rect.top + rect.height / 2;
            const deltaX = event.clientX - eyeCenterX;
            const deltaY = event.clientY - eyeCenterY;
            const angle = Math.atan2(deltaY, deltaX);
            const distance = Math.min(Math.min(rect.width / 4, 20), Math.sqrt(deltaX * deltaX + deltaY * deltaY));
            const pupilX = distance * Math.cos(angle);
            const pupilY = distance * Math.sin(angle);
            const pupil = eye.querySelector('.pupil');
            const pupil_highlight = eye.querySelector('.pupil_highlight');
            pupil.style.transform = `translate(${pupilX}px, ${pupilY}px)`;
            pupil_highlight.style.transform = `translate(${pupilX}px, ${pupilY}px)`;
        });
    });
    document.addEventListener('mouseleave', function(event) {
        const eyes = document.querySelectorAll('.eye');
        eyes.forEach(eye => {                  
            const pupil = eye.querySelector('.pupil');
            const pupil_highlight = eye.querySelector('.pupil_highlight');
            pupil.style.transform = `translate(0px, 0px)`;
            pupil_highlight.style.transform = `translate(0px, 0px)`;
        });
    });
</script>
<center> 
    <div class="relative">
        <span class="eye"> 
            <span class="pupil"></span>
            <span class="pupil_highlight"></span>
        </span>
        <div class="mask">
            <span class="eyelid"></span>
        </div>
        <img src="data:image/png;base64,{chashunter_png}" class="chashunter" alt="ChaosHunter" width="140" height="140"> 
        <span class="frame"> </span>
    </div>
</center>
</div>
"""
import base64
from pathlib import Path
def add_chashunter_icon(icon_path: str) -> None:
    img_bytes = Path(icon_path).read_bytes()
    encoded_img = base64.b64encode(img_bytes).decode()
    components.html(ADD_CHAOS_HUNTER_ICON.replace("{chashunter_png}", f"{encoded_img}"))


# ref: https://discuss.streamlit.io/t/remove-hide-running-man-animation-on-top-of-page/21773/3
HIDE_ST_STYLE = """\
<style>
    div[data-testid="stToolbar"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
    div[data-testid="stDecoration"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
    div[data-testid="stStatusWidget"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }
    #MainMenu {
        visibility: hidden;
        height: 0%;
    }
    header {
        visibility: hidden;
        height: 0%;
    }
    footer {
        visibility: hidden;
        height: 0%;
    }
</style>
"""
def apply_hide_st_style() -> None:
    apply_html(HIDE_ST_STYLE)

# ref: https://github.com/streamlit/streamlit/issues/6605
HIDE_HEIGHT0_COMPONENTS = """\
<style>
    .element-container:has(iframe[height="0"]) {{
        display: none;
    }}
</style>
"""
def apply_hide_height0_components():
    apply_html(HIDE_HEIGHT0_COMPONENTS)

CENTERIZE_COMPONENTS_VERTICALLY = """\
<style>
    [data-testid="stHorizontalBlock"] {
        align-items: center;
    }
</style>
"""
def apply_centerize_components_vertically():
    apply_html(CENTERIZE_COMPONENTS_VERTICALLY)

AUTO_SCROLL = """\
<script>
    const chatContainer = document.querySelector(".stChatContainer");
    let autoScrollEnabled = true;

    if (chatContainer) {
        chatContainer.addEventListener('scroll', () => {
            autoScrollEnabled = chatContainer.scrollTop + chatContainer.clientHeight >= chatContainer.scrollHeight;
        });

        const observer = new MutationObserver(() => {
            if (autoScrollEnabled) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        });

        observer.observe(chatContainer, { childList: true });
    }
</script>
"""
def apply_enable_auto_scroll():
    apply_html(AUTO_SCROLL)


# stand-alone spiner in streamlit
# ref: https://github.com/streamlit/streamlit/issues/6799
# Thank the authors for the excelent hack
class st_spinner:
    def __init__(self, text = "In progress..."):
        self.text = text
        self._spinner = iter(self._start()) # This creates an infinite spinner
        next(self._spinner) #  This starts it
        
    def _start(self):
        with st.spinner(self.text):
            yield 
    
    def end(self, text: str = None): # This ends it
        next(self._spinner, None)
        if text is not None:
            st.write(text)

# ref: https://discuss.streamlit.io/t/detecting-user-exit-browser-tab-closed-session-end/62066
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx
from streamlit.runtime.scriptrunner.script_run_context import get_script_run_ctx
from streamlit.runtime import get_instance
def monitor_session(session_id: str) -> None:
    thread = threading.Timer(interval=2, function=monitor_session, args=(session_id,) )
    add_script_run_ctx(thread)
    ctx = get_script_run_ctx()     
    runtime = get_instance()
    if runtime.is_active_session(session_id=ctx.session_id):
        thread.start()
    else:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.hdel("cluster_usage", session_id)
        return

def get_available_clusters() -> Tuple[str]:
    # get the cluster list
    cluster_str = type_cmd("kubectl config get-contexts | awk 'NR>1 {print $2}'", widget=False)
    cluster_list = tuple(cluster_str.strip().split("\n"))
    # get the available cluster list
    r = redis.Redis(host='localhost', port=6379, db=0)
    cluster_usage = r.hgetall("cluster_usage")
    used_cluster_list = tuple(v.decode() for v in cluster_usage.values())
    return tuple(set(cluster_list) - set(used_cluster_list))


# -----------------------------
# Phase timeline (UI component)
# -----------------------------
PHASE_NAMES = [
	"Preprocess",
	"Hypothesis",
	"Experiment",
	"Analysis",
	"Improvement",
	"Postprocess",
]

_TIMELINE_CSS = """
<style>
.ce-timeline-wrapper { position: sticky; top: 0; z-index: 9; padding: 6px 8px; background: inherit; backdrop-filter: blur(2px); }
.ce-timeline { display: flex; gap: 8px; align-items: center; margin: 0 0 8px 0; flex-wrap: wrap; }
.ce-step { display: flex; align-items: center; gap: 8px; }
.ce-dot { width: 10px; height: 10px; border-radius: 50%; background: #d0d7de; }
.ce-dot.active { background: #2ecc71; }
.ce-dot.done { background: #7fdbb5; }
.ce-label { font-size: 0.9rem; color: #6b7280; }
.ce-label.active { color: #111827; font-weight: 600; }
.ce-sep { width: 28px; height: 2px; background: #e5e7eb; }
</style>
"""

def render_phase_timeline(current_phase_idx: int = -1) -> None:
	"""Render a compact horizontal timeline of CE phases.

	Args:
		current_phase_idx: -1 for idle, otherwise 0..5 matching PHASE_NAMES
	"""
	steps_html = []
	for idx, name in enumerate(PHASE_NAMES):
		state_class = ""
		if current_phase_idx == idx:
			state_class = "active"
		elif current_phase_idx > idx:
			state_class = "done"
		steps_html.append(
			f"""
			<div class=\"ce-step\">
			  <span class=\"ce-dot {state_class}\"></span>
			  <span class=\"ce-label {state_class}\">{name}</span>
			</div>
			"""
		)
		if idx < len(PHASE_NAMES) - 1:
			steps_html.append("<div class=\"ce-sep\"></div>")
	html = f"""
	{_TIMELINE_CSS}
	<div class=\"ce-timeline-wrapper\"><div class=\"ce-timeline\">{''.join(steps_html)}</div></div>
	"""
	apply_html(html)


# -----------------------------
# YAML diff renderer
# -----------------------------
import difflib

def render_yaml_diff(old_text: str, new_text: str, title: str = "Change") -> None:
	"""Render a unified diff for YAML/text changes inside an expander.

	Args:
		old_text: previous content
		new_text: new content
		title: header label for the expander
	"""
	old_lines = (old_text or "").splitlines(keepends=True)
	new_lines = (new_text or "").splitlines(keepends=True)
	diff = difflib.unified_diff(old_lines, new_lines, fromfile="before", tofile="after")
	with st.expander(f"{title} (diff)"):
		st.code("".join(diff) or "(no changes)", language="diff")


# -----------------------------
# Result badges
# -----------------------------
def render_badges(items: list[tuple[str, str, str]]) -> None:
	"""Render badges as colored chips.

	Args:
		items: list of tuples (label, value, style) where style in {"success","warn","danger","info"}
	"""
	STYLE = """
	<style>
	.ce-badges{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 8px 0}
	.ce-badge{border-radius:9999px;padding:4px 10px;font-size:.85rem;border:1px solid #e5e7eb;background:#fff}
	.ce-success{background:#ecfdf5;border-color:#34d399;color:#065f46}
	.ce-warn{background:#fffbeb;border-color:#f59e0b;color:#92400e}
	.ce-danger{background:#fef2f2;border-color:#ef4444;color:#7f1d1d}
	.ce-info{background:#eff6ff;border-color:#3b82f6;color:#1e3a8a}
	</style>
	"""
	parts = ["<div class='ce-badges'>"]
	for label, value, style in items:
		parts.append(f"<span class='ce-badge ce-{style}'>{label}: {value}</span>")
	parts.append("</div>")
	apply_html(STYLE + "".join(parts))


# -----------------------------
# Dark mode and theme functions
# -----------------------------
def apply_dark_mode(enabled: bool) -> None:
	"""Apply dark mode styling."""
	if enabled:
		apply_dark_mode_css()
	else:
		apply_light_mode_css()


def apply_dark_mode_css() -> None:
	"""Apply dark mode CSS."""
	css = """
	<style>
	/* Dark mode overrides */
	.main .block-container {
		background-color: #0e1117;
		color: #fafafa;
	}
	.stApp {
		background-color: #0e1117;
	}
	.stMarkdown {
		color: #fafafa;
	}
	.stText {
		color: #fafafa;
	}
	.stMetric {
		color: #fafafa;
	}
	.stDataFrame {
		background-color: #262730;
	}
	.stExpander {
		background-color: #262730;
	}
	.stContainer {
		background-color: #262730;
	}
	.stTabs [data-baseweb="tab-list"] {
		background-color: #262730;
	}
	.stTabs [data-baseweb="tab"] {
		background-color: #262730;
		color: #fafafa;
	}
	.stTabs [aria-selected="true"] {
		background-color: #1e1e2e;
		color: #66ff66;
	}
	</style>
	"""
	apply_html(css)


def apply_light_mode_css() -> None:
	"""Apply light mode CSS."""
	css = """
	<style>
	/* Light mode overrides */
	.main .block-container {
		background-color: #ffffff;
		color: #262730;
	}
	.stApp {
		background-color: #ffffff;
	}
	.stMarkdown {
		color: #262730;
	}
	.stText {
		color: #262730;
	}
	.stMetric {
		color: #262730;
	}
	.stDataFrame {
		background-color: #fafafa;
	}
	.stExpander {
		background-color: #fafafa;
	}
	.stContainer {
		background-color: #fafafa;
	}
	.stTabs [data-baseweb="tab-list"] {
		background-color: #fafafa;
	}
	.stTabs [data-baseweb="tab"] {
		background-color: #fafafa;
		color: #262730;
	}
	.stTabs [aria-selected="true"] {
		background-color: #e6f3ff;
		color: #0066cc;
	}
	</style>
	"""
	apply_html(css)


def apply_sticky_header_css() -> None:
	"""Apply sticky header CSS."""
	css = """
	<style>
	.stApp > header {
		position: sticky;
		top: 0;
		z-index: 999;
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(10px);
	}
	</style>
	"""
	apply_html(css)


def apply_dark_mode_toggle_css() -> None:
	"""Apply dark mode toggle button CSS."""
	css = """
	<style>
	.stToggle {
		background-color: #262730;
		border-radius: 20px;
		padding: 4px;
	}
	.stToggle > label {
		color: #fafafa;
	}
	</style>
	"""
	apply_html(css)


# -----------------------------
# Copy button helper
# -----------------------------
def render_copy_button(label: str, text: str, key: str) -> None:
	"""Render a copy-to-clipboard button."""
	if st.button(label, key=key):
		st.write("```bash")
		st.code(text, language="bash")
		st.write("```")
		st.toast("Command copied to clipboard!", icon="📋")


# -----------------------------
# Skeleton loader helper
# -----------------------------
def render_skeleton_loader(placeholder_text: str = "Loading...") -> None:
	"""Render a skeleton loader."""
	css = """
	<style>
	.skeleton {
		background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
		background-size: 200% 100%;
		animation: loading 1.5s infinite;
		border-radius: 4px;
		height: 20px;
		margin: 8px 0;
	}
	@keyframes loading {
		0% { background-position: 200% 0; }
		100% { background-position: -200% 0; }
	}
	</style>
	"""
	apply_html(css)
	st.markdown(f'<div class="skeleton" title="{placeholder_text}"></div>', unsafe_allow_html=True)
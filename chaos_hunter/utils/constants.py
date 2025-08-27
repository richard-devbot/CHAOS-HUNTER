import os
from PIL import Image
import numpy as np

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# If we're in a container environment, adjust the path
if os.path.exists("/workspace"):
    PROJECT_ROOT = "/workspace"

SKAFFOLD_YAML_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/data_generation/templates/skaffold_yaml_template.j2")
UNITTEST_BASE_PY_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/k8s/unittest_base.py")
K6_POD_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/k6/templates/k6_pod_template.j2")
K8S_POD_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/k8s/templates/k8s_pod_template.j2")
META_TEMPLATE_PATH  = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/workflow_meta_template.j2")
TASK_TEMPLATE_PATH  = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/task_template.j2")
TASK_K6_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/task_k6_template.j2")
FAULT_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/fault_template.j2")
GROUNDCHILDREN_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/groundchildren_template.j2")
SUSPEND_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "chaos_hunter/ce_tools/chaosmesh/templates/suspend_template.j2")

# Prefer ChaosHunter-branded assets; gracefully fall back to existing ones
CHAOSHUNTER_LOGO_PATH = os.path.join(PROJECT_ROOT, "docs/static/images/chashunter_logo.png")
CHAOSHUNTER_IMAGE_PATH = os.path.join(PROJECT_ROOT, "docs/static/images/chashunter_icon.png")

_FALLBACK_LOGO_PATH = os.path.join(PROJECT_ROOT, "docs/static/images/chashunter_logo.png")
_FALLBACK_IMAGE_PATH = os.path.join(PROJECT_ROOT, "docs/static/images/chashunter_icon.png")

if not os.path.exists(CHAOSHUNTER_LOGO_PATH):
    CHAOSHUNTER_LOGO_PATH = _FALLBACK_LOGO_PATH
if not os.path.exists(CHAOSHUNTER_IMAGE_PATH):
    CHAOSHUNTER_IMAGE_PATH = _FALLBACK_IMAGE_PATH

# Load image files if they exist, otherwise set to None
try:
    if os.path.exists(CHAOSHUNTER_IMAGE_PATH):
        CHAOSHUNTER_IMAGE = Image.open(CHAOSHUNTER_IMAGE_PATH)
        CHAOSHUNTER_ICON = np.array(CHAOSHUNTER_IMAGE)
    else:
        CHAOSHUNTER_IMAGE = None
        CHAOSHUNTER_ICON = None
except Exception:
    CHAOSHUNTER_IMAGE = None
    CHAOSHUNTER_ICON = None

K8S_VALIDATION_VERSION = "1.27"
from PIL import Image
import numpy as np

SKAFFOLD_YAML_TEMPLATE_PATH = "chaos_hunter/data_generation/templates/skaffold_yaml_template.j2"
UNITTEST_BASE_PY_PATH = "chaos_hunter/ce_tools/k8s/unittest_base.py"
K6_POD_TEMPLATE_PATH = "chaos_hunter/ce_tools/k6/templates/k6_pod_template.j2"
K8S_POD_TEMPLATE_PATH = "chaos_hunter/ce_tools/k8s/templates/k8s_pod_template.j2"
META_TEMPLATE_PATH  = "chaos_hunter/ce_tools/chaosmesh/templates/workflow_meta_template.j2"
TASK_TEMPLATE_PATH  = "chaos_hunter/ce_tools/chaosmesh/templates/task_template.j2"
TASK_K6_TEMPLATE_PATH = "chaos_hunter/ce_tools/chaosmesh/templates/task_k6_template.j2"
FAULT_TEMPLATE_PATH = "chaos_hunter/ce_tools/chaosmesh/templates/fault_template.j2"
GROUNDCHILDREN_TEMPLATE_PATH = "chaos_hunter/ce_tools/chaosmesh/templates/groundchildren_template.j2"
SUSPEND_TEMPLATE_PATH = "chaos_hunter/ce_tools/chaosmesh/templates/suspend_template.j2"

CHAOSHUNTER_LOGO_PATH = "docs/static/images/image.png"
CHAOSHUNTER_IMAGE_PATH = "docs/static/images/chashunter_icon.png"
CHAOSHUNTER_IMAGE = Image.open(CHAOSHUNTER_IMAGE_PATH)
CHAOSHUNTER_ICON = np.array(CHAOSHUNTER_IMAGE)

K8S_VALIDATION_VERSION = "1.27"
import os
import time
import json
import subprocess
from typing import Tuple, Literal, Optional
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from ....utils.functions import (
    write_file,
    type_cmd,
    render_jinja_template,
    parse_time,
    sanitize_k8s_name,
    limit_string_length
)
from ....utils.wrappers import BaseModel
from ....utils.schemas import File
from ....utils.constants import K6_POD_TEMPLATE_PATH, K8S_POD_TEMPLATE_PATH


K8S_INSPECTION_SUMMARY = """\
# The Python code of k8s client libraries to inspect the current state of the steady state and its result are the following:
## Script:
```python
{k8s_api_command}
```  
## Result (current state):
{current_state}"""

K6_INSPECTION_SUMMARY = """\
# The k6 javascript to inspect the current state of the steady state and its result are the following:
## Script:
```js
{k6_js}
```  
## Result (current state):
# {current_state}"""


class Inspection(BaseModel):
    tool_type: Literal["k8s", "k6"]
    duration: str
    script: File
    result: Optional[str]

    def to_str(self):
        assert self.result is not None
        if self.tool_type == "k8s":
            return K8S_INSPECTION_SUMMARY.format(
                k8s_api_command=self.script.content,
                current_state=self.result
            )
        else:
            return K6_INSPECTION_SUMMARY.format(
                k6_js=self.script.content,
                current_state=self.result
            )

def _create_k8s_api_client(kube_context: str):
    """Helper function to create a Kubernetes API client."""
    configuration = client.Configuration()
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        config.load_incluster_config(client_configuration=configuration)
    else:
        config.load_kube_config(context=kube_context, client_configuration=configuration)
    return client.CoreV1Api(client.ApiClient(configuration=configuration))

def _check_pvc_exists(pvc_name: str, namespace: str, kube_context: str) -> bool:
    """Checks if a PersistentVolumeClaim exists in the specified namespace."""
    api = _create_k8s_api_client(kube_context)
    try:
        api.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
        return True
    except ApiException as e:
        if e.status == 404:
            return False
        raise

def run_pod(
    inspection: Inspection,
    work_dir: str,
    kube_context: str,
    namespace: str,
    display_container = None
) -> Tuple[int, str]:
    # Check if PVC exists before proceeding
    if not _check_pvc_exists("pvc", namespace, kube_context):
        error_msg = f"PersistentVolumeClaim 'pvc' not found in namespace '{namespace}'. Pod creation will fail."
        print(error_msg)
        if display_container is not None:
            display_container.write(f"###### Error: {error_msg}")
        return -1, error_msg
    # write pod manifest
    pod_name = sanitize_k8s_name(os.path.splitext(inspection.script.fname)[0]) + "-pod"
    script_path = inspection.script.path
    extension = os.path.splitext(inspection.script.fname)[1]
    if extension == ".js":
        template_path = K6_POD_TEMPLATE_PATH
        duration = inspection.duration
    elif extension == ".py":
        template_path = K8S_POD_TEMPLATE_PATH
        duration = parse_time(inspection.duration)
    else:
        raise TypeError(f"Invalid extension!: {extension}. .js and .py are supported.")
    pod_manifest = render_jinja_template(
        template_path,
        pod_name=pod_name,
        script_path=script_path,
        script_content=inspection.script.content if inspection.tool_type == "k8s" else "",
        duration=duration
    )
    yaml_path = f"{work_dir}/{os.path.splitext(inspection.script.fname)[0]}_pod.yaml"
    write_file(yaml_path, pod_manifest)
    # apply the manifest
    type_cmd(f"kubectl apply -f {yaml_path} --context {kube_context} -n {namespace}")
    
    # wait for completion using phase polling (Pods do not have a 'complete' condition)
    if wait_for_pod_completion(pod_name, kube_context, namespace, display_container=display_container):
        time.sleep(1)
        returncode, console_logs = get_pod_logs(pod_name, kube_context, namespace)
        type_cmd(f"kubectl delete pod {pod_name} --context {kube_context} -n {namespace}")
        return returncode, limit_string_length(console_logs)
    else:
        console_logs = "Pod did not complete successfully."
        print("Pod did not complete successfully.")
        type_cmd(f"kubectl delete pod {pod_name} --context {kube_context} -n {namespace}")
        assert False, console_logs
        return -1, console_logs

def wait_for_pod_completion(
    pod_name: str,
    kube_context: str,
    namespace: str = "chaos-hunter",
    timeout: float = 120.,  # Reduced to 2 minutes for 60-second scripts
    interval: int = 2,      # Check every 2 seconds
    display_container = None
) -> bool:
    start_time = time.time()
    while (time.time()) - start_time < timeout:
        try:
            result = subprocess.run(
                ["kubectl", "get", "pod", pod_name, "--context", kube_context, "-n", namespace, "-o", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            pod_data = json.loads(result.stdout)
            phase = pod_data["status"]["phase"]
            # Check if container has terminated (for long-running scripts)
            container_statuses = pod_data.get("status", {}).get("containerStatuses", [])
            if container_statuses and container_statuses[0].get("state", {}).get("terminated"):
                if display_container is not None:
                    display_container.write(f"###### Pod ```{pod_name}``` has completed.  \nThe inspection script's results (current states) are as follows:")
                print(f"Pod {pod_name} has completed.\nThe script's results are as follows:")
                return True
            elif phase == "Succeeded":
                if display_container is not None:
                    display_container.write(f"###### Pod ```{pod_name}``` has completed sucessfully.  \nThe inspection script's results (current states) are as follows:")
                print(f"Pod {pod_name} has completed sucessfully.\nThe script's results are as follows:")
                return True
            elif phase == "Failed":
                if display_container is not None:
                    display_container.write(f"###### Pod ```{pod_name}``` has failed.")
                print(f"Pod {pod_name} has failed.")
                return True
            else:
                if display_container is not None:
                    display_container.write(f"###### Pod ```{pod_name}``` is in phase ```{phase}```. Waiting...")
                print(f"Pod {pod_name} is in phase {phase}. Waiting... (elapsed: {int(time.time() - start_time)}s)")
        except subprocess.CalledProcessError as e:
            print(f"Error checking Pod status: {e}")
            return False
        time.sleep(interval)
    print(f"Timeout waiting for Pod {pod_name} to complete.")
    return False

def get_pod_logs(
    pod_name: str,
    kube_context: str,
    namespace: str = "chaos-hunter"
) -> Tuple[int, str]:
    try:
        result = subprocess.run(
            ["kubectl", "logs", pod_name, "--context", kube_context, "-n", namespace],
            capture_output=True, text=True, check=True
        )
        status = get_pod_status(pod_name, kube_context, namespace)
        return status.exitcode, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error getting Pod logs: {e}")
        return None

class Status(BaseModel):
    exitcode: int
    logs: str
  
def get_pod_status(
    pod_name: str,
    kube_context: str,
    namespace: str
) -> Status:
    logs = type_cmd(f"kubectl logs {pod_name} --context {kube_context} -n {namespace}")
    summary = type_cmd(f"kubectl get pod {pod_name} --context {kube_context} -n {namespace} -o json")
    # check container status
    pod_info = json.loads(summary)
    container_statuses = pod_info.get("status", {}).get("containerStatuses", [])
    assert len(container_statuses) > 0, f"Cannot find containerStatuses in the json summary: {container_statuses}."
    for container_status in container_statuses:
        state = container_status.get("state", {})
        terminated = state.get("terminated")
        if terminated:
            return Status(exitcode=int(terminated.get("exitCode")), logs=logs)
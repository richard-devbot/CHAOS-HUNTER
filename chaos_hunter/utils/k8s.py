import os
import subprocess
import time
from kubernetes import client, config

from .functions import run_command, DisplayHandler, CLIDisplayHandler


def kubectl_apply(manifest_path):
    try:
        result = subprocess.run(["kubectl", "apply", "-f", manifest_path], capture_output=True, text=True)
        if result.returncode == 0:
            print("Applied manifest successfully.")
            print(result.stdout)
        else:
            print("Error applying manifest:")
            print(result.stderr)
            return False
        return True
    except Exception as e:
        print(f"Error running kubectl apply: {e}")
        return False

def create_api_client(context=None):
    configuration = client.Configuration()
    if os.getenv('KUBERNETES_SERVICE_HOST'):
        # Running inside the cluster
        config.load_incluster_config(client_configuration=configuration)
        print("Loaded in-cluster Kubernetes configuration")
    else:
        # Running outside the cluster, using kubeconfig
        config.load_kube_config(context=context, client_configuration=configuration)
        print(f"Loaded kubeconfig with context: {context}")
    return client.ApiClient(configuration=configuration)

def check_deployment_status_by_label(label_selector, api_client, namespace=None):
    api = client.AppsV1Api(api_client)
    deployments = api.list_deployment_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_deployment(namespace, label_selector=label_selector)
    for deployment in deployments.items:
        available_replicas = deployment.status.available_replicas or 0
        desired_replicas = deployment.spec.replicas or 0
        print(f"Deployment {deployment.metadata.name} in namespace {deployment.metadata.namespace}: Available replicas {available_replicas}/{desired_replicas}")
        if available_replicas != desired_replicas:
            return False
    return True

def check_pod_status_by_label(label_selector, api_client, namespace=None):
    api = client.CoreV1Api(api_client)
    pods = api.list_pod_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_pod(namespace, label_selector=label_selector)
    for pod in pods.items:
        print(f"Pod {pod.metadata.name} in namespace {pod.metadata.namespace}: Phase {pod.status.phase}")
        if pod.status.phase != "Running":
            return False
    return True

def check_service_status_by_label(label_selector, api_client, namespace=None):
    api = client.CoreV1Api(api_client)
    services = api.list_service_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_service(namespace, label_selector=label_selector)
    for service in services.items:
        print(f"Service {service.metadata.name} in namespace {service.metadata.namespace}: Cluster IP {service.spec.cluster_ip}")
        if not service.spec.cluster_ip:
            return False
    return True

def check_job_status_by_label(label_selector, api_client, namespace=None):
    api = client.BatchV1Api(api_client)
    jobs = api.list_job_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_job(namespace, label_selector=label_selector)
    for job in jobs.items:
        print(f"Job {job.metadata.name} in namespace {job.metadata.namespace}: Succeeded {job.status.succeeded}")
        if not job.status.succeeded or job.status.succeeded < 1:
            return False
    return True

def check_statefulset_status_by_label(label_selector, api_client, namespace=None):
    api = client.AppsV1Api(api_client)
    statefulsets = api.list_stateful_set_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_stateful_set(namespace, label_selector=label_selector)
    for statefulset in statefulsets.items:
        ready_replicas = statefulset.status.ready_replicas or 0
        desired_replicas = statefulset.spec.replicas or 0
        print(f"StatefulSet {statefulset.metadata.name} in namespace {statefulset.metadata.namespace}: Ready replicas {ready_replicas}/{desired_replicas}")
        if ready_replicas != desired_replicas:
            return False
    return True

def check_daemonset_status_by_label(label_selector, api_client, namespace=None):
    api = client.AppsV1Api(api_client)
    daemonsets = api.list_daemon_set_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_daemon_set(namespace, label_selector=label_selector)
    for daemonset in daemonsets.items:
        number_available = daemonset.status.number_available or 0
        desired_number_scheduled = daemonset.status.desired_number_scheduled or 0
        print(f"DaemonSet {daemonset.metadata.name} in namespace {daemonset.metadata.namespace}: Available {number_available}/{desired_number_scheduled}")
        if number_available != desired_number_scheduled:
            return False
    return True

def check_resources_status(label_selector, api_client, namespace=None):
    if not check_deployment_status_by_label(label_selector, api_client, namespace):
        return False
    if not check_pod_status_by_label(label_selector, api_client, namespace):
        return False
    if not check_service_status_by_label(label_selector, api_client, namespace):
        return False
    if not check_job_status_by_label(label_selector, api_client, namespace):
        return False
    if not check_statefulset_status_by_label(label_selector, api_client, namespace):
        return False
    if not check_daemonset_status_by_label(label_selector, api_client, namespace):
        return False
    return True

def wait_for_resources_ready(label_selector, context=None, namespace=None, timeout=300):
    api_client = create_api_client(context)  # Create a new ApiClient for the current session
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_resources_status(label_selector, api_client, namespace):
            print(f"All resources with label '{label_selector}' are ready in namespace '{namespace}' and context '{context}'.")
            time.sleep(1)
            return True
        time.sleep(1)
    print(f"Resources with label '{label_selector}' did not become ready within the timeout period in namespace '{namespace}' and context '{context}'.")
    return False

def remove_all_resources_by_labels(
    context: str,
    label_selector: str,
    display_handler: DisplayHandler = CLIDisplayHandler()
) -> None:
    try:
        run_command(
            cmd=f"kubectl delete all --all-namespaces --context {context} -l {label_selector}",
            display_handler=display_handler
        )
    except subprocess.CalledProcessError as e:
        assert False, f"Failed to delete resources (errorcode: {e.returncode}): {e.stderr.decode('utf-8')}"

def remove_all_resources_by_namespace(
    context: str,
    namespace: str,
    display_handler: DisplayHandler = CLIDisplayHandler()
) -> None:
    for resource_type in ["workflow", "workflownode", "deployments", "pods", "services"]:
        try:
            run_command(
                cmd=f"kubectl delete {resource_type} --all --context {context} -n {namespace}",
                display_handler=display_handler
            )
        except subprocess.CalledProcessError as e:
            assert False, f"Failed to delete {resource_type} (errorcode: {e.returncode}): {e.stderr.decode('utf-8')}"

# import os
# import subprocess
# import time
# from kubernetes import client, config

# from .functions import run_command, DisplayHandler, CLIDisplayHandler


# def kubectl_apply(manifest_path):
#     try:
#         result = subprocess.run(["kubectl", "apply", "-f", manifest_path], capture_output=True, text=True)
#         if result.returncode == 0:
#             print("Applied manifest successfully.")
#             print(result.stdout)
#         else:
#             print("Error applying manifest:")
#             print(result.stderr)
#             return False
#         return True
#     except Exception as e:
#         print(f"Error running kubectl apply: {e}")
#         return False

# def create_api_client(context=None):
#     configuration = client.Configuration()
#     if os.getenv('KUBERNETES_SERVICE_HOST'):
#         # Running inside the cluster
#         config.load_incluster_config(client_configuration=configuration)
#         print("Loaded in-cluster Kubernetes configuration")
#     else:
#         # Running outside the cluster, using kubeconfig
#         config.load_kube_config(context=context, client_configuration=configuration)
#         print(f"Loaded kubeconfig with context: {context}")
#     return client.ApiClient(configuration=configuration)

# def check_deployment_status_by_label(label_selector, api_client, namespace=None):
#     api = client.AppsV1Api(api_client)
#     deployments = api.list_deployment_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_deployment(namespace, label_selector=label_selector)
#     for deployment in deployments.items:
#         available_replicas = deployment.status.available_replicas or 0
#         desired_replicas = deployment.spec.replicas or 0
#         print(f"Deployment {deployment.metadata.name} in namespace {deployment.metadata.namespace}: Available replicas {available_replicas}/{desired_replicas}")
#         if available_replicas != desired_replicas:
#             return False
#     return True

# def check_pod_status_by_label(label_selector, api_client, namespace=None):
#     api = client.CoreV1Api(api_client)
#     pods = api.list_pod_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_pod(namespace, label_selector=label_selector)
#     for pod in pods.items:
#         print(f"Pod {pod.metadata.name} in namespace {pod.metadata.namespace}: Phase {pod.status.phase}")
#         if pod.status.phase != "Running":
#             return False
#     return True

# def check_service_status_by_label(label_selector, api_client, namespace=None):
#     api = client.CoreV1Api(api_client)
#     services = api.list_service_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_service(namespace, label_selector=label_selector)
#     for service in services.items:
#         print(f"Service {service.metadata.name} in namespace {service.metadata.namespace}: Cluster IP {service.spec.cluster_ip}")
#         if not service.spec.cluster_ip:
#             return False
#     return True

# def check_job_status_by_label(label_selector, api_client, namespace=None):
#     api = client.BatchV1Api(api_client)
#     jobs = api.list_job_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_job(namespace, label_selector=label_selector)
#     for job in jobs.items:
#         print(f"Job {job.metadata.name} in namespace {job.metadata.namespace}: Succeeded {job.status.succeeded}")
#         if not job.status.succeeded or job.status.succeeded < 1:
#             return False
#     return True

# def check_statefulset_status_by_label(label_selector, api_client, namespace=None):
#     api = client.AppsV1Api(api_client)
#     statefulsets = api.list_stateful_set_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_stateful_set(namespace, label_selector=label_selector)
#     for statefulset in statefulsets.items:
#         ready_replicas = statefulset.status.ready_replicas or 0
#         desired_replicas = statefulset.spec.replicas or 0
#         print(f"StatefulSet {statefulset.metadata.name} in namespace {statefulset.metadata.namespace}: Ready replicas {ready_replicas}/{desired_replicas}")
#         if ready_replicas != desired_replicas:
#             return False
#     return True

# def check_daemonset_status_by_label(label_selector, api_client, namespace=None):
#     api = client.AppsV1Api(api_client)
#     daemonsets = api.list_daemon_set_for_all_namespaces(label_selector=label_selector) if not namespace else api.list_namespaced_daemon_set(namespace, label_selector=label_selector)
#     for daemonset in daemonsets.items:
#         number_available = daemonset.status.number_available or 0
#         desired_number_scheduled = daemonset.status.desired_number_scheduled or 0
#         print(f"DaemonSet {daemonset.metadata.name} in namespace {daemonset.metadata.namespace}: Available {number_available}/{desired_number_scheduled}")
#         if number_available != desired_number_scheduled:
#             return False
#     return True

# def check_resources_status(label_selector, api_client, namespace=None):
#     if not check_deployment_status_by_label(label_selector, api_client, namespace):
#         return False
#     if not check_pod_status_by_label(label_selector, api_client, namespace):
#         return False
#     if not check_service_status_by_label(label_selector, api_client, namespace):
#         return False
#     if not check_job_status_by_label(label_selector, api_client, namespace):
#         return False
#     if not check_statefulset_status_by_label(label_selector, api_client, namespace):
#         return False
#     if not check_daemonset_status_by_label(label_selector, api_client, namespace):
#         return False
#     return True

# def wait_for_resources_ready(label_selector, context=None, namespace=None, timeout=300):
#     api_client = create_api_client(context)  # Create a new ApiClient for the current session
#     start_time = time.time()
#     while time.time() - start_time < timeout:
#         if check_resources_status(label_selector, api_client, namespace):
#             print(f"All resources with label '{label_selector}' are ready in namespace '{namespace}' and context '{context}'.")
#             time.sleep(1)
#             return True
#         time.sleep(1)
#     print(f"Resources with label '{label_selector}' did not become ready within the timeout period in namespace '{namespace}' and context '{context}'.")
#     return False

# def remove_all_resources_by_labels(
#     context: str,
#     label_selector: str,
#     display_handler: DisplayHandler = CLIDisplayHandler()
# ) -> None:
#     try:
#         run_command(
#             cmd=f"kubectl delete all --all-namespaces --context {context} -l {label_selector}",
#             display_handler=display_handler
#         )
#     except subprocess.CalledProcessError as e:
#         # Check if the error is just "no resources found" - this is not a real error
#         error_output = e.stderr.decode('utf-8') if e.stderr else ""
#         if "No resources found" in error_output or "no resources found" in error_output:
#             display_handler.write("No resources found to delete")
#             return
#         else:
#             # This is a real error, raise it
#             raise RuntimeError(f"Failed to delete resources (errorcode: {e.returncode}): {error_output}")

# def remove_all_resources_by_namespace(
#     context: str,
#     namespace: str,
#     display_handler: DisplayHandler = CLIDisplayHandler()
# ) -> None:
#     for resource_type in ["workflow", "workflownode", "deployments", "pods", "services"]:
#         try:
#             run_command(
#                 cmd=f"kubectl delete {resource_type} --all --context {context} -n {namespace}",
#                 display_handler=display_handler
#             )
#         except subprocess.CalledProcessError as e:
#             # Check if the error is just "no resources found" - this is not a real error
#             error_output = e.stderr.decode('utf-8') if e.stderr else ""
#             if "No resources found" in error_output or "no resources found" in error_output:
#                 display_handler.write(f"No {resource_type} found to delete")
#                 continue
#             else:
#                 # This is a real error, raise it
#                 raise RuntimeError(f"Failed to delete {resource_type} (errorcode: {e.returncode}): {error_output}")
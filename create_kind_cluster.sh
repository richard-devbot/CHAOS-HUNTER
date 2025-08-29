# #!/bin/bash

# #------------------
# # default settings
# #------------------
# CLUSTER_NAME="chaos-hunter-cluster"
# PORT=8080
# OPENAI_API_KEY=""
# ANTHROPIC_API_KEY=""
# GOOGLE_API_KEY="AIzaSyDCzrl0SUX6Iy2hFl7YcBIkueLQI4vcVts"
# DEVELOP="False"

# #-----------------
# # analyze options
# #-----------------
# while [[ "$#" -gt 0 ]]; do
#     case $1 in
#         -n|--name) CLUSTER_NAME="$2"; shift 2;;
#         -p|--port) PORT="$2"; shift 2;;
#         -o|--openai-key) OPENAI_API_KEY="$2"; shift 2;;
#         -a|--anthropic-key) ANTHROPIC_API_KEY="$2"; shift 2;;
#         -g|--google-key) GOOGLE_API_KEY="$2"; shift 2;;
#         -d|--develop) DEVELOP="True"; shift 1;;
#         *) echo "Unknown parameter passed: $1"; exit 1;;
#     esac
# done

# #------------------
# # Clean previous cluster for a fresh start
# #------------------
# echo "Attempting to delete any existing kind cluster to ensure a clean start..."
# kind delete cluster --name "${CLUSTER_NAME}" || echo "No existing cluster found or failed to delete, proceeding..."

# #------------------
# # cluster settings
# #------------------
# echo "Constructing kind clusters..."
# # Create the kind cluster. We don't need a complex kind_config.yaml for this setup.
# kind create cluster --name "${CLUSTER_NAME}"
# # Check if kind cluster creation was successful
# if [ $? -ne 0 ]; then
#     echo "Failed to create the kind cluster."
#     exit 1
# fi

# #------------------
# # kubectl commands
# #------------------
# # Switch to the created cluster's context
# kubectl config use-context kind-${CLUSTER_NAME}

# # Create namespace "chaos-hunter"
# kubectl create namespace chaos-hunter

# # Deploy the simplified PVC. 'kind' will handle the PV automatically.
# kubectl apply -f k8s/pvc.yaml

# # Grant necessary permissions
# kubectl apply -f k8s/super_user_role_binding.yaml
# kubectl apply -f k8s/admin_permissions.yaml

# # Enable `kubectl top` by deploying the metrics-server
# kubectl apply -n kube-system -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# #-----------------------------
# # Build & load a docker image
# #-----------------------------
# # build the docker image for k8s api pod used by ChaosHunter
# docker build -t chaos-hunter/k8sapi:1.0 -f docker/Dockerfile_k8sapi .

# # build the main application docker image
# docker build -f docker/Dockerfile_llm -t chaos-hunter/chaos-hunter:1.0 .

# # Load the docker images into the kind cluster nodes
# echo "Loading images into kind cluster..."
# kind load docker-image chaos-hunter/k8sapi:1.0 --name ${CLUSTER_NAME}
# kind load docker-image chaos-hunter/chaos-hunter:1.0 --name ${CLUSTER_NAME}
# echo "Image loading complete."

# #------------
# # Chaos Mesh
# #------------
# helm repo add chaos-mesh https://charts.chaos-mesh.org
# helm repo update
# helm install chaos-mesh chaos-mesh/chaos-mesh --namespace chaos-mesh --create-namespace --version 2.6.3
# # Function to check if chaos-dashboard is running
# check_chaos_dashboard() {
#     kubectl get pods -n chaos-mesh -l app.kubernetes.io/component=chaos-dashboard -o jsonpath='{.items.status.phase}' 2>/dev/null
# }
# # Wait for chaos-dashboard to be running
# echo "Waiting for chaos-dashboard to be ready..."
# while [[ "$(check_chaos_dashboard)" != "Running" ]]; do
#     echo "Waiting for chaos-dashboard to be ready..."
#     sleep 5
# done

# echo "Chaos dashboard is ready. Starting port-forward..."
# nohup kubectl port-forward -n chaos-mesh svc/chaos-dashboard 2333:2333 &
# PORT_FORWARD_PID=$!
# echo "Chaos Mesh dashboard port-forwarded. To stop, use: kill ${PORT_FORWARD_PID}"

# #-------------------------------
# # launch ChaosHunter's container
# #-------------------------------
# # The docker run command is identical for both modes now, as the script handles the logic
# docker run --rm \
#     -v .:/app/ \
#     -v ~/.kube/config:/root/.kube/config \
#     -v $(which kubectl):/usr/local/bin/kubectl \
#     -v $(which skaffold):/usr/local/bin/skaffold \
#     -v $(which kind):/usr/local/bin/kind \
#     -v ~/.krew/bin/kubectl-graph:/root/.krew/bin/kubectl-graph \
#     -v /workspace:/workspace \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -e PATH="/root/.krew/bin:$PATH" \
#     -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
#     -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
#     -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
#     -d \
#     --name chaos-hunter \
#     --network host \
#     chaos-hunter/chaos-hunter:1.0 \
#     bash -c "redis-server --daemonize yes; sleep 2; redis-cli ping && tail -f /dev/null"

# #----------
# # epilogue
# #----------
# echo "A kind cluster named '${CLUSTER_NAME}' has been created successfully!"


#!/bin/bash

#------------------
# default settings
#------------------
CLUSTER_NAME="chaos-hunter-cluster"
PORT=8080
OPENAI_API_KEY=""
ANTHROPIC_API_KEY=""
GOOGLE_API_KEY=""
DEVELOP="False"
OLLAMA="False"

#-----------------
# analyze options
#-----------------
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -n|--name) CLUSTER_NAME="$2"; shift 2;;
        -p|--port) PORT="$2"; shift 2;;
        -o|--openai-key) OPENAI_API_KEY="$2"; shift 2;;
        -a|--anthropic-key) ANTHROPIC_API_KEY="$2"; shift 2;;
        -g|--google-key) GOOGLE_API_KEY="$2"; shift 2;;
        -l|--ollama) OLLAMA="True"; shift 1;;
        -d|--develop) DEVELOP="True"; shift 1;;
        *) echo "Unknown parameter passed: $1"; exit 1;;
    esac
done

#------------------
# cluster settings
#------------------
echo "Constructing kind clusters..."
# Export PWD environment variable to make sure envsubst works correctly
if [ "${DEVELOP}" = "True" ]; then
    echo "Running in development mode..."
    export MOUNTED_HOST_PATH="/workspace"
else
    export MOUNTED_HOST_PATH=$(pwd)
fi
# Create the kind cluster with our configuration, replacing the environment variable "PWD" with the root dir
envsubst < k8s/kind_config.yaml | kind create cluster --config=- --name "${CLUSTER_NAME}"
# Check if kind cluster creation was successful
if [ $? -ne 0 ]; then
    echo "Failed to create the kind cluster."
    exit 1
fi

#------------------
# kubectl commands
#------------------
# Switch to the created cluster's context
kubectl config use-context kind-${CLUSTER_NAME}

# Create namespace "chaos-hunter"
kubectl create namespace chaos-hunter

# Deploy pv/pvc
# Deploy pv/pvc
kubectl apply -f k8s/storageclass.yaml
kubectl apply -f k8s/pvc.yaml

# Grant superuser authorization to the "default" service account in the "chaos-hunter" namespace
kubectl apply -f k8s/super_user_role_binding.yaml

# Enable `kubectl top` by deploying the metrics-server
kubectl apply -n kube-system -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

#-----------------------------
# Build & load a docker image
#-----------------------------
# build and load the docker image for k8s api pod used by Chaoshunter
docker build -t chaos-hunter/k8sapi:1.0 -f docker/Dockerfile_k8sapi .
kind load docker-image chaos-hunter/k8sapi:1.0 --name ${CLUSTER_NAME}
# docker image for 
docker build -f docker/Dockerfile_llm -t chaos-hunter/chaos-hunter:1.0 .

#------------
# Chaos Mesh
#------------
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm install chaos-mesh chaos-mesh/chaos-mesh --namespace chaos-mesh --create-namespace --set chaosDaemon.runtime=containerd --set chaosDaemon.socketPath=/run/containerd/containerd.sock --set dashboard.create=true --version 2.6.3
# Function to check if chaos-dashboard is running
check_chaos_dashboard() {
    kubectl get pods -n chaos-mesh -l app.kubernetes.io/component=chaos-dashboard -o jsonpath='{.items[0].status.phase}' 2>/dev/null
}
# Wait for chaos-dashboard to be running
echo "Waiting for chaos-dashboard to be ready..."
while [[ "$(check_chaos_dashboard)" != "Running" ]]; do
    echo "Waiting for chaos-dashboard to be ready..."
    sleep 5
done

echo "Chaos dashboard is ready. Starting port-forward..."
# Enable Chaos Mesh dashboard via port-forwarding in the background
nohup kubectl port-forward -n chaos-mesh svc/chaos-dashboard 2333:2333 &
# Get the PID of the background port-forward process
PORT_FORWARD_PID=$!
# Print the background job information and the PID
echo "Chaos Mesh dashboard is being port-forwarded at http://localhost:2333 in the background."
echo "To stop the port-forward process, use: kill ${PORT_FORWARD_PID}"

#-----------------------------------
# launch ollama server if requested
#-----------------------------------
if [ "${OLLAMA}" = "True" ]; then
    echo "Starting Ollama container..."
    docker run -d \
        --name ollama \
        -p 11434:11434 \
        -v ollama_data:/root/.ollama \
        ollama/ollama:latest
fi

#-------------------------------
# launch Chaoshunter's container
#-------------------------------
if [ "${DEVELOP}" = "True" ]; then
    docker run --rm \
        -v .:/app/ \
        -v ~/.kube/config:/root/.kube/config \
        -v $(which kubectl):/usr/local/bin/kubectl \
        -v $(which skaffold):/usr/local/bin/skaffold \
        -v $(which kind):/usr/local/bin/kind \
        -v ~/.krew/bin/kubectl-graph:/root/.krew/bin/kubectl-graph \
        -v /workspace:/workspace \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e PATH="/root/.krew/bin:$PATH" \
        -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
        -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
        -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
        -d \
        --name chaos-hunter \
        --network host \
        chaos-hunter/chaos-hunter:1.0 \
        bash -c "redis-server --daemonize yes && tail -f /dev/null"
else
    docker run --rm \
        -v .:/app/ \
        -v ~/.kube/config:/root/.kube/config \
        -v $(which kubectl):/usr/local/bin/kubectl \
        -v $(which skaffold):/usr/local/bin/skaffold \
        -v $(which kind):/usr/local/bin/kind \
        -v ~/.krew/bin/kubectl-graph:/root/.krew/bin/kubectl-graph \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e PATH="/root/.krew/bin:$PATH" \
        -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
        -e ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
        -e GOOGLE_API_KEY="${GOOGLE_API_KEY}" \
        -d \
        --name chaos-hunter \
        --network host \
        chaos-hunter/chaos-hunter:1.0 \
        bash -c "redis-server --daemonize yes; streamlit run Chaoshunter_demo.py --server.port ${PORT} --server.fileWatcherType none"
fi
# COMMON_RUN_OPTS=(
#     -d --rm
#     --name chaos-hunter
#     --network host
#     -v .:/app
#     -v "$HOME/.kube/config:/root/.kube/config"
#     -v "$(which kubectl):/usr/local/bin/kubectl"
#     -v "$(which skaffold):/usr/local/bin/skaffold"
#     -v "$(which kind):/usr/local/bin/kind"
#     -v "$HOME/.krew/bin/kubectl-graph:/root/.krew/bin/kubectl-graph"
#     -v /var/run/docker.sock:/var/run/docker.sock
#     -e "PATH=/root/.krew/bin:$PATH"
#     -e "OPENAI_API_KEY=$OPENAI_API_KEY"
#     -e "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY"
#     -e "GOOGLE_API_KEY=$GOOGLE_API_KEY"
# )
# if [ "${DEVELOP}" = "True" ]; then
#   COMMON_RUN_OPTS+=(-v /workspace:/workspace)
#   RUN_CMD='bash -c "redis-server --daemonize yes && tail -f /dev/null"'
# else
#   RUN_CMD='bash -c "redis-server --daemonize yes; streamlit run Chaoshunter_demo.py --server.port '"${PORT}"' --server.fileWatcherType none"'
# fi
# docker run "${COMMON_RUN_OPTS[@]}" chaos-hunter/chaos-hunter:1.0 ${RUN_CMD}

#----------
# epilogue
#----------
echo "A kind cluster named '${CLUSTER_NAME}' has been created successuly!"
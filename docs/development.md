# Development mode
<p>
In the option A of the Quick Start, the application codebase is copied to the Docker image when building it. Then, the application is launched based on the copied codebase when running the container.
In other words, the application codebase is fixed to its state at the time of the Docker image build.

On the other hand, you may want to modify the codebase interactively while verifying its behavior.
To achieve this, you should mount a Docker volume to your working directory on the host, and manually launch the Streamlit app within the ChaosHunter's container running in dind. 
The following section describes the process step by step.
</p>

### 0. Launch the dind container in development mode
```
docker run --rm \
           --name chaos-hunter-dev \
           --privileged \
           -d \
           -p <port>:<port> \
           -v <path-to-this-repo>:/workspace \
           chaos-hunter/kind-in-dind-sandbox:0.1
docker exec -it chaos-hunter-dev bash -c "
    /usr/local/bin/entrypoint.sh --develop \
                                 --openai-key <your-openai-api-key> \
                                 --anthropic-key <your-anthropic-api-key> \
                                 --google-key <your-gemini-api-key>"
```

### 1. Enter the ChaosHunter's container running in dind
Enter the dind container.
```
docker exec -it chaos-hunter-dev bash
```
You are now within the dind container and should be able to find the ChaosHunter's container.
Check it by the following command.
```
docker ps
```
The return should be like:
```
CONTAINER ID   IMAGE                         COMMAND                  CREATED      STATUS      PORTS                       NAMES
3a7044477faf   chaos-hunter/chaos-hunter:1.0   "bash -c 'redis-serv…"   2 days ago   Up 2 days                               chaos-hunter
64b315ace43c   kindest/node:v1.30.0          "/usr/local/bin/entr…"   2 days ago   Up 2 days   127.0.0.1:41641->6443/tcp   chaos-hunter-cluster-control-plane
```
If there are no problems, enter the ChaosHunter's container.
```
docker exec -it chaos-hunter bash
``` 

### 2. Launch the streamlit app manually
Move to the mounted working directory.
```
cd /workspace
```
Launch the streamlit app by yourself.
```
streamlit run ChaosHunter_demo.py --server.port <port> --server.fileWatcherType none
```
Now, you can modify the codebase interactively while verifying its behavior.
After modifying the codebase on the host, you need to stop the Streamlit app using ```Ctrl + C``` and restart it to apply the changes.
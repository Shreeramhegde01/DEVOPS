# Exercise 2 – Deploy a Flask app on Minikube using kubectl and YAML

**Objective:** use Minikube to set up a single-node cluster and deploy a Python Flask application with a
Deployment and a NodePort Service.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask app – returns `Hello from Flask on Kubernetes!` on port 15000 |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container image for the app |
| `flask-deployment.yaml` | Deployment (1 replica, `imagePullPolicy: Never`) **+** NodePort Service |
| `test_app.py` | Unit test (`python -m pytest`) |

## Minikube cheat sheet

```bash
minikube start / stop / delete        # lifecycle
minikube status; kubectl cluster-info # status
minikube service <svc> [--url]        # open / print URL of a service
minikube service list                 # all service URLs
eval $(minikube docker-env)           # point docker CLI at Minikube's Docker daemon
minikube image load <image>           # copy a local image into Minikube
minikube logs | dashboard | ssh       # debugging
```

## Steps

### 1. Start Minikube
```bash
minikube start
```

### 2. Build the image with Minikube's Docker daemon
The Deployment uses `imagePullPolicy: Never`, so the image must already exist **inside** Minikube.

```bash
# Linux / WSL / Git Bash
eval $(minikube docker-env)
docker build -t flask-app .
```
```powershell
# Windows PowerShell
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
docker build -t flask-app .
```
(Alternative on any OS: `minikube image build -t flask-app .`)

### 3. Deploy
```bash
kubectl apply -f flask-deployment.yaml
# deployment.apps/flask-app created
# service/flask-app-service created
```

### 4. Verify
```bash
kubectl get deployments
# NAME        READY   UP-TO-DATE   AVAILABLE   AGE
# flask-app   1/1     1            1           5s

kubectl get pods -l app=flask-app
# NAME                         READY   STATUS    RESTARTS   AGE
# flask-app-7c9d8b6f5d-x2k4p   1/1     Running   0          10s

kubectl describe deployment flask-app
kubectl logs deploy/flask-app
#  * Running on http://127.0.0.1:15000
#  * Running on http://10.244.0.5:15000

kubectl get services
# NAME                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)           AGE
# flask-app-service   NodePort    10.96.45.120   <none>        15000:3xxxx/TCP   1m
```

### 5. Why `curl http://127.0.0.1:15000` fails
Minikube runs in its own VM/container. Port 15000 is open only **inside** the Pod network, not on the laptop,
so the curl gets `Connection refused`. The Service is what makes it reachable.

### 6. Access the app through the Service
```bash
minikube service flask-app-service --url
# http://127.0.0.1:36157
# ❗ Because you are using a Docker driver, the terminal needs to be open to run it.
```
Keep that terminal open; in a **new** terminal:
```bash
curl http://127.0.0.1:36157
# Hello from Flask on Kubernetes!
```

`External request → Service (port 15000) → Pod (targetPort 15000) → Flask`

## Cleanup
```bash
kubectl delete -f flask-deployment.yaml
```

## Q&A

1. **Purpose of `minikube service flask-app-service --url`?** – Prints a URL (and opens a tunnel) to reach the Service from the laptop.
2. **What happens when you run it?** – Minikube checks the Service exists, creates a tunnel to its NodePort and prints the URL.
3. **Why is `targetPort` used?** – It is the port the container listens on; the Service forwards to it.
4. **`port` vs `targetPort`?** – `port` is the Service's own port; `targetPort` is the container's port.
5. **How do you access a Flask app in Minikube?** – `minikube service <service-name> --url`, then curl/browse that URL.
6. **Why must the terminal stay open with the Docker driver?** – The URL is served by a tunnel process; closing the terminal kills the tunnel.
7. **Benefit of `--url`?** – Gives the exact URL without working out the node IP and NodePort by hand.
8. **Command to expose a service?** – `kubectl expose ...` or `kubectl apply -f <service.yaml>`.
9. **How does Minikube help?** – Runs a real single-node Kubernetes locally, so deployments can be tested without a cloud cluster.
10. **Role of `kubectl`?** – The CLI that talks to the Kubernetes API server to create, inspect, scale and delete resources.
11. **Why `imagePullPolicy: Never`?** – The image only exists locally inside Minikube; `Never` stops Kubernetes from trying (and failing) to pull it from Docker Hub.

# Exercise 1 – Kubernetes Getting Started (Hello Pod)

**Scenario (Zepto):** the product team built a lightweight storefront / delivery-status web app.
As the DevOps engineer, deploy it on Kubernetes so it is always running, portable and ready to scale.
The `nginx` image stands in for the storefront app.

**Goal:** run the first app inside Kubernetes and open it in the browser.

## Files

| File | Purpose |
|------|---------|
| `hello-k8s.yaml` | Declarative Pod + NodePort Service (same result as the `kubectl` commands below) |

## Prerequisites

| OS | Install Minikube |
|----|------------------|
| Windows (PowerShell as Admin) | `choco install minikube` |
| Linux / WSL | `curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube` |
| macOS | `brew install minikube` |

Minikube needs a driver – Docker Desktop (recommended), VirtualBox or Hyper-V.

## Steps (imperative – as in the lab manual)

```bash
# 1. Start a local single-node cluster
minikube start

# 2. Create the first Pod from the nginx image
kubectl run hello-k8s --image=nginx --port=80

# 3. Verify the Pod is running
kubectl get pods
# NAME        READY   STATUS    RESTARTS   AGE
# hello-k8s   1/1     Running   0          20s

# 4. Expose the Pod as a NodePort Service
kubectl expose pod hello-k8s --type=NodePort --port=80
kubectl get svc hello-k8s
# NAME        TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)        AGE
# hello-k8s   NodePort   10.104.12.34   <none>        80:31234/TCP   5s

# 5. Open the app in the browser (keeps a tunnel open on Docker driver - leave the terminal running)
minikube service hello-k8s
```

You should see the **"Welcome to nginx!"** page – the first container deployed on Kubernetes.

## Steps (declarative – same thing with YAML)

```bash
kubectl apply -f hello-k8s.yaml
kubectl get pods,svc -l run=hello-k8s
minikube service hello-k8s --url      # prints http://127.0.0.1:<port>
curl http://127.0.0.1:<port>          # returns the nginx welcome HTML
```

## What happens internally

1. `kubectl run` sends a Pod object to the **API server**, which stores it in **etcd**.
2. The **scheduler** picks a node (the only node, `minikube`).
3. The **kubelet** on that node asks the container runtime to pull `nginx` and start the container.
4. `kubectl expose` creates a **Service**; **kube-proxy** programs rules so that `<node-ip>:<nodePort>` forwards to the Pod's port 80.
5. `minikube service` opens a tunnel from your laptop to that NodePort.

## Cleanup

```bash
kubectl delete svc hello-k8s
kubectl delete pod hello-k8s
# or: kubectl delete -f hello-k8s.yaml
```

## Viva questions

1. **What is a Pod?** – The smallest deployable unit in Kubernetes: one or more containers that share network and storage.
2. **Why do we need a Service?** – Pod IPs are internal and change when Pods are recreated; a Service gives a stable address and can expose the Pod outside the cluster.
3. **What does `NodePort` do?** – Opens the same port (30000-32767) on every node and forwards traffic from it to the Pods behind the Service.
4. **What is Minikube?** – A tool that runs a single-node (or small multi-node) Kubernetes cluster locally for learning and testing.
5. **What happens if you delete this Pod?** – It is gone for good, because a bare Pod has no controller. A Deployment/ReplicaSet (Exercise 2 and 3) would recreate it.

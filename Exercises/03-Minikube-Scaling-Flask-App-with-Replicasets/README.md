# Exercise 3 – Scaling a Flask App on a Single Node using ReplicaSets

## Use case: e-commerce flash sale
During a flash sale (Big Billion Days / Prime Day) traffic jumps from ~100 to ~10,000 requests per minute.
A single Pod would fall over. A **ReplicaSet** keeps N identical Pods running behind one Service, so we can
scale out during the sale and back in afterwards.

**Objectives:** understand ReplicaSets and Pods, scale the app, observe self-healing and pod distribution.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flash-sale API: `/` welcome, `/buy` simulated checkout (shows which pod served it), `/health` for probes |
| `requirements.txt`, `Dockerfile` | Image `flashsale:1.0` served by gunicorn on port 5000 |
| `flashsale-replicaset.yaml` | ReplicaSet (3 replicas, readiness/liveness probes, CPU/memory limits) + ClusterIP Service |
| `flashsale-deployment.yaml` | *Additional challenge* – same app as a Deployment (rolling updates / rollback) |
| `load-test.sh` | Sends N `/buy` requests through the Service and counts requests per pod |
| `test_app.py` | Unit tests |

## Steps

### 1. Clean up any previous cluster
```bash
minikube stop
minikube delete
```

### 2. Start Minikube with one node
```bash
minikube start --nodes=1
kubectl get nodes
# NAME       STATUS   ROLES           AGE   VERSION
# minikube   Ready    control-plane   42s   v1.31.0
```

### 3. Build the image inside Minikube
Build **before** applying the ReplicaSet so the Pods find the image straight away.
```bash
eval $(minikube docker-env)                     # PowerShell: & minikube docker-env --shell powershell | Invoke-Expression
docker build -t flashsale:1.0 .
```
(Optional – push to Docker Hub instead: `docker build -t <user>/flashsale:1.0 . && docker push <user>/flashsale:1.0`
and change `image:` in the YAML.)

### 4. Create the ReplicaSet and Service
```bash
kubectl apply -f flashsale-replicaset.yaml
# replicaset.apps/flashsale-rs created
# service/flashsale-svc created
```

### 5. Verify the Pods and the ReplicaSet
```bash
kubectl get pods
# NAME                 READY   STATUS    RESTARTS   AGE
# flashsale-rs-8gbfp   1/1     Running   0          35s
# flashsale-rs-f4gsl   1/1     Running   0          35s
# flashsale-rs-nb5kl   1/1     Running   0          35s

kubectl get rs
# NAME           DESIRED   CURRENT   READY   AGE
# flashsale-rs   3         3         3       40s
```

### 6. Flash sale starts – scale to 5 replicas
```bash
kubectl scale rs flashsale-rs --replicas=5
kubectl get rs
# NAME           DESIRED   CURRENT   READY   AGE
# flashsale-rs   5         5         5       7m38s
kubectl get pods
```

### 7. Generate shopper traffic and watch the load spread across pods
```bash
./load-test.sh 30
#   6 "served_by_pod":"flashsale-rs-4nr6q"
#   7 "served_by_pod":"flashsale-rs-84v7x"
#   5 "served_by_pod":"flashsale-rs-nsmlx"
#   6 "served_by_pod":"flashsale-rs-rbwr4"
#   6 "served_by_pod":"flashsale-rs-wfbb4"
```

### 8. Self-healing – delete a pod
```bash
kubectl delete pod <one-of-the-pod-names>
kubectl get pods        # a new pod with a new name appears; the count is back to 5
```

### 9. Pod distribution across nodes
```bash
kubectl get pods -o wide
# all 5 pods show NODE = minikube (single-node cluster)
```

### 10. Sale over – scale back in
```bash
kubectl scale rs flashsale-rs --replicas=2
```

### Additional challenges
```bash
kubectl describe rs flashsale-rs            # inspect the ReplicaSet and its events
kubectl describe pod <pod>                  # probes, resources, events
kubectl logs <pod>                          # gunicorn logs
kubectl exec -it <pod> -- sh                # shell inside the container
kubectl apply -f flashsale-deployment.yaml  # Deployment instead of ReplicaSet
```

## Cleanup
```bash
kubectl delete -f flashsale-replicaset.yaml
kubectl delete -f flashsale-deployment.yaml --ignore-not-found
```

## Q&A

1. **Initial number of replicas?** – 3.
2. **Pods running after applying the ReplicaSet?** – 3.
3. **What happens when you scale to 5?** – The ReplicaSet controller creates 2 more pods so 5 are running.
4. **What happens when you delete a pod?** – The ReplicaSet notices only 4 pods match its selector and immediately creates a replacement.
5. **How does Kubernetes keep the desired count?** – A control loop keeps comparing desired replicas with running pods and creates or deletes pods to close the gap.
6. **How many nodes are running?** – 1 (`minikube`).
7. **Where are the pods running?** – All 5 on the single node `minikube`.
8. **Why readiness and liveness probes?** – Readiness keeps traffic away from a pod until `/health` answers; liveness restarts a container that stops answering.
9. **ReplicaSet vs Deployment?** – A ReplicaSet only keeps N pods running. A Deployment manages ReplicaSets and adds rolling updates, rollout history and rollback, so it is what you normally use.

# Exercise 10 – Multi-Node Kubernetes Cluster with Multiple Applications and ReplicaSets

## Storyboard
An e-commerce platform has two services:
1. **Product Catalog** (AppA) – lists available products → **2 replicas**
2. **Shopping Cart** (AppB) – manages user carts → **3 replicas**

For availability and fault tolerance, the replicas of each service must be spread across **different nodes**, so a
node failure never takes a whole service down.

```
                      Minikube profile "devops-multinode"
 ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
 │ devops-multinode     │ │ devops-multinode-m02 │ │ devops-multinode-m03 │
 │  shopping-cart  pod  │ │  shopping-cart  pod  │ │  shopping-cart  pod  │
 │                      │ │  product-catalog pod │ │  product-catalog pod │
 └──────────────────────┘ └──────────────────────┘ └──────────────────────┘
      NodePort Services: product-catalog-service, shopping-cart-service
```

## Files

| File | Purpose |
|------|---------|
| `product_catalog.py`, `Dockerfile.product` | AppA – `GET /products` (+ `GET /whoami` shows pod and node) |
| `shopping_cart.py`, `Dockerfile.shopping` | AppB – `GET /cart`, `POST /cart` (+ `GET /whoami`) |
| `product_catalog_deployment.yaml` | Deployment, 2 replicas, required pod anti-affinity on `kubernetes.io/hostname` |
| `shopping_cart_deployment.yaml` | Deployment, 3 replicas, same anti-affinity |
| `product_catalog_service.yaml`, `shopping_cart_service.yaml` | NodePort Services |
| `test_apps.py` | Unit tests for both apps |

## Steps

### Step 0 – Clean up any existing Minikube
```bash
minikube stop
minikube delete
```

### Step 1 – Start a 3-node cluster
```bash
minikube start --nodes 3 -p devops-multinode
# Linux as root with the docker driver needs --force
# Low on RAM? add --memory=2048 --cpus=2

kubectl get nodes
# NAME                   STATUS   ROLES           AGE   VERSION
# devops-multinode       Ready    control-plane   90s   v1.31.0
# devops-multinode-m02   Ready    <none>          60s   v1.31.0
# devops-multinode-m03   Ready    <none>          35s   v1.31.0
```

> With several nodes, `eval $(minikube docker-env)` would build the image on **one** node only.
> Build locally and use `minikube image load`, which copies the image to **every** node (Step 3).
> The manual also enables the registry add-on (`minikube -p devops-multinode addons enable registry`);
> that is an alternative way to share images and is not needed with `image load`.

### Step 2 – Build the images
```bash
docker build -t product-catalog:latest -f Dockerfile.product .
docker build -t shopping-cart:latest -f Dockerfile.shopping .
docker images | grep -E "product-catalog|shopping-cart"
```

### Step 3 – Load the images into the cluster
```bash
minikube -p devops-multinode image load product-catalog:latest
minikube -p devops-multinode image load shopping-cart:latest
minikube -p devops-multinode image ls | grep -E "product-catalog|shopping-cart"
# docker.io/library/shopping-cart:latest
# docker.io/library/product-catalog:latest
```

### Step 4 – Deploy the applications
```bash
kubectl apply -f product_catalog_deployment.yaml
kubectl apply -f shopping_cart_deployment.yaml
kubectl apply -f product_catalog_service.yaml
kubectl apply -f shopping_cart_service.yaml
```

> Fix compared to the manual: its `shopping_cart_deployment.yaml` used `namespace: devops-exercise` while the
> Service is in `default`. A Service only selects Pods in its own namespace, so the cart Service would have no
> endpoints. Both now use `default`.

### Step 5 – Verify distribution
```bash
kubectl get pods -o wide
# NAME                               READY   STATUS    IP           NODE
# product-catalog-5fdfc7f5fb-2jlnv   1/1     Running   10.244.1.3   devops-multinode-m02
# product-catalog-5fdfc7f5fb-7v556   1/1     Running   10.244.2.4   devops-multinode-m03
# shopping-cart-788c48675b-7l4lx     1/1     Running   10.244.0.4   devops-multinode
# shopping-cart-788c48675b-d48w2     1/1     Running   10.244.1.4   devops-multinode-m02
# shopping-cart-788c48675b-hml9r     1/1     Running   10.244.2.5   devops-multinode-m03
```
Every replica of a service is on a different node – that is what `podAntiAffinity` enforces.

### Step 6 – Access the services (keep each terminal open)
```bash
minikube -p devops-multinode service product-catalog-service --url    # e.g. http://127.0.0.1:35855
minikube -p devops-multinode service shopping-cart-service --url      # e.g. http://127.0.0.1:38975
```

### Step 7 – Test with curl
```bash
curl http://127.0.0.1:35855/products
# [{"id":1,"name":"Laptop","price":1200},{"id":2,"name":"Phone","price":800},{"id":3,"name":"Headphones","price":150}]

curl http://127.0.0.1:38975/cart
# []

curl -X POST http://127.0.0.1:38975/cart -H "Content-Type: application/json" -d '{"id": 1, "name": "Laptop", "quantity": 1}'
# [{"id":1,"name":"Laptop","quantity":1}]

curl http://127.0.0.1:38975/whoami
# {"node":"devops-multinode-m03","pod":"shopping-cart-788c48675b-hml9r","service":"shopping-cart"}
```
PowerShell: use `curl.exe` and escape the JSON: `-d '{\"id\": 1, \"name\": \"Laptop\", \"quantity\": 1}'`.

## Observations

1. **Spread across nodes:** 2 catalog pods on 2 different nodes, 3 cart pods on 3 different nodes.
2. **Node failure experiment**
   ```bash
   kubectl drain devops-multinode-m02 --ignore-daemonsets --delete-emptydir-data
   kubectl get pods -o wide
   ```
   * The product-catalog pod from m02 is rescheduled on the free node (`devops-multinode`), so the service stays at 2 replicas.
   * The shopping-cart pod from m02 stays **Pending**: the only two healthy nodes already run a cart pod, and
     *required* anti-affinity forbids a second one. The service keeps working on 2 of 3 replicas.
     Using `preferredDuringSchedulingIgnoredDuringExecution` would let it squeeze onto a node already running one.
   ```bash
   kubectl uncordon devops-multinode-m02     # node back → the Pending pod is scheduled again
   ```
3. **State per replica:** the cart is a Python list in each pod's memory. Repeating `curl .../cart` can return
   different carts because each request may land on a different pod. Real systems keep shared state outside the
   pods (Redis / a database) so any replica can serve any user.

## Cleanup
```bash
minikube delete -p devops-multinode
```

## Summary
Two Python services (Product Catalog and Shopping Cart) were deployed on a 3-node Minikube cluster with replicas
spread across nodes by pod anti-affinity. This maximises availability and fault tolerance: losing a node removes
at most one replica of each service.

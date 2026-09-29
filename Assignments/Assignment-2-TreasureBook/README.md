# Assignment 2 – TreasureBook: Graph API on Kubernetes with Autoscaling

> *Imagine Facebook's web of friendships, likes and shares – but for a treasure hunt.*
> TreasureBook connects **treasures, locations and maps** (nodes) with **trails, hiding places and leads**
> (edges). As the DevOps engineer, keep it running, scaling and observable during treasure-hunt surges.

## Mission → deliverables

| Mission | Deliverable |
|---------|-------------|
| 1. Build and containerise the TreasureBook API | `app/app.py`, `app/Dockerfile`, build/run instructions below |
| 2. Deploy the API and MongoDB on Kubernetes | `k8s/api-deployment.yaml`, `k8s/api-service.yaml`, `k8s/mongodb.yaml` |
| 3. Autoscaling for high traffic | `k8s/api-hpa.yaml` – 3 → 10 pods at > 5% CPU |
| 4. Monitor the system under load | `metrics-server` + `kubectl top`, `loadtest/watch_scaling.sh` |
| 5. Simulate real-world traffic and analyse scaling | `loadtest/load_test.py`, `loadtest/loadtest-job.yaml`, [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) |

## Graph model (Facebook TAO analogy)

| Facebook (TAO) | TreasureBook | Example | API |
|----------------|--------------|---------|-----|
| User | **Treasure** (node) | Golden Crown | `POST /node {"type":"Treasures", "name":"Golden Crown"}` |
| Page | **Location** (node) | Cave of Wonders | `POST /node {"type":"Location", ...}` |
| Message | **Map** (node) | Mystic Map | `POST /node {"type":"Map", ...}` |
| Friendship | **Trail** (edge, Location → Location) | Forest of Secrets ↔ Mystic Lake | `POST /edge {"type":"Trail", "from":..., "to":...}` |
| Likes | **Hidden-At** (edge, Treasure → Location) | Golden Crown hidden at Cave of Wonders | `POST /edge {"type":"Hidden-At", ...}` |
| Comments | **Leads-To** (edge, Map → Treasure) | Mystic Map leads to Cursed Diamond | `POST /edge {"type":"Leads-to", ...}` |

Like TAO, *objects* (nodes) and *associations* (edges) live in separate collections (`nodes`, `edges`), with
edges indexed by `from`/`to` for fast neighbour look-ups. Edge endpoints are validated
(e.g. `Hidden-At` must go Treasure → Location).

### API reference

| Method & path | Description |
|---------------|-------------|
| `POST /node` | Create a node – `{"type": "Treasure\|Location\|Map", "name": "...", "properties": {...}}` (plural `Treasures` also accepted) |
| `GET /nodes?type=Location&limit=50` | List nodes, optionally by type |
| `GET /node/<id or name>` | One node |
| `GET /node/<id or name>/neighbors` | All edges in/out of a node with the connected nodes |
| `POST /edge` | Create an edge – `{"type": "Trail\|Hidden-At\|Leads-To", "from": <id or name>, "to": <id or name>}` |
| `GET /edges?type=Trail` | List edges |
| `GET /path?from=A&to=B` | Shortest chain of trails/leads between two nodes (breadth-first, ≤ 6 hops) |
| `GET /graph` | Whole graph (nodes + edges) |
| `GET /stats` | Counts per node / edge type |
| `GET /health`, `GET /ready` | Liveness (process up) / readiness (MongoDB reachable) probes |

Every response carries an `X-Served-By: <pod-name>` header, which shows load balancing across replicas.

## 1. Containerisation

### Build and run with Docker
```bash
cd Assignments/Assignment-2-TreasureBook
docker network create treasure-net
docker run -d --name mongodb --network treasure-net -v treasure-data:/data/db mongo:7.0
docker build -t treasurebook-api:1.0 ./app
docker run -d --name treasurebook-api --network treasure-net -p 5000:5000 \
  -e MONGO_URI=mongodb://mongodb:27017/treasurebook treasurebook-api:1.0

./loadtest/seed_data.sh http://localhost:5000
```
or simply `docker compose up -d --build` (same thing, defined in `docker-compose.yml`).

Example:
```bash
curl -X POST localhost:5000/node -H "Content-Type: application/json" -d '{"type":"Treasures","name":"Golden Crown"}'
# {"created_at":"2026-09-29T10:00:00+00:00","id":"66f9...","name":"Golden Crown","properties":{},"type":"Treasure"}
curl "localhost:5000/path?from=Forest%20of%20Secrets&to=Golden%20Crown"
# {"found":true,"hops":3,"path":["Forest of Secrets","Mystic Lake","Cave of Wonders","Golden Crown"],"via":["Trail","Trail","Hidden-At"]}
```

## 2. Deploy on Kubernetes (Minikube)

```bash
minikube start --cpus=4 --memory=6144
minikube addons enable metrics-server          # required by the HPA

# build the image straight into Minikube
minikube image build -t treasurebook-api:1.0 ./app
# (or: eval $(minikube docker-env) && docker build -t treasurebook-api:1.0 ./app)

kubectl apply -f k8s/
kubectl rollout status deployment/mongodb
kubectl rollout status deployment/treasurebook-api

kubectl get deploy,pods,svc,hpa
# NAME                               READY   UP-TO-DATE   AVAILABLE
# deployment.apps/mongodb            1/1     1            1
# deployment.apps/treasurebook-api   3/3     3            3
# NAME                                                    REFERENCE                     TARGETS       MINPODS   MAXPODS   REPLICAS
# horizontalpodautoscaler.autoscaling/treasurebook-api   Deployment/treasurebook-api   cpu: 2%/5%    3         10        3
```

| Manifest | Key settings |
|----------|--------------|
| `api-deployment.yaml` | `replicas: 3`, requests **100m CPU / 256Mi**, limits **200m CPU / 512Mi**, readiness `/ready`, liveness `/health` |
| `api-hpa.yaml` | `minReplicas: 3`, `maxReplicas: 10`, target **5 % CPU**, fast scale-up, 60 s scale-down window |
| `api-service.yaml` | `NodePort` 30080 → pod port 5000 |
| `mongodb.yaml` | 1 replica, `Recreate` strategy, 1 Gi PersistentVolumeClaim, ClusterIP Service `mongodb` |

Access the API:
```bash
minikube service treasurebook-api --url       # keep open; prints e.g. http://127.0.0.1:52341
./loadtest/seed_data.sh http://127.0.0.1:52341
```

## 3–5. Autoscaling under simulated traffic

Terminal 1 – record the autoscaler:
```bash
./loadtest/watch_scaling.sh          # writes loadtest/results/scaling-<time>.csv
```
Terminal 2 – watch pods appear:
```bash
kubectl get hpa treasurebook-api -w
kubectl top pods -l app=treasurebook-api
```
Terminal 3 – the treasure-hunt surge, **inside the cluster** (recommended):
```bash
cd loadtest
kubectl create configmap treasurebook-loadtest --from-file=load_test.py
kubectl apply -f loadtest-job.yaml
kubectl logs -f job/treasurebook-loadtest
```
or from the laptop through the tunnel: `python loadtest/load_test.py --url http://127.0.0.1:52341 --duration 180 --concurrency 30`.

What you should see:
1. CPU climbs well above 5% → the HPA adds pods in steps of up to 4 → **10 replicas** within about a minute.
2. The load test summary lists requests served by **several different pods**.
3. After the test, CPU drops → after the 60 s window the HPA scales back down to **3**.

Record your numbers in [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md).

Re-run the test: `kubectl delete job treasurebook-loadtest && kubectl apply -f loadtest/loadtest-job.yaml`.

## Cleanup
```bash
kubectl delete -f k8s/ -f loadtest/loadtest-job.yaml --ignore-not-found
kubectl delete configmap treasurebook-loadtest --ignore-not-found
```

## Tests
```bash
cd app && pip install -r requirements.txt mongomock pytest && python -m pytest -v
```

## Screenshots to capture
1. `docker build` + `curl` creating nodes / edges and `/path` output.
2. `kubectl get deploy,pods,svc,hpa` after deployment (3 replicas).
3. `kubectl get hpa -w` / `watch_scaling.sh` during the surge (replicas → 10).
4. `kubectl get pods -o wide` with 10 API pods, and `kubectl top pods`.
5. Load test summary (throughput, latency percentiles, requests per pod).
6. Scale-down back to 3 replicas.

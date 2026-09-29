# TreasureBook – Performance Report

## Test setup

| Item | Value |
|------|-------|
| Cluster | Minikube, single node (docker driver) |
| API | `treasurebook-api:1.0`, gunicorn 2 workers × 4 threads per pod |
| Per-pod resources | requests 100m CPU / 256Mi, limits 200m CPU / 512Mi |
| Autoscaler | HPA `autoscaling/v2`, min 3, max 10, target 5% average CPU |
| Database | MongoDB 7.0, 1 replica, 1 Gi PVC |
| Load generator | `loadtest/load_test.py` as a Kubernetes Job (in-cluster, through the `treasurebook-api` Service) |
| Traffic | 30 concurrent "adventurers", 180 s; mix 20% create node, 10% create edge, 30% list nodes, 15% neighbours, 10% stats, 10% get node, 5% shortest path |

How to reproduce: see [README.md](README.md#35-autoscaling-under-simulated-traffic).

## Results

_Fill in from `kubectl logs job/treasurebook-loadtest` and `loadtest/results/scaling-*.csv`._

### Traffic simulation

| Metric | Value |
|--------|-------|
| Total requests | |
| Throughput (req/s) | |
| Success rate | |
| Latency avg / p50 / p95 / p99 / max (ms) | |
| Pods that served traffic | |

### Scaling timeline

| Time (s) | CPU utilisation (% of request) | Desired replicas | Running pods |
|----------|-------------------------------|------------------|--------------|
| 0 | | 3 | 3 |
| | | | |

## Observations

- **Scale-up:**
- **Load distribution:**
- **Latency during scale-up:**
- **Resource usage (`kubectl top pods`):**
- **Scale-down:**
- **Bottlenecks / improvements:**

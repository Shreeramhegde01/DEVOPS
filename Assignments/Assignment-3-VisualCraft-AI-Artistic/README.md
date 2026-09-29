# Assignment 3 – VisualCraft: Deploying, Monitoring and Automating an AI Artistic Style Service

**Problem statement:** Visual Craft is an AI art platform that turns photos into artistic images with neural
style transfer. As its DevOps engineer, deploy the provided AI service (`urmsandeep/ai-artistic-style-service`),
make it self-healing, monitor API usage and resources with Prometheus + Grafana, and automate testing and
deployment with a CI/CD pipeline.

## Architecture

```
                         POST /styleTransfer (image=@photo.jpg)
   curl / Postman ────────────────► localhost:5001
                                        │
┌───────────────────────────────────────┼───────── docker compose project "visualcraft" ───────────────────┐
│                          ┌────────────▼────────────┐   forwards    ┌─────────────────────────────────┐    │
│                          │ style-api-gateway :5001 │ ────────────► │ ai-artistic-style :5001         │    │
│                          │ Flask + prometheus_client│              │ urmsandeep/ai-artistic-style-   │    │
│                          │ /metrics  /health        │              │ service (PyTorch "mosaic" model)│    │
│                          └────────────▲────────────┘              │ restart: always                 │    │
│                                       │ scrape 5s                  └───────────────▲─────────────────┘    │
│  ┌──────────────┐  query  ┌───────────┴───────┐  scrape  ┌──────────────┐          │ container CPU/mem    │
│  │ Grafana :3000│ ──────► │ Prometheus :9090  │ ───────► │ cAdvisor     │ ─────────┘                      │
│  │ dashboard    │         │ + alert rules     │ ───────► │ node-exporter│ (host CPU / memory)             │
│  └──────────────┘         └───────────────────┘          └──────────────┘                                 │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
   CI/CD: Jenkinsfile (poll SCM) or GitHub Actions  →  tests → pull → build → deploy → verify → resilience test
```

**Why a gateway?** The provided image only has `POST /styleTransfer` (Flask + PyTorch) – no `/metrics`
endpoint (checked by inspecting the image: it installs only `torch torchvision flask`). A Prometheus target of
`ai-artistic-style:5001` would therefore return 404. The gateway (`gateway/app.py`) is a thin reverse proxy that
keeps the API identical on port 5001 and records, for every call:

| Metric | Used for |
|--------|----------|
| `styletransfer_requests_total{status="200\|400\|500\|..."}` | Number of requests, grouped by status code |
| `rate(styletransfer_requests_total[1m])` | Request rate, traffic spikes |
| `styletransfer_request_duration_seconds` (histogram) | Response time – average, p50 / p95 / p99 |
| `styletransfer_requests_in_progress`, `styletransfer_upload_bytes` | Concurrency, input sizes |
| `styletransfer_upstream_up` | Is the AI container reachable? (alert `AIServiceDown`) |

CPU and memory come from **cAdvisor** (per container) and **node-exporter** (host).

## Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | AI service (`restart: always`), gateway, Prometheus, Grafana, node-exporter, cAdvisor |
| `gateway/` | Metrics gateway (Flask, prometheus_client) + `Dockerfile` + unit tests |
| `prometheus/` | `prometheus.yml` (4 scrape jobs), `alert_rules.yml`, `Dockerfile` |
| `grafana/` | Provisioned data source + dashboard **VisualCraft – API Performance** |
| `tests/smoke_test.py` | Post-deployment test: 200 + valid JPEG, 400 without an image, metrics present |
| `tests/sample-input.jpg` | Sample input image (use your own photo too) |
| `scripts/generate_traffic.py` | Mixed traffic (200 / 400 / 500) to populate the dashboards |
| `scripts/resilience_test.sh` | Crashes the AI container and verifies auto-restart + recovery |
| `Jenkinsfile` | CI/CD pipeline (Jenkins) |
| `../../.github/workflows/visualcraft-cicd.yml` | Same pipeline on GitHub Actions |

## 1. Run the AI service on its own (as in the assignment)
```bash
docker pull urmsandeep/ai-artistic-style-service
docker run -d -p 5001:5001 urmsandeep/ai-artistic-style-service
docker ps -a | grep ai-artistic-style-service
curl -X POST http://127.0.0.1:5001/styleTransfer -F "image=@tests/sample-input.jpg" --output styled_image.jpg
```
Stop it before continuing (`docker rm -f <id>`), because the compose stack uses port 5001.

## 2. Deploy with Docker Compose
```bash
cd Assignments/Assignment-3-VisualCraft-AI-Artistic
docker compose up -d --build        # first run pulls ~3 GB (PyTorch image)
docker compose ps
docker compose logs -f ai-artistic-style-service     # wait for "Running on http://0.0.0.0:5001"
```

## 3. API testing
```bash
curl -X POST http://localhost:5001/styleTransfer -F "image=@tests/sample-input.jpg" --output styled_output.jpg
curl -i -X POST http://localhost:5001/styleTransfer                  # 400 {"error":"No image uploaded"}
curl http://localhost:5001/metrics | grep styletransfer_requests_total
```
Or the automated check:
```bash
pip install requests
python tests/smoke_test.py
# 1. Waiting up to 240s for http://localhost:5001 ...
#    service is up
# 2. POST /styleTransfer with sample-input.jpg (30167 bytes)
#    HTTP 200, image/jpeg, ... bytes in 0.9s
#    stylized image saved to .../output/styled_output.jpg
# 3. POST /styleTransfer without an image (expect 400)
#    HTTP 400 {"error":"No image uploaded"}
# 4. GET /metrics
#    styletransfer_requests_total{endpoint="/styleTransfer",method="POST",status="200"} 1.0
#    styletransfer_requests_total{endpoint="/styleTransfer",method="POST",status="400"} 1.0
# PASS - the AI Artistic Style Service is deployed and working
```
**Postman:** `POST http://localhost:5001/styleTransfer` → Body → form-data → key `image` (type *File*) → choose a
JPG → *Send and Download*.

## 4. Monitoring
```bash
python scripts/generate_traffic.py --requests 60      # ~80% OK, ~10% 400, ~10% 500
```
* **Prometheus** http://localhost:9090 → *Status → Targets*: `ai-artistic-style-service`, `cadvisor`,
  `node-exporter`, `prometheus` all **UP**. Try `sum by (status) (styletransfer_requests_total)`.
* **Grafana** http://localhost:3000 (admin / admin) → *Dashboards → VisualCraft → VisualCraft – API Performance*:

| Panel | Query (simplified) |
|-------|--------------------|
| Total API Requests | `sum(styletransfer_requests_total)` |
| Success Rate | `rate(...{status="200"}) / rate(...)` |
| Avg Response Time | `rate(duration_sum) / rate(duration_count)` |
| AI Service UP/DOWN | `styletransfer_upstream_up` |
| Requests by Status Code | `sum by (status) (increase(styletransfer_requests_total[1m]))` |
| Request Rate | `sum(rate(styletransfer_requests_total[1m]))` |
| Response Time p50/p95/p99 | `histogram_quantile(0.95, sum by (le) (rate(..._bucket[5m])))` |
| CPU Usage (containers) | `rate(container_cpu_usage_seconds_total{name="ai-artistic-style"}[1m]) * 100` |
| Memory Usage (containers) | `container_memory_working_set_bytes{name="ai-artistic-style"}` |
| Host CPU / Memory | node-exporter |

Alert rules (`prometheus/alert_rules.yml`): `AIServiceDown`, `HighErrorRate` (> 10% 5xx), `HighLatency` (p95 > 5 s).
Import community dashboards too if you like: *Dashboards → New → Import* → `1860` (Node Exporter Full) or
`14282` (cAdvisor).

## 5. Resilience testing
```bash
./scripts/resilience_test.sh
# == Restart count before: 0   (restart policy: always)
# == Simulating a crash of the AI service (process inside ai-artistic-style exits)
# == Waiting for Docker to restart the container ...
#    restarted automatically (restart count 0 -> 1) after 3s
# == Verifying the API works again (model reload can take a minute) ...
# PASS - the AI Artistic Style Service is deployed and working
# == Service self-recovered 25s after the crash
```
While it runs, Grafana shows the AI service going **DOWN**, the gateway answering **502** (visible in
*Requests by Status Code*), and everything returning to normal once Docker has restarted the container.
> `docker kill` / `docker stop` count as a *manual* stop, and Docker deliberately does not restart manually
> stopped containers. That is why the script makes the process inside the container exit instead.

## 6. CI/CD pipeline

### Jenkins (`Jenkinsfile`)
1. Start Jenkins from **Exercise 7** (`docker compose up -d --build` in `Exercises/07-Jenkins-CI-Automation`).
2. **New Item → Pipeline** → *Pipeline script from SCM* → Git → `https://github.com/Shreeramhegde01/DEVOPS.git`,
   branch `*/main`, Script Path `Assignments/Assignment-3-VisualCraft-AI-Artistic/Jenkinsfile` → Save → **Build Now**.

| Stage | What happens |
|-------|--------------|
| Run Tests | Unit tests of the gateway – nothing is deployed if they fail |
| Pull Docker Image | `docker pull urmsandeep/ai-artistic-style-service:latest` |
| Build Images | gateway, Prometheus and Grafana images |
| Deploy Service | `docker compose up -d` (only changed containers are recreated) |
| Verify Deployment | `tests/smoke_test.py` against the live service; the styled image is archived as a build artifact |
| Resilience Test | crash + auto-restart check (parameter `RUN_RESILIENCE_TEST`) |

**Automatic redeploy on push:** the pipeline polls GitHub every 2 minutes (`pollSCM('H/2 * * * *')`). Change something
(e.g. a panel title in `grafana/dashboards/…json`), commit and push – within 2 minutes Jenkins starts a build, runs
the tests and redeploys the changed service.

### GitHub Actions (`.github/workflows/visualcraft-cicd.yml`)
Every push that touches this folder runs *Run tests* → *Deploy and verify* (compose up, smoke test, traffic,
Prometheus/Grafana checks, resilience test) on a GitHub runner. The stylized output image is uploaded as a workflow artifact.
See the **Actions** tab of the repository.

## Cleanup
```bash
docker compose down            # add -v to also drop volumes
```

## Screenshots to capture (submission)
1. `docker compose ps` – all 6 containers up.
2. curl/Postman request and response; **input image and stylized output image** side by side.
3. Prometheus *Targets* (all UP) and *Alerts*.
4. Grafana **VisualCraft – API Performance** dashboard after `generate_traffic.py` (Total requests, status codes,
   rate, latency, CPU, memory).
5. Resilience test output + the dip visible in Grafana.
6. Jenkins Stage View of a successful run (and a second run triggered by a push), or the GitHub Actions run.

# Exercise 6 – Real-Time Operations Monitoring and Alerting (ZAPPTTO)

**Objective:** as a DevOps engineer at ZAPPTTO (a quick-commerce delivery service), give operations real-time
insight into delivery performance: simulate delivery metrics in Python, scrape them with **Prometheus**,
visualise them in **Grafana**, raise **alerts**, and automate the deployment with **Jenkins**.

```
delivery_metrics.py ──/metrics:8000──►  Prometheus :9090  ──►  Grafana :3000
   (Gauges + Summary)     scrape 5s      alert_rules.yml         dashboard
                                          (alerts)
          ▲                                                         ▲
          └──────────────  Jenkinsfile: build → deploy → verify  ───┘
```

## Files

```
06-Grafana-Realtime-Monitoring-of-Quick-Commerce-App/
├── delivery_metrics.py        # Python script that simulates metrics (Gauges + Summary)
├── requirements.txt
├── test_delivery_metrics.py   # unit tests (run by the pipeline)
├── Dockerfile                 # image for delivery_metrics.py
├── prometheus.yml             # Prometheus scrape configuration
├── alert_rules.yml            # alert rules
├── Dockerfile.prometheus      # prom/prometheus + our config baked in
├── Dockerfile.grafana         # grafana + provisioned data source + dashboard
├── grafana/provisioning/...   # data source + dashboard provider
├── grafana/dashboards/delivery-monitoring.json
├── docker-compose.yml         # the whole stack in one command
└── Jenkinsfile                # CI/CD pipeline
```

## Option A – step by step (as in the lab manual)

### Step 1 – Run the Python application
```bash
pip3 install prometheus-client
python3 delivery_metrics.py
# [INFO] Starting the HTTP server on port 8000...
# [DEBUG] Total deliveries: 69
# [DEBUG] Pending deliveries: 20
# [DEBUG] On-the-way deliveries: 17
# [DEBUG] Average delivery time: 28.26 seconds
```
```bash
curl http://localhost:8000/metrics | grep deliver
# total_deliveries 96.0
# pending_deliveries 13.0
# on_the_way_deliveries 16.0
# average_delivery_time_count 42.0
# average_delivery_time_sum 1261.7
```
`start_http_server` creates the `/metrics` endpoint automatically. Metric types: **Counter** (only goes up),
**Gauge** (up and down), **Histogram** (bucketed distribution), **Summary** (count + sum, quantiles).

### Step 2 – Run Prometheus with the config and alert rules
```bash
# Windows / macOS (Docker Desktop):
docker run -d --name prometheus -p 9090:9090 \
  -v "$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml" \
  -v "$(pwd)/alert_rules.yml:/etc/prometheus/alert_rules.yml" \
  prom/prometheus:v2.54.1

# Linux / WSL: add  --add-host=host.docker.internal:host-gateway
# PowerShell: use ${PWD} instead of $(pwd)
```
Open http://localhost:9090 → **Status → Targets**: `delivery_service` should be **UP**.

### Step 3 – Run Grafana
```bash
docker run -d --name grafana -p 3000:3000 grafana/grafana:11.2.0
```
1. http://localhost:3000 → login `admin` / `admin` (skip the password change).
2. **Connections → Data sources → Add → Prometheus**, URL `http://host.docker.internal:9090`
   (Linux: `http://172.17.0.1:9090`) → **Save & test**.
3. **Dashboards → New → Import** → upload `grafana/dashboards/delivery-monitoring.json`, or build the panels:
   * Total Deliveries – `total_deliveries`
   * Pending Deliveries – `pending_deliveries`
   * On-the-Way Deliveries – `on_the_way_deliveries`
   * Average Delivery Time – `rate(average_delivery_time_sum[1m]) / rate(average_delivery_time_count[1m])`

### Step 4 – Alerts
Prometheus → **Alerts**: `HighPendingDeliveries` goes *pending* and then *firing* (pending is 10–20, threshold 10).

| Alert | Expression | Severity |
|-------|------------|----------|
| HighPendingDeliveries | `pending_deliveries > 10` for 15s | warning |
| HighAverageDeliveryTime | 1-minute average delivery time `> 30` for 15s | critical |
| DeliveryServiceDown | `up{job="delivery_service"} == 0` for 30s | critical |

### Step 5 – Simulate more alerts
```bash
PENDING_MIN=50 PENDING_MAX=100 DELIVERY_TIME_MIN=35 DELIVERY_TIME_MAX=60 python3 delivery_metrics.py
```
(Equivalent to editing `pending = random.randint(50, 100)` in the code.) Both alerts fire within ~30 seconds.

Stop the manual containers before Option B: `docker rm -f prometheus grafana`.

## Option B – everything with Docker Compose
```bash
docker compose up -d --build
docker compose ps
```
* Metrics: http://localhost:8000/metrics
* Prometheus: http://localhost:9090 (Targets / Alerts)
* Grafana: http://localhost:3000 → dashboard **ZAPPTTO → ZAPPTTO Delivery Monitoring**, already wired to Prometheus

Simulate alerts: `PENDING_MIN=50 PENDING_MAX=100 docker compose up -d`. Stop: `docker compose down`.

## Step 6 – Jenkins pipeline
1. Start Jenkins from **Exercise 7** (the custom image has docker CLI + compose + python3, with the Docker socket mounted).
2. **New Item → Pipeline** → *Pipeline script from SCM* → Git → this repository URL, branch `main`,
   Script Path `Exercises/06-Grafana-Realtime-Monitoring-of-Quick-Commerce-App/Jenkinsfile`.
   (Or paste the Jenkinsfile into *Pipeline script* for a quick test.)
3. **Build Now**. Stages: *Pre-check Docker → Unit Test Metrics App → Build Docker Images →
   Run Application, Prometheus & Grafana → Verify Monitoring Stack*.

> The manual's Jenkinsfile copies files from a local path and bind-mounts `$WORKSPACE/prometheus.yml`.
> When Jenkins itself runs in Docker, that workspace path does not exist on the Docker host, so Docker mounts
> an empty directory instead of the file and Prometheus fails to start. Here the configs are baked into images and
> the repo is checked out by Jenkins (SCM), which works in every setup.

## Expected outputs (take screenshots)
1. `curl http://localhost:8000/metrics` output.
2. Prometheus **Targets** page (`delivery_service` UP) and a graph of `pending_deliveries`.
3. Prometheus **Alerts** page with `HighPendingDeliveries` firing.
4. Grafana dashboard with the four panels.
5. Jenkins **Console Output** / Stage View of a successful build.

## Networking note (WSL / Linux)
Containers reach the host through `host.docker.internal` (Docker Desktop) or the `docker0` bridge IP
(`172.17.0.1`, see `ip addr show docker0`). With Docker Compose all three services share a network and
Grafana reaches Prometheus by service name (`http://prometheus:9090`).

# Assignment 1 (Option 1) – Dockerized Multi-Container Web Application with Networking and Container Management

**Objective:** build a Python web application with a database backend, containerise both services, and manage the
containers and network **programmatically with the Docker SDK for Python**.

## Architecture

```
            Browser / curl  ──►  localhost:5000
                                     │  (published port)
 ┌───────────────────────────────────┼──── crud-net (custom bridge network) ────────────┐
 │  ┌────────────────────────────────▼──┐  mongodb://crud-mongodb:27017  ┌─────────────┐ │
 │  │ crud-flask-app  (Flask + gunicorn)│ ─────────────────────────────► │ crud-mongodb│ │
 │  │ CRUD API + web UI, HEALTHCHECK    │    Docker DNS resolves name    │  mongo:7.0  │ │
 │  └───────────────────────────────────┘                                └──────┬──────┘ │
 └──────────────────────────────────────────────────────────────────────────────┼────────┘
                                                                  volume crud-mongo-data
        scripts/*.py  ── Docker SDK for Python ──► build, network, volume, containers, health, restart
```

## Requirement → implementation

| # | Requirement | Where |
|---|-------------|-------|
| 1 | Flask web app with CRUD, data in MongoDB | `app/app.py` (REST API `/api/books`) + `app/templates/index.html` (web UI) |
| 1 | Dockerfile for the Flask app | `app/Dockerfile` (gunicorn, `HEALTHCHECK`) |
| 2 | Database in a separate container, persisted with a volume | `mongo:7.0` container `crud-mongodb` with named volume `crud-mongo-data` (`setup_network.py`); proven by `verify_persistence.py` |
| 3 | Docker SDK creates a custom bridge network and connects both containers | `scripts/setup_network.py` |
| 3 | Script to manage and inspect the network, proving communication | `scripts/inspect_network.py` (subnet, IPs, name resolution + TCP test, disconnect/reconnect demo) |
| 4 | Script that lists active containers, checks the Flask container's health and restarts it if unhealthy | `scripts/container_manager.py` |
| 5 | Demonstration | "Demo script" below |

## API

| Method | Path | Body | Result |
|--------|------|------|--------|
| POST | `/api/books` | `{"title": "...", "author": "...", "year": 2020}` | 201 + created book |
| GET | `/api/books` | – | list of books |
| GET | `/api/books/<id>` | – | one book / 404 |
| PUT | `/api/books/<id>` | any of `title`, `author`, `year` | updated book |
| DELETE | `/api/books/<id>` | – | `{"deleted": "<id>"}` |
| GET | `/health` | – | 200 healthy (DB ping ok) / 503 DB down / 500 fault injected |
| POST | `/admin/fail` | – | demo only: forces `/health` to fail until the container restarts |

## Setup
Requirements: Docker (Docker Desktop on Windows/macOS) and Python 3.9+.
```bash
cd Assignments/Assignment-1A-Dockerized-Multi-Container-CRUD-App/scripts
pip install -r requirements.txt
```

## Demo script

### 1. Build and start everything (Docker SDK)
```bash
python setup_network.py
# 1. Building image crud-flask-app:1.0 from .../app ...
# 2. Network
#    created bridge network 'crud-net' (3f9c1b2a7d11)
# 3. Volume
#    created volume 'crud-mongo-data'
# 4. Starting MongoDB container 'crud-mongodb' (mongo:7.0) ...
#    MongoDB is ready
# 5. Starting Flask container 'crud-flask-app' ...
#    app healthy: {'books': 0, 'database': 'up', 'status': 'healthy'}
# Done. Open http://localhost:5000 in the browser.
```
Open **http://localhost:5000** and add, edit and delete a few books in the UI – or use curl:
```bash
curl -X POST localhost:5000/api/books -H "Content-Type: application/json" -d '{"title":"The Phoenix Project","author":"Gene Kim","year":2013}'
curl localhost:5000/api/books
curl -X PUT localhost:5000/api/books/<id> -H "Content-Type: application/json" -d '{"year":2018}'
curl -X DELETE localhost:5000/api/books/<id>
```

### 2. Inspect the network and test connectivity
```bash
python inspect_network.py --demo-disconnect
# === Inspecting crud-net ===
# Network : crud-net (3f9c1b2a7d11)
# Driver  : bridge   Scope: local   Internal: False
# Subnet  : 172.19.0.0/16   Gateway: 172.19.0.1
# Containers on this network:
#    crud-mongodb       172.19.0.2/16      02:42:ac:13:00:02
#    crud-flask-app     172.19.0.3/16      02:42:ac:13:00:03
# === Connectivity tests ===
# [PASS] crud-flask-app -> crud-mongodb:27017 (resolved to 172.19.0.2)
# [PASS] host -> crud-flask-app:5000 /health -> 200 {...}
# === Disconnecting crud-flask-app from crud-net ===
# [PASS] app can no longer reach the DB: socket.gaierror: [Errno -2] Name or service not known
# [PASS] reconnected - app reaches the DB again (172.19.0.2)
```

### 3. Container management and auto-restart
Terminal 1:
```bash
python container_manager.py --watch --interval 5
# === Active containers ===
# NAME                 IMAGE                    STATUS     HEALTH     PORTS
# crud-flask-app       crud-flask-app:1.0       running    healthy    5000/tcp->5000
# crud-mongodb         mongo:7.0                running    n/a
# === Health check ===
# [10:02:01] crud-flask-app healthy (docker: healthy, http: 200, books: 3)
```
Terminal 2 – break the app:
```bash
curl -X POST localhost:5000/admin/fail
```
Terminal 1 reacts:
```
# [10:02:06] UNHEALTHY crud-flask-app (docker: healthy, http: 500, body: {...fault injected...}) -> restarting
# [10:02:09] crud-flask-app recovered in 3.2s: {'books': 3, 'database': 'up', 'status': 'healthy'}
```
Also try `docker stop crud-flask-app` → the manager starts it again.

### 4. Data persistence across container restarts
```bash
python verify_persistence.py
# 1. Created book 66f9... 'Persistence check 10:05:12'
# 2. Stopping and removing MongoDB container crud-mongodb (a1b2c3d4e5f6) completely ...
#    while the DB is gone, GET /api/books -> HTTP 503
# 3. Creating a brand-new MongoDB container with the same volume 'crud-mongo-data' ...
# 4. GET /api/books -> HTTP 200, 4 book(s)
# RESULT: PASS - data survived the container re-creation
```

### 5. Cleanup
```bash
python teardown.py            # containers + network
python teardown.py --volumes  # ... and the data volume
```

## Tests
```bash
cd app && pip install -r requirements.txt mongomock pytest && python -m pytest -v
```

## Screenshots to capture
1. `setup_network.py` output and the web UI with some books.
2. `inspect_network.py --demo-disconnect` output.
3. `container_manager.py --watch` detecting and restarting the unhealthy container.
4. `verify_persistence.py` PASS.
5. `docker ps`, `docker network inspect crud-net`, `docker volume ls`.

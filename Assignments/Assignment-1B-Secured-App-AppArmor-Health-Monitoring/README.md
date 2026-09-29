# Assignment 1 (Option 2) – Secured Multi-Container Python Application with AppArmor and Automated Health Monitoring

**Objective:** a secure, containerised Flask application (user registration + login) with a MongoDB backend,
confined by an **AppArmor** profile applied through the **Docker SDK for Python**, plus a **health monitor**
that restarts the app when it becomes unhealthy and sends an alert.

## Architecture

```
  Browser / curl ──► localhost:5050
                        │
 ┌──────────────────────┼─────────── auth-net (custom bridge network) ──────────────────────┐
 │  ┌───────────────────▼─────────────────────┐                     ┌──────────────────────┐ │
 │  │ secure-flask-app (gunicorn, non-root)   │ ── TCP 27017 ─────► │ auth-mongodb         │ │
 │  │  AppArmor: flask-auth-profile (enforce) │   Docker DNS name   │ users collection     │ │
 │  │  cap_drop ALL, no-new-privileges        │                     └──────────┬───────────┘ │
 │  │  HEALTHCHECK → /health                  │                                │             │
 │  └───────────────────▲─────────────────────┘                     volume auth-mongo-data   │
 └──────────────────────┼───────────────────────────────────────────────────────────────────┘
                        │ checks every 5 s: state, Docker health, /health, probe login
             scripts/health_monitor.py ── restart + log + alert (console / e-mail / webhook)
```

## Requirement → implementation

| # | Requirement | Where |
|---|-------------|-------|
| 1 | Flask app with registration and login | `app/app.py` + `app/templates/` (web pages) and JSON API `/api/register`, `/api/login`; passwords stored as salted hashes |
| 1 | Dockerfile | `app/Dockerfile` – non-root user, `HEALTHCHECK` |
| 2 | Separate MongoDB container, data persisted in a volume | `auth-mongodb` + volume `auth-mongo-data` (`scripts/deploy_secure_stack.py`) |
| 2 | Docker networking between app and DB | custom bridge `auth-net`, DB reached by container name |
| 3 | AppArmor profile restricting the app (file access, ...) | `apparmor/flask-auth-profile` |
| 3 | Docker SDK applies the profile and verifies enforcement | `deploy_secure_stack.py` (`security_opt=["apparmor=flask-auth-profile"]`), `verify_apparmor.py` |
| 4 | Script that periodically checks the Flask container's health | `scripts/health_monitor.py` |
| 4 | Restart when unhealthy (e.g. failed login service) and log it | same – restart + `scripts/logs/health_monitor.log` |
| 4 | Notification on restart (e-mail or console) | console always; e-mail via SMTP and/or webhook when configured |
| 5 | Live demo | "Demo script" below |

## What the AppArmor profile enforces (`apparmor/flask-auth-profile`)

| Protection | Rules |
|------------|-------|
| Account data unreadable | `deny /etc/passwd`, `/etc/shadow`, `/etc/gshadow`, `/root/**` |
| Application code immutable | `deny /app/** wl` |
| System directories read-only | `deny /etc/** wl`, `/usr/** wl`, `/var/** wl`, `/bin/** wl`, ... |
| No shells / tools | `deny /{,usr/}bin/{bash,dash,sh,curl,wget,apt*}`, `pip*` |
| Network limited to TCP/UDP | `deny network raw`, `deny network packet` |
| No privileged kernel operations | `deny capability sys_admin/sys_module/sys_ptrace`, `deny mount`, `/proc` and `/sys` writes |

On top of that the container runs as a non-root user with `cap_drop=["ALL"]` and `no-new-privileges`.

## Setup

AppArmor needs a **Linux host with AppArmor** (Ubuntu/Debian – native, VM or cloud VM). Docker Desktop on
Windows/macOS cannot load AppArmor profiles; there you can still demo everything else with `--no-apparmor`.

```bash
cd Assignments/Assignment-1B-Secured-App-AppArmor-Health-Monitoring
sudo apt-get install -y apparmor-utils
sudo cp apparmor/flask-auth-profile /etc/apparmor.d/flask-auth-profile
sudo apparmor_parser -r -W /etc/apparmor.d/flask-auth-profile
sudo aa-status | grep flask-auth-profile

cd scripts
pip install -r requirements.txt
```

## Demo script

### 1. Deploy (Docker SDK)
```bash
python deploy_secure_stack.py            # add --no-apparmor on Docker Desktop
# 1. Building secure-flask-app:1.0 ...
# 2. Network 'auth-net' and volume 'auth-mongo-data'
# 3. MongoDB container 'auth-mongodb' (user data persisted in 'auth-mongo-data')
# 4. Flask container 'secure-flask-app' (AppArmor profile flask-auth-profile, no-new-privileges)
#    healthy: {'database': 'up', 'login_service': 'ok', 'status': 'healthy'}
```
Open **http://localhost:5050** → register → log in → dashboard.
```bash
curl -X POST localhost:5050/api/register -H "Content-Type: application/json" -d '{"username":"shreeram","password":"devops-2026"}'
# {"message":"registered","username":"shreeram"}
curl -X POST localhost:5050/api/login -H "Content-Type: application/json" -d '{"username":"shreeram","password":"devops-2026"}'
# {"message":"login successful","username":"shreeram"}
```

### 2. Security – verify the AppArmor profile
```bash
python verify_apparmor.py
# === Profile applied? ===
# HostConfig.SecurityOpt : ['apparmor=flask-auth-profile', 'no-new-privileges:true']
# AppArmorProfile        : flask-auth-profile
# Kernel view of PID 1   : flask-auth-profile (enforce)
#
# === Enforcement ===
# Action                                           docker-default       flask-auth-profile
# ------------------------------------------------------------------------------------------
# Read /etc/passwd (as root)                       ALLOWED (exit 0)     BLOCKED (exit 1)
# Modify application code /app/app.py (as root)    ALLOWED (exit 0)     BLOCKED (exit 1)
# Create a file in /etc (as root)                  ALLOWED (exit 0)     BLOCKED (exit 1)
# App process spawns /bin/sh                       ALLOWED (exit 0)     BLOCKED (exit 1)
# Read the app's templates                         ALLOWED (exit 0)     ALLOWED (exit 0)
#
# === Application still works under the profile ===
# register -> 201, login -> 200 {...}
# RESULT: AppArmor profile applied and enforced, app functional
```

### 3. Automated health monitoring
Terminal 1:
```bash
python health_monitor.py --interval 5 --threshold 2
# 2026-09-29 10:10:01 INFO    monitoring secure-flask-app every 5s (restart after 2 consecutive failures)
# 2026-09-29 10:10:01 INFO    check 1: healthy
```
Terminal 2 – break the login service:
```bash
curl -X POST localhost:5050/admin/fail
```
Terminal 1:
```
# 2026-09-29 10:10:06 WARNING check 2: UNHEALTHY (1/2) - /health returned 503: {'login_service': 'failing', 'status': 'unhealthy'}
# 2026-09-29 10:10:11 WARNING check 3: UNHEALTHY (2/2) - /health returned 503: {...}
# 2026-09-29 10:10:11 WARNING restarting secure-flask-app (reason: /health returned 503: ...)
# 2026-09-29 10:10:14 INFO    secure-flask-app recovered after 3.1s
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ALERT: secure-flask-app restarted after failed health check
# Reason: /health returned 503: ...
# Result: recovered after 3.1s
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# 2026-09-29 10:10:16 INFO    check 4: healthy
```
Other failures it handles: `docker stop secure-flask-app` (it is started again) and `docker stop auth-mongodb`
(the login check fails → app restart → alert; start the DB again with `docker start auth-mongodb`).

The incident history is in `scripts/logs/health_monitor.log`.

#### E-mail / webhook alerts (optional)
```bash
export SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=you@gmail.com SMTP_PASSWORD=<app-password>
export ALERT_EMAIL_TO=you@gmail.com
export ALERT_WEBHOOK_URL=https://hooks.slack.com/services/...     # optional
python health_monitor.py
```

### 4. Persistence
```bash
docker rm -f auth-mongodb && python deploy_secure_stack.py   # users are still there (volume auth-mongo-data)
```

### 5. Cleanup
```bash
python teardown.py --volumes
sudo apparmor_parser -R /etc/apparmor.d/flask-auth-profile
```

## Tests
```bash
cd app && pip install -r requirements.txt mongomock pytest && python -m pytest -v
```

## Screenshots to capture
1. Register / login / dashboard pages.
2. `sudo aa-status` showing `flask-auth-profile` in enforce mode.
3. `verify_apparmor.py` output.
4. `health_monitor.py` detecting the failure, restarting and printing the alert.
5. `docker ps` (both containers healthy) and `docker network inspect auth-net`.

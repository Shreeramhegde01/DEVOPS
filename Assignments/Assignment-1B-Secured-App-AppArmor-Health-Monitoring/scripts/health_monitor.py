"""Automated health monitoring for the SecureAuth Flask container.

Every --interval seconds it checks:
  1. the container is running
  2. Docker's HEALTHCHECK status is not "unhealthy"
  3. GET /health returns 200 (database reachable + login service ok)
  4. a real login with a probe account succeeds (POST /api/login)

After --threshold consecutive failed checks it restarts the container, logs the incident to
logs/health_monitor.log and sends an alert:
  * console (always)
  * e-mail  - if SMTP_HOST and ALERT_EMAIL_TO are set (optional SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_FROM)
  * webhook - if ALERT_WEBHOOK_URL is set (e.g. a Slack incoming webhook), JSON {"text": ...}

Usage:  python health_monitor.py [--interval 5] [--threshold 2] [--cycles 0]
Demo:   curl -X POST http://localhost:5050/admin/fail      (breaks the login service)
"""
import argparse
import json
import logging
import os
import smtplib
import socket
import time
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from common import APP_CONTAINER, client, get_container, health_status, http_json, wait_for_app

PROBE_USER = os.environ.get("PROBE_USERNAME", "healthcheck-probe")
PROBE_PASSWORD = os.environ.get("PROBE_PASSWORD", "probe-password-123")
LOG_FILE = Path(__file__).resolve().parent / "logs" / "health_monitor.log"

log = logging.getLogger("health_monitor")


def setup_logging():
    LOG_FILE.parent.mkdir(exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")):
        handler.setFormatter(formatter)
        log.addHandler(handler)
    log.setLevel(logging.INFO)


def ensure_probe_account():
    status, _ = http_json("POST", "/api/register", {"username": PROBE_USER, "password": PROBE_PASSWORD})
    return status in (201, 409)   # created now, or already existed


def check(docker_client):
    """Returns (healthy, reason)."""
    container = get_container(docker_client, APP_CONTAINER)
    if container is None:
        return False, "container does not exist"
    if container.status != "running":
        return False, f"container status is '{container.status}'"
    if health_status(container) == "unhealthy":
        return False, "Docker HEALTHCHECK reports unhealthy"
    status, body = http_json("GET", "/health")
    if status != 200:
        return False, f"/health returned {status}: {body}"
    status, body = http_json("POST", "/api/login", {"username": PROBE_USER, "password": PROBE_PASSWORD})
    if status == 401 and ensure_probe_account():   # probe account missing (e.g. fresh volume) - recreate once
        status, body = http_json("POST", "/api/login", {"username": PROBE_USER, "password": PROBE_PASSWORD})
    if status != 200:
        return False, f"probe login failed with {status}: {body}"
    return True, "ok"


def notify(subject, message):
    """Console alert always; e-mail and webhook when configured."""
    banner = "!" * 72
    print(f"\n{banner}\nALERT: {subject}\n{message}\n{banner}\n", flush=True)

    if os.environ.get("SMTP_HOST") and os.environ.get("ALERT_EMAIL_TO"):
        try:
            email = EmailMessage()
            email["Subject"] = f"[SecureAuth] {subject}"
            email["From"] = os.environ.get("ALERT_EMAIL_FROM", os.environ.get("SMTP_USER", "monitor@localhost"))
            email["To"] = os.environ["ALERT_EMAIL_TO"]
            email.set_content(message)
            with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", 587)), timeout=10) as smtp:
                smtp.starttls()
                if os.environ.get("SMTP_USER"):
                    smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
                smtp.send_message(email)
            log.info("alert e-mail sent to %s", os.environ["ALERT_EMAIL_TO"])
        except (OSError, smtplib.SMTPException) as exc:
            log.error("could not send alert e-mail: %s", exc)

    if os.environ.get("ALERT_WEBHOOK_URL"):
        try:
            payload = json.dumps({"text": f"*{subject}*\n{message}"}).encode()
            request = urllib.request.Request(os.environ["ALERT_WEBHOOK_URL"], data=payload,
                                             headers={"Content-Type": "application/json"})
            urllib.request.urlopen(request, timeout=10).close()
            log.info("alert webhook delivered")
        except OSError as exc:
            log.error("could not deliver webhook alert: %s", exc)


def restart(docker_client, reason):
    container = get_container(docker_client, APP_CONTAINER)
    if container is None:
        log.error("cannot restart: %s does not exist (run deploy_secure_stack.py)", APP_CONTAINER)
        return
    log.warning("restarting %s (reason: %s)", APP_CONTAINER, reason)
    started = time.time()
    if container.status == "running":
        container.restart(timeout=5)
    else:
        container.start()
    recovered = wait_for_app(timeout=60)
    took = time.time() - started
    outcome = f"recovered after {took:.1f}s" if recovered else f"STILL UNHEALTHY {took:.0f}s after restart"
    log.info("%s %s", APP_CONTAINER, outcome)
    notify(
        f"{APP_CONTAINER} restarted after failed health check",
        f"Host: {socket.gethostname()}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Reason: {reason}\nResult: {outcome}\nLog: {LOG_FILE}",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--interval", type=int, default=5, help="seconds between checks (default 5)")
    parser.add_argument("--threshold", type=int, default=2, help="consecutive failures before restart (default 2)")
    parser.add_argument("--cycles", type=int, default=0, help="stop after N checks (0 = run forever)")
    args = parser.parse_args()

    setup_logging()
    docker_client = client()
    ensure_probe_account()
    log.info("monitoring %s every %ss (restart after %s consecutive failures)",
             APP_CONTAINER, args.interval, args.threshold)

    failures, cycle = 0, 0
    while True:
        cycle += 1
        healthy, reason = check(docker_client)
        if healthy:
            if failures:
                log.info("%s healthy again", APP_CONTAINER)
            failures = 0
            log.info("check %d: healthy", cycle)
        else:
            failures += 1
            log.warning("check %d: UNHEALTHY (%d/%d) - %s", cycle, failures, args.threshold, reason)
            if failures >= args.threshold:
                restart(docker_client, reason)
                failures = 0
        if cycle == args.cycles:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nmonitor stopped")

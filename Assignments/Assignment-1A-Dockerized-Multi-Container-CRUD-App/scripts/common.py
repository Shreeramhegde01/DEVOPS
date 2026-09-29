"""Names and helpers shared by all management scripts (Docker SDK for Python)."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import docker
from docker.errors import NotFound

NETWORK = "crud-net"                 # custom bridge network
VOLUME = "crud-mongo-data"           # named volume -> MongoDB data survives container restarts / re-creation
DB_IMAGE = "mongo:7.0"
DB_CONTAINER = "crud-mongodb"        # also the hostname the app uses (Docker DNS on the custom network)
APP_IMAGE = "crud-flask-app:1.0"
APP_CONTAINER = "crud-flask-app"
APP_PORT = 5000
APP_URL = f"http://localhost:{APP_PORT}"
APP_DIR = Path(__file__).resolve().parent.parent / "app"


def client():
    return docker.from_env()


def get_container(docker_client, name):
    try:
        return docker_client.containers.get(name)
    except NotFound:
        return None


def http_json(method, path, body=None, timeout=5):
    """Small HTTP helper (standard library only). Returns (status, parsed-json-or-None)."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(APP_URL + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")
    except OSError:
        return None, None


def wait_for_app(timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, body = http_json("GET", "/health")
        if status == 200:
            return body
        time.sleep(2)
    return None


def wait_for_mongo(container, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        exit_code, _ = container.exec_run(["mongosh", "--quiet", "--eval", "db.adminCommand('ping').ok"])
        if exit_code == 0:
            return True
        time.sleep(2)
    return False


def health_status(container):
    """Docker HEALTHCHECK status: starting / healthy / unhealthy, or 'n/a' if the image has none."""
    container.reload()
    return container.attrs["State"].get("Health", {}).get("Status", "n/a")

"""Names and helpers shared by the management scripts (Docker SDK for Python)."""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import docker
from docker.errors import NotFound

NETWORK = "auth-net"
VOLUME = "auth-mongo-data"
DB_IMAGE = "mongo:7.0"
DB_CONTAINER = "auth-mongodb"
APP_IMAGE = "secure-flask-app:1.0"
APP_CONTAINER = "secure-flask-app"
APPARMOR_PROFILE = "flask-auth-profile"
APP_PORT = 5050                      # host port -> container port 5000
APP_URL = f"http://localhost:{APP_PORT}"
ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"


def client():
    return docker.from_env()


def get_container(docker_client, name):
    try:
        return docker_client.containers.get(name)
    except NotFound:
        return None


def apparmor_supported(docker_client):
    """True if the Docker host runs AppArmor (Linux). Docker Desktop on Windows/macOS does not."""
    return any("apparmor" in opt for opt in docker_client.info().get("SecurityOptions", []))


def http_json(method, path, body=None, timeout=5):
    """Returns (status, parsed-json-or-None); status is None if the app is unreachable."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(APP_URL + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        try:
            return err.code, json.loads(err.read() or b"null")
        except ValueError:
            return err.code, None
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


def health_status(container):
    container.reload()
    return container.attrs["State"].get("Health", {}).get("Status", "n/a")

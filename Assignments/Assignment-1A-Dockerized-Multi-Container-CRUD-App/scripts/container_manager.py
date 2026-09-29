"""Container management: lists all active containers, checks the health of the Flask container and restarts it
automatically if it is unhealthy (or starts it if it has stopped).

Usage:  python container_manager.py                  # one check
        python container_manager.py --watch          # keep checking every 10 s (Ctrl+C to stop)
        python container_manager.py --watch --interval 5 --cycles 20

Health = Docker HEALTHCHECK status (see app/Dockerfile) AND a live HTTP GET /health from the host.
Demo:   curl -X POST http://localhost:5000/admin/fail    -> next check restarts the container
"""
import argparse
import datetime
import time

from common import APP_CONTAINER, client, get_container, health_status, http_json, wait_for_app


def log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def list_active_containers(docker_client):
    containers = docker_client.containers.list()   # running containers only
    print(f"{'NAME':<20} {'IMAGE':<24} {'STATUS':<10} {'HEALTH':<10} PORTS")
    for c in containers:
        image = c.image.tags[0] if c.image.tags else c.image.short_id
        ports = ", ".join(f"{k}->{v[0]['HostPort']}" for k, v in (c.ports or {}).items() if v)
        print(f"{c.name:<20} {image:<24} {c.status:<10} {health_status(c):<10} {ports}")
    return containers


def check_and_heal(docker_client):
    """Returns True if the app was healthy, False if an action (start/restart) was needed."""
    app = get_container(docker_client, APP_CONTAINER)
    if app is None:
        log(f"{APP_CONTAINER} does not exist - run setup_network.py")
        return False

    if app.status != "running":
        log(f"{APP_CONTAINER} is '{app.status}' -> starting it")
        app.start()
        wait_for_app()
        return False

    docker_health = health_status(app)
    http_status, body = http_json("GET", "/health")
    if docker_health != "unhealthy" and http_status == 200:
        log(f"{APP_CONTAINER} healthy (docker: {docker_health}, http: {http_status}, books: {body.get('books')})")
        return True

    log(f"UNHEALTHY {APP_CONTAINER} (docker: {docker_health}, http: {http_status}, body: {body}) -> restarting")
    started = time.time()
    app.restart(timeout=5)
    recovered = wait_for_app()
    if recovered:
        log(f"{APP_CONTAINER} recovered in {time.time() - started:.1f}s: {recovered}")
    else:
        log(f"{APP_CONTAINER} still unhealthy after restart - check: docker logs {APP_CONTAINER}")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--watch", action="store_true", help="keep checking")
    parser.add_argument("--interval", type=int, default=10, help="seconds between checks (default 10)")
    parser.add_argument("--cycles", type=int, default=0, help="stop after N checks (0 = forever)")
    args = parser.parse_args()

    docker_client = client()
    print("=== Active containers ===")
    list_active_containers(docker_client)
    print("\n=== Health check ===")

    cycle = 0
    while True:
        cycle += 1
        check_and_heal(docker_client)
        if not args.watch or cycle == args.cycles:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")

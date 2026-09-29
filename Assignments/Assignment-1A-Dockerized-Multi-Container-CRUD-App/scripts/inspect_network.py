"""Inspects the custom bridge network and proves the containers can talk to each other.

Usage:  python inspect_network.py                     # inspect + connectivity tests
        python inspect_network.py --demo-disconnect   # also disconnect/reconnect the app to show isolation
"""
import sys
import time

from common import APP_CONTAINER, DB_CONTAINER, NETWORK, client, get_container, http_json

PROBE = ("import socket; ip = socket.gethostbyname('{host}'); "
         "socket.create_connection(('{host}', {port}), 3); print(ip)")


def probe_db_from_app(app):
    """Run inside the Flask container: resolve the DB by name and open a TCP connection to port 27017."""
    exit_code, output = app.exec_run(["python", "-c", PROBE.format(host=DB_CONTAINER, port=27017)])
    return exit_code == 0, (output.decode().strip().splitlines() or [""])[-1]


def show_network(network):
    network.reload()
    attrs = network.attrs
    ipam = attrs["IPAM"]["Config"][0] if attrs["IPAM"]["Config"] else {}
    print(f"Network : {attrs['Name']} ({attrs['Id'][:12]})")
    print(f"Driver  : {attrs['Driver']}   Scope: {attrs['Scope']}   Internal: {attrs['Internal']}")
    print(f"Subnet  : {ipam.get('Subnet')}   Gateway: {ipam.get('Gateway')}")
    print("Containers on this network:")
    for info in attrs["Containers"].values():
        print(f"   {info['Name']:<18} {info['IPv4Address']:<18} {info['MacAddress']}")


def main():
    docker_client = client()
    networks = docker_client.networks.list(names=[NETWORK])
    if not networks:
        sys.exit(f"Network '{NETWORK}' not found - run setup_network.py first")
    network = networks[0]
    app = get_container(docker_client, APP_CONTAINER)
    if app is None or get_container(docker_client, DB_CONTAINER) is None:
        sys.exit("Containers not found - run setup_network.py first")

    print("=== Docker networks on this host ===")
    for net in docker_client.networks.list():
        print(f"   {net.name:<22} {net.attrs['Driver']}")

    print("\n=== Inspecting", NETWORK, "===")
    show_network(network)

    print("\n=== Connectivity tests ===")
    ok, detail = probe_db_from_app(app)
    print(f"[{'PASS' if ok else 'FAIL'}] {APP_CONTAINER} -> {DB_CONTAINER}:27017 (resolved to {detail})")
    status, body = http_json("GET", "/health")
    print(f"[{'PASS' if status == 200 else 'FAIL'}] host -> {APP_CONTAINER}:5000 /health -> {status} {body}")
    all_ok = ok and status == 200

    if "--demo-disconnect" in sys.argv:
        print(f"\n=== Disconnecting {APP_CONTAINER} from {NETWORK} ===")
        network.disconnect(app)
        ok_disconnected, detail = probe_db_from_app(app)
        print(f"[{'PASS' if not ok_disconnected else 'FAIL'}] app can no longer reach the DB: {detail}")
        network.connect(app)
        time.sleep(2)
        ok_again, detail = probe_db_from_app(app)
        print(f"[{'PASS' if ok_again else 'FAIL'}] reconnected - app reaches the DB again ({detail})")
        all_ok = all_ok and not ok_disconnected and ok_again

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

"""Task 4 - apply the AppArmor profile to the Flask container with the Docker SDK for Python.

Usage:  python apply_apparmor.py [--keep]
        --keep  leave the container running afterwards (default: stop and remove it)
"""
import sys
import time
import urllib.request

import docker

IMAGE = "flask-apparmor"
CONTAINER = "flask-apparmor"
PROFILE = "my-apparmor-profile"


def wait_for_http(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return resp.read().decode()
        except OSError:
            time.sleep(1)
    return None


def main():
    keep = "--keep" in sys.argv

    # Create a Docker client
    client = docker.from_env()

    # Build the Docker image
    print("Building image from Dockerfile...")
    _, logs = client.images.build(path=".", tag=IMAGE, rm=True)
    for chunk in logs:
        if "stream" in chunk:
            print("[INFO]", chunk["stream"].rstrip())

    # Remove a container left over from an earlier run
    try:
        client.containers.get(CONTAINER).remove(force=True)
    except docker.errors.NotFound:
        pass

    # Run the container with the AppArmor profile
    print("\nRunning container with AppArmor profile...")
    try:
        container = client.containers.run(
            IMAGE,
            name=CONTAINER,
            ports={"5000/tcp": 5000},
            security_opt=[f"apparmor={PROFILE}"],
            detach=True,
        )
    except docker.errors.APIError as exc:
        sys.exit(f"Could not start the container: {exc.explanation}\n"
                 f"Load the profile first:  sudo apparmor_parser -r -W /etc/apparmor.d/{PROFILE}")
    print(f"Container started: {container.short_id}")

    # Verify AppArmor profile applied
    print("\nInspecting container to verify AppArmor profile...")
    info = client.api.inspect_container(container.id)
    security_opt = info["HostConfig"]["SecurityOpt"]
    active_profile = info.get("AppArmorProfile")
    _, attr = container.exec_run("cat /proc/1/attr/current")
    kernel_view = attr.decode().strip()

    print(f"AppArmor profile applied (HostConfig.SecurityOpt): {security_opt}")
    print(f"AppArmorProfile reported by Docker              : {active_profile}")
    print(f"Kernel confinement of the Flask process (PID 1)  : {kernel_view}")

    body = wait_for_http("http://localhost:5000/")
    print(f"App response on http://localhost:5000/           : {body}")

    ok = active_profile == PROFILE and f"{PROFILE} (enforce)" in kernel_view and body is not None

    if keep:
        print(f"\nContainer '{CONTAINER}' left running (docker rm -f {CONTAINER} to remove it).")
    else:
        print("\nStopping the container...")
        container.stop()
        container.remove()

    print("\nRESULT:", "profile enforced" if ok else "profile NOT enforced")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

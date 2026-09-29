"""Deploys the secured stack with the Docker SDK for Python:

  image secure-flask-app:1.0 -> network auth-net -> volume auth-mongo-data
  -> MongoDB (auth-mongodb) -> Flask app (secure-flask-app) confined by the AppArmor profile flask-auth-profile

Usage:  python deploy_secure_stack.py                 # Linux host with AppArmor (profile must be loaded)
        python deploy_secure_stack.py --no-apparmor   # Docker Desktop (Windows/macOS): run without the profile
"""
import secrets
import sys
import time

from docker.errors import APIError, NotFound

from common import (APP_CONTAINER, APP_DIR, APP_IMAGE, APP_PORT, APP_URL, APPARMOR_PROFILE, DB_CONTAINER, DB_IMAGE,
                    NETWORK, VOLUME, apparmor_supported, client, get_container, wait_for_app)


def replace_container(docker_client, name, **kwargs):
    old = get_container(docker_client, name)
    if old is not None:
        old.remove(force=True)
    return docker_client.containers.run(name=name, detach=True, **kwargs)


def main():
    use_apparmor = "--no-apparmor" not in sys.argv
    docker_client = client()

    if use_apparmor and not apparmor_supported(docker_client):
        sys.exit("This Docker host does not support AppArmor (e.g. Docker Desktop on Windows/macOS).\n"
                 "Run on Ubuntu/Debian for the security part, or use --no-apparmor for the rest of the demo.")

    print(f"1. Building {APP_IMAGE} ...")
    docker_client.images.build(path=str(APP_DIR), tag=APP_IMAGE, rm=True)

    print(f"2. Network '{NETWORK}' and volume '{VOLUME}'")
    if not docker_client.networks.list(names=[NETWORK]):
        docker_client.networks.create(NETWORK, driver="bridge")
    try:
        docker_client.volumes.get(VOLUME)
    except NotFound:
        docker_client.volumes.create(VOLUME)

    print(f"3. MongoDB container '{DB_CONTAINER}' (user data persisted in '{VOLUME}')")
    mongo = replace_container(
        docker_client, DB_CONTAINER, image=DB_IMAGE, network=NETWORK,
        volumes={VOLUME: {"bind": "/data/db", "mode": "rw"}},
        restart_policy={"Name": "unless-stopped"},
    )
    for _ in range(45):
        if mongo.exec_run(["mongosh", "--quiet", "--eval", "db.adminCommand('ping').ok"]).exit_code == 0:
            break
        time.sleep(2)
    else:
        sys.exit(f"MongoDB did not become ready - docker logs {DB_CONTAINER}")

    security_opt = [f"apparmor={APPARMOR_PROFILE}"] if use_apparmor else None
    print(f"4. Flask container '{APP_CONTAINER}' "
          f"({'AppArmor profile ' + APPARMOR_PROFILE if use_apparmor else 'WITHOUT AppArmor'}, no-new-privileges)")
    try:
        replace_container(
            docker_client, APP_CONTAINER, image=APP_IMAGE, network=NETWORK,
            ports={"5000/tcp": APP_PORT},
            environment={
                "MONGO_URI": f"mongodb://{DB_CONTAINER}:27017/authdb",
                "SECRET_KEY": secrets.token_hex(32),
                "ENABLE_FAULT_INJECTION": "1",
            },
            security_opt=(security_opt or []) + ["no-new-privileges:true"],
            cap_drop=["ALL"],
        )
    except APIError as exc:
        sys.exit(f"Could not start the app: {exc.explanation}\n"
                 f"Is the profile loaded?  sudo apparmor_parser -r -W /etc/apparmor.d/{APPARMOR_PROFILE}")

    health = wait_for_app()
    if health is None:
        sys.exit(f"App did not become healthy - docker logs {APP_CONTAINER}")
    print(f"   healthy: {health}")
    print(f"\nOpen {APP_URL}  |  next: python verify_apparmor.py  and  python health_monitor.py")


if __name__ == "__main__":
    main()

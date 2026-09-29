"""Builds the Flask image and starts the whole application with the Docker SDK for Python:

  1. build image crud-flask-app:1.0 from ../app
  2. create the custom bridge network  crud-net
  3. create the named volume           crud-mongo-data
  4. run MongoDB  (crud-mongodb)   on crud-net, data in the volume
  5. run Flask    (crud-flask-app) on crud-net, published on localhost:5000

Usage:  python setup_network.py
"""
import sys

from docker.errors import NotFound

from common import (APP_CONTAINER, APP_DIR, APP_IMAGE, APP_PORT, APP_URL, DB_CONTAINER, DB_IMAGE, NETWORK, VOLUME,
                    client, get_container, wait_for_app, wait_for_mongo)


def ensure_network(docker_client):
    existing = docker_client.networks.list(names=[NETWORK])
    if existing:
        print(f"   network '{NETWORK}' already exists")
        return existing[0]
    network = docker_client.networks.create(NETWORK, driver="bridge")
    print(f"   created bridge network '{NETWORK}' ({network.short_id})")
    return network


def ensure_volume(docker_client):
    try:
        docker_client.volumes.get(VOLUME)
        print(f"   volume '{VOLUME}' already exists (existing data is kept)")
    except NotFound:
        docker_client.volumes.create(VOLUME)
        print(f"   created volume '{VOLUME}'")


def replace_container(docker_client, name, **kwargs):
    old = get_container(docker_client, name)
    if old is not None:
        old.remove(force=True)
    return docker_client.containers.run(name=name, detach=True, **kwargs)


def start_mongo(docker_client):
    container = replace_container(
        docker_client, DB_CONTAINER,
        image=DB_IMAGE,
        network=NETWORK,
        volumes={VOLUME: {"bind": "/data/db", "mode": "rw"}},
        restart_policy={"Name": "unless-stopped"},
    )
    if not wait_for_mongo(container):
        sys.exit("MongoDB did not become ready - check: docker logs " + DB_CONTAINER)
    return container


def start_app(docker_client):
    return replace_container(
        docker_client, APP_CONTAINER,
        image=APP_IMAGE,
        network=NETWORK,
        ports={"5000/tcp": APP_PORT},
        environment={
            "MONGO_URI": f"mongodb://{DB_CONTAINER}:27017/library",   # container name resolved by Docker DNS
            "ENABLE_FAULT_INJECTION": "1",                             # enables POST /admin/fail for the demo
        },
        restart_policy={"Name": "unless-stopped"},
    )


def main():
    docker_client = client()

    print(f"1. Building image {APP_IMAGE} from {APP_DIR} ...")
    docker_client.images.build(path=str(APP_DIR), tag=APP_IMAGE, rm=True)

    print("2. Network")
    ensure_network(docker_client)

    print("3. Volume")
    ensure_volume(docker_client)

    print(f"4. Starting MongoDB container '{DB_CONTAINER}' ({DB_IMAGE}) ...")
    start_mongo(docker_client)
    print("   MongoDB is ready")

    print(f"5. Starting Flask container '{APP_CONTAINER}' ...")
    start_app(docker_client)
    health = wait_for_app()
    if health is None:
        sys.exit("Flask app did not become healthy - check: docker logs " + APP_CONTAINER)
    print(f"   app healthy: {health}")

    print(f"\nDone. Open {APP_URL} in the browser.")
    print("Next: python inspect_network.py | python container_manager.py --watch | python verify_persistence.py")


if __name__ == "__main__":
    main()

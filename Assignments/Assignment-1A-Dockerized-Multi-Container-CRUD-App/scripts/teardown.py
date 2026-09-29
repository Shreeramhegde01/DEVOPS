"""Stops and removes the containers and the network.

Usage:  python teardown.py              # keep the data volume
        python teardown.py --volumes    # also delete the MongoDB data volume
"""
import sys

from docker.errors import NotFound

from common import APP_CONTAINER, DB_CONTAINER, NETWORK, VOLUME, client, get_container


def main():
    docker_client = client()
    for name in (APP_CONTAINER, DB_CONTAINER):
        container = get_container(docker_client, name)
        if container is not None:
            container.remove(force=True)
            print(f"removed container {name}")
    for network in docker_client.networks.list(names=[NETWORK]):
        network.remove()
        print(f"removed network {NETWORK}")
    if "--volumes" in sys.argv:
        try:
            docker_client.volumes.get(VOLUME).remove()
            print(f"removed volume {VOLUME}")
        except NotFound:
            pass


if __name__ == "__main__":
    main()

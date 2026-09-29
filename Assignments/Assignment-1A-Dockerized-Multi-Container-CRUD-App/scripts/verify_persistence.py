"""Proves that MongoDB data survives the database container being destroyed and re-created,
because it lives in the named Docker volume crud-mongo-data.

Usage:  python verify_persistence.py
"""
import sys
import time

from common import DB_CONTAINER, VOLUME, client, get_container, http_json, wait_for_app
from setup_network import start_mongo


def main():
    docker_client = client()
    title = f"Persistence check {time.strftime('%H:%M:%S')}"

    status, book = http_json("POST", "/api/books", {"title": title, "author": "verify_persistence.py"})
    if status != 201:
        sys.exit(f"Could not create a book (HTTP {status}) - is the app running? (setup_network.py)")
    print(f"1. Created book {book['id']} '{title}'")

    old = get_container(docker_client, DB_CONTAINER)
    print(f"2. Stopping and removing MongoDB container {DB_CONTAINER} ({old.short_id}) completely ...")
    old.stop(timeout=30)   # graceful shutdown: mongod flushes its journal to the volume first
    old.remove()
    status, _ = http_json("GET", "/api/books")
    print(f"   while the DB is gone, GET /api/books -> HTTP {status}")

    print(f"3. Creating a brand-new MongoDB container with the same volume '{VOLUME}' ...")
    new = start_mongo(docker_client)
    print(f"   new container {new.short_id} is ready")
    wait_for_app()

    status, books = http_json("GET", "/api/books")
    found = status == 200 and any(b["id"] == book["id"] for b in books)
    print(f"4. GET /api/books -> HTTP {status}, {len(books or [])} book(s)")
    print(f"\nRESULT: {'PASS - data survived the container re-creation' if found else 'FAIL - data lost'}")
    sys.exit(0 if found else 1)


if __name__ == "__main__":
    main()

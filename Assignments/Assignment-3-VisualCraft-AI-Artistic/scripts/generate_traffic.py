"""Sends a realistic mix of requests so the Grafana dashboards have data:
   ~80% valid JPEG uploads (200), ~10% requests without an image (400), ~10% corrupt "images" (500).

Usage:  python generate_traffic.py [--url http://localhost:5001] [--requests 60] [--concurrency 3]
"""
import argparse
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

SAMPLE = Path(__file__).resolve().parent.parent / "tests" / "sample-input.jpg"


def one_request(url, image_bytes):
    roll = random.random()
    started = time.time()
    try:
        if roll < 0.8:
            response = requests.post(f"{url}/styleTransfer", timeout=180,
                                     files={"image": ("photo.jpg", image_bytes, "image/jpeg")})
        elif roll < 0.9:
            response = requests.post(f"{url}/styleTransfer", timeout=60)          # no image -> 400
        else:
            response = requests.post(f"{url}/styleTransfer", timeout=60,          # not a JPEG -> 500
                                     files={"image": ("broken.jpg", b"this is not an image", "image/jpeg")})
        return response.status_code, time.time() - started
    except requests.RequestException:
        return "error", time.time() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5001")
    parser.add_argument("--requests", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()
    url, image = args.url.rstrip("/"), SAMPLE.read_bytes()

    started = time.time()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: one_request(url, image), range(args.requests)))
    elapsed = time.time() - started

    statuses = Counter(status for status, _ in results)
    latencies = sorted(latency for _, latency in results)
    print(f"{len(results)} requests in {elapsed:.1f}s ({len(results) / elapsed:.2f} req/s)")
    print("status codes:", dict(statuses))
    print(f"latency: avg {sum(latencies) / len(latencies):.2f}s, "
          f"p95 {latencies[int(0.95 * (len(latencies) - 1))]:.2f}s, max {latencies[-1]:.2f}s")


if __name__ == "__main__":
    main()

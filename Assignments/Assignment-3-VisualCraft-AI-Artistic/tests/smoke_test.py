"""Post-deployment smoke test for the VisualCraft AI Artistic Style Service (run by Jenkins / GitHub Actions).

  1. waits until the service is up (the AI model needs time to load)
  2. POST /styleTransfer with a JPEG  -> 200, image/jpeg, valid JPEG saved to --output
  3. POST /styleTransfer without image -> 400
  4. GET /metrics exposes styletransfer_requests_total

Usage:  python smoke_test.py [--url http://localhost:5001] [--image sample-input.jpg]
                             [--output ../output/styled_output.jpg] [--wait 240]
"""
import argparse
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def wait_until_ready(url, wait):
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            if requests.get(f"{url}/health", timeout=3).json().get("ai_service") == "up":
                return True
        except (requests.RequestException, ValueError):
            pass
        time.sleep(5)
    return False


def style_transfer(url, image_path, retries=5):
    for attempt in range(1, retries + 1):
        with open(image_path, "rb") as fh:
            response = requests.post(f"{url}/styleTransfer", files={"image": (image_path.name, fh, "image/jpeg")},
                                     timeout=180)
        if response.status_code not in (502, 503, 504):
            return response
        print(f"   attempt {attempt}: HTTP {response.status_code}, retrying ...")
        time.sleep(5)
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5001")
    parser.add_argument("--image", default=str(HERE / "sample-input.jpg"))
    parser.add_argument("--output", default=str(HERE.parent / "output" / "styled_output.jpg"))
    parser.add_argument("--wait", type=int, default=240, help="seconds to wait for the service to come up")
    args = parser.parse_args()
    url, image, output = args.url.rstrip("/"), Path(args.image), Path(args.output)
    failures = []

    print(f"1. Waiting up to {args.wait}s for {url} ...")
    if not wait_until_ready(url, args.wait):
        sys.exit("FAIL: service did not become ready")
    print("   service is up")

    print(f"2. POST /styleTransfer with {image.name} ({image.stat().st_size} bytes)")
    started = time.time()
    response = style_transfer(url, image)
    took = time.time() - started
    is_jpeg = response.content[:3] == b"\xff\xd8\xff"
    print(f"   HTTP {response.status_code}, {response.headers.get('Content-Type')}, "
          f"{len(response.content)} bytes in {took:.2f}s")
    if response.status_code == 200 and is_jpeg:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(response.content)
        print(f"   stylized image saved to {output}")
    else:
        failures.append(f"style transfer returned {response.status_code}")

    print("3. POST /styleTransfer without an image (expect 400)")
    response = requests.post(f"{url}/styleTransfer", timeout=30)
    print(f"   HTTP {response.status_code} {response.text.strip()}")
    if response.status_code != 400:
        failures.append(f"missing image returned {response.status_code}, expected 400")

    print("4. GET /metrics")
    metrics = requests.get(f"{url}/metrics", timeout=10).text
    lines = [line for line in metrics.splitlines() if line.startswith("styletransfer_requests_total")]
    print("   " + "\n   ".join(lines))
    if not lines:
        failures.append("styletransfer_requests_total missing from /metrics")

    if failures:
        sys.exit("FAIL: " + "; ".join(failures))
    print("\nPASS - the AI Artistic Style Service is deployed and working")


if __name__ == "__main__":
    main()

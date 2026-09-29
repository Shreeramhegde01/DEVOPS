"""VisualCraft style API gateway.

The provided AI Artistic Style Service image (urmsandeep/ai-artistic-style-service) has no /metrics endpoint,
so this small gateway sits in front of it: clients call POST /styleTransfer on port 5001 exactly as before,
the gateway forwards the request to the AI container and records Prometheus metrics for every call:

  styletransfer_requests_total{endpoint,method,status}   number of requests, by status code (200/400/500/...)
  styletransfer_request_duration_seconds{endpoint}       latency histogram (-> avg / p50 / p95 / p99)
  styletransfer_requests_in_progress                      requests currently being processed
  styletransfer_upload_bytes                              size of uploaded images
  styletransfer_upstream_up                               1 if the AI container accepts connections
"""
import os
import socket
import time
from urllib.parse import urlparse

import requests
from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "http://ai-artistic-style:5001").rstrip("/")
UPSTREAM_TIMEOUT = float(os.environ.get("UPSTREAM_TIMEOUT", "120"))

REQUESTS = Counter("styletransfer_requests_total", "API requests to the AI Artistic Style Service",
                   ["endpoint", "method", "status"])
LATENCY = Histogram("styletransfer_request_duration_seconds", "Time taken to answer an API request", ["endpoint"],
                    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 21, 34, 60))
IN_PROGRESS = Gauge("styletransfer_requests_in_progress", "Requests currently being processed")
UPLOAD_BYTES = Histogram("styletransfer_upload_bytes", "Size of uploaded images in bytes",
                         buckets=(10e3, 50e3, 100e3, 250e3, 500e3, 1e6, 2.5e6, 5e6, 10e6))
UPSTREAM_UP = Gauge("styletransfer_upstream_up", "1 if the AI Artistic Style Service accepts connections")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


def upstream_reachable():
    target = urlparse(UPSTREAM_URL)
    try:
        with socket.create_connection((target.hostname, target.port or 80), timeout=1):
            return True
    except OSError:
        return False


@app.post("/styleTransfer")
def style_transfer():
    started = time.perf_counter()
    status = 500
    IN_PROGRESS.inc()
    try:
        if request.content_length:
            UPLOAD_BYTES.observe(request.content_length)
        files = {name: (f.filename, f.stream, f.mimetype) for name, f in request.files.items()}
        try:
            upstream = requests.post(f"{UPSTREAM_URL}/styleTransfer", files=files, data=request.form.to_dict(),
                                     timeout=UPSTREAM_TIMEOUT)
        except requests.Timeout:
            status = 504
            return jsonify(error="AI service timed out"), status
        except requests.RequestException as exc:
            status = 502
            return jsonify(error="AI service unavailable", details=str(exc)), status
        status = upstream.status_code
        headers = {k: v for k, v in upstream.headers.items() if k.lower() in ("content-type", "content-disposition")}
        return Response(upstream.content, status=status, headers=headers)
    finally:
        IN_PROGRESS.dec()
        REQUESTS.labels("/styleTransfer", "POST", str(status)).inc()
        LATENCY.labels("/styleTransfer").observe(time.perf_counter() - started)


@app.get("/metrics")
def metrics():
    UPSTREAM_UP.set(1 if upstream_reachable() else 0)
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    """The gateway is alive; also reports whether the AI service is reachable."""
    return jsonify(gateway="ok", ai_service="up" if upstream_reachable() else "down")


@app.get("/")
def index():
    return jsonify(service="VisualCraft AI Artistic Style API",
                   usage="curl -X POST http://localhost:5001/styleTransfer -F image=@photo.jpg --output styled.jpg",
                   metrics="/metrics", health="/health")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

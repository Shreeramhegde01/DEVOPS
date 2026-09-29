"""Simulates delivery metrics for the ZAPPTTO quick-commerce platform and exposes them to Prometheus.

Metrics are served on http://localhost:8000/metrics.
Ranges can be changed without editing code (used in Step 6 - "Simulate Alerts"):
    PENDING_MIN / PENDING_MAX              default 10 / 20
    DELIVERY_TIME_MIN / DELIVERY_TIME_MAX  default 15 / 45 (seconds)
"""
import os
import random
import time

from prometheus_client import start_http_server, Summary, Gauge

PENDING_MIN = int(os.environ.get("PENDING_MIN", 10))
PENDING_MAX = int(os.environ.get("PENDING_MAX", 20))  # Ensure values exceed the alert threshold (10)
DELIVERY_TIME_MIN = float(os.environ.get("DELIVERY_TIME_MIN", 15))
DELIVERY_TIME_MAX = float(os.environ.get("DELIVERY_TIME_MAX", 45))

# Metrics
total_deliveries = Gauge("total_deliveries", "Total number of deliveries")
pending_deliveries = Gauge("pending_deliveries", "Number of pending deliveries")
on_the_way_deliveries = Gauge("on_the_way_deliveries", "Number of deliveries on the way")
average_delivery_time = Summary("average_delivery_time", "Average delivery time in seconds")


# Simulate delivery statuses
def simulate_delivery():
    pending = random.randint(PENDING_MIN, PENDING_MAX)
    on_the_way = random.randint(5, 20)
    delivered = random.randint(30, 70)
    avg_time = random.uniform(DELIVERY_TIME_MIN, DELIVERY_TIME_MAX)

    total = pending + on_the_way + delivered

    print(f"[DEBUG] Total deliveries: {total}")
    print(f"[DEBUG] Pending deliveries: {pending}")
    print(f"[DEBUG] On-the-way deliveries: {on_the_way}")
    print(f"[DEBUG] Average delivery time: {avg_time:.2f} seconds")

    total_deliveries.set(total)
    pending_deliveries.set(pending)
    on_the_way_deliveries.set(on_the_way)
    average_delivery_time.observe(avg_time)


if __name__ == "__main__":
    print("[INFO] Starting the HTTP server on port 8000...")
    start_http_server(8000, addr="0.0.0.0")
    print("[INFO] HTTP server started. Simulating deliveries...")
    while True:
        simulate_delivery()
        print("[INFO] Sleeping for 1 seconds...")
        time.sleep(1)

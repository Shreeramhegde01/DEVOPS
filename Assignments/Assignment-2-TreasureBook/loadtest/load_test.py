"""TreasureBook traffic simulator - a treasure-hunt surge.

Many "adventurers" (threads) add treasures, locations, maps and trails while others explore the graph.
Uses only the Python standard library, so it runs anywhere - on the laptop or inside the cluster as a Job.

Usage:
    python load_test.py --url http://127.0.0.1:30080 --duration 180 --concurrency 30
    python load_test.py --url http://treasurebook-api:5000 --json results.json      (inside the cluster)

Workload mix: 20% POST /node, 10% POST /edge, 30% GET /nodes, 15% GET /node/<id>/neighbors,
              10% GET /stats, 10% GET /node/<id>, 5% GET /path
"""
import argparse
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

NODE_TYPES = ["Treasure", "Location", "Map"]
EDGE_RULES = [("Trail", "Location", "Location"), ("Hidden-At", "Treasure", "Location"), ("Leads-To", "Map", "Treasure")]
ADJECTIVES = ["Golden", "Cursed", "Mystic", "Ancient", "Hidden", "Emerald", "Silent", "Sunken", "Frozen", "Crimson"]
NOUNS = {"Treasure": ["Crown", "Diamond", "Chalice", "Amulet", "Scepter"],
         "Location": ["Cave", "Forest", "Lake", "Temple", "Island"],
         "Map": ["Map", "Scroll", "Chart", "Atlas", "Compass"]}


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.latencies = []
        self.status = Counter()
        self.endpoints = Counter()
        self.pods = Counter()
        self.timeline = defaultdict(int)
        self.start = time.time()

    def record(self, endpoint, status, latency, pod):
        with self.lock:
            self.latencies.append(latency)
            self.status[status] += 1
            self.endpoints[endpoint] += 1
            if pod:
                self.pods[pod] += 1
            self.timeline[int((time.time() - self.start) // 10) * 10] += 1


class Client:
    def __init__(self, base_url, stats):
        self.base = base_url.rstrip("/")
        self.stats = stats

    def call(self, method, path, endpoint, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        started = time.perf_counter()
        status, payload, pod = "error", None, None
        try:
            with urllib.request.urlopen(request, timeout=15) as resp:
                status, payload, pod = resp.status, json.loads(resp.read()), resp.headers.get("X-Served-By")
        except urllib.error.HTTPError as err:
            status, pod = err.code, err.headers.get("X-Served-By")
        except (OSError, ValueError):
            pass
        self.stats.record(endpoint, status, time.perf_counter() - started, pod)
        return status, payload


class World:
    """Node ids created so far, per type (shared by all threads)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.ids = {t: [] for t in NODE_TYPES}

    def add(self, node_type, node_id):
        with self.lock:
            self.ids[node_type].append(node_id)

    def pick(self, node_type):
        with self.lock:
            return random.choice(self.ids[node_type]) if self.ids[node_type] else None


def create_node(client, world, node_type=None):
    node_type = node_type or random.choice(NODE_TYPES)
    name = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS[node_type])} #{random.randint(1, 10**6)}"
    status, body = client.call("POST", "/node", "POST /node",
                               {"type": node_type, "name": name, "properties": {"found": False}})
    if status == 201:
        world.add(node_type, body["id"])


def create_edge(client, world):
    edge_type, from_type, to_type = random.choice(EDGE_RULES)
    source, target = world.pick(from_type), world.pick(to_type)
    if source and target and source != target:
        client.call("POST", "/edge", "POST /edge", {"type": edge_type, "from": source, "to": target})


def one_action(client, world):
    roll = random.random()
    any_node = world.pick(random.choice(NODE_TYPES))
    if roll < 0.20:
        create_node(client, world)
    elif roll < 0.30:
        create_edge(client, world)
    elif roll < 0.60:
        client.call("GET", f"/nodes?type={random.choice(NODE_TYPES)}&limit=20", "GET /nodes")
    elif roll < 0.75 and any_node:
        client.call("GET", f"/node/{any_node}/neighbors", "GET /node/<id>/neighbors")
    elif roll < 0.85:
        client.call("GET", "/stats", "GET /stats")
    elif roll < 0.95 and any_node:
        client.call("GET", f"/node/{any_node}", "GET /node/<id>")
    else:
        a, b = world.pick("Location"), world.pick("Treasure")
        if a and b:
            client.call("GET", "/path?" + urllib.parse.urlencode({"from": a, "to": b}), "GET /path")


def seed(client, world):
    for node_type, count in (("Location", 15), ("Treasure", 15), ("Map", 5)):
        for _ in range(count):
            create_node(client, world, node_type)
    for _ in range(40):
        create_edge(client, world)


def worker(client, world, stop_at):
    while time.time() < stop_at:
        one_action(client, world)


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def report(stats, duration, concurrency):
    lat = [v * 1000 for v in stats.latencies]
    total = len(lat)
    ok = sum(n for s, n in stats.status.items() if isinstance(s, int) and s < 400)
    summary = {
        "duration_s": round(duration, 1),
        "concurrency": concurrency,
        "total_requests": total,
        "throughput_rps": round(total / duration, 1) if duration else 0,
        "success_rate_pct": round(100 * ok / total, 2) if total else 0,
        "status_codes": {str(k): v for k, v in sorted(stats.status.items(), key=str)},
        "latency_ms": {
            "avg": round(statistics.mean(lat), 1) if lat else None,
            "p50": round(percentile(lat, 50), 1) if lat else None,
            "p90": round(percentile(lat, 90), 1) if lat else None,
            "p95": round(percentile(lat, 95), 1) if lat else None,
            "p99": round(percentile(lat, 99), 1) if lat else None,
            "max": round(max(lat), 1) if lat else None,
        },
        "requests_per_endpoint": dict(stats.endpoints.most_common()),
        "requests_per_pod": dict(stats.pods.most_common()),
        "requests_per_10s": {f"{k}-{k + 10}s": v for k, v in sorted(stats.timeline.items())},
    }
    print("\n================ TreasureBook load test ================")
    print(f"Duration        : {summary['duration_s']} s with {concurrency} concurrent adventurers")
    print(f"Total requests  : {total}   Throughput: {summary['throughput_rps']} req/s")
    print(f"Success rate    : {summary['success_rate_pct']} %   Status codes: {summary['status_codes']}")
    print("Latency (ms)    : " + "  ".join(f"{k}={v}" for k, v in summary["latency_ms"].items()))
    print("Per endpoint    :")
    for endpoint, count in summary["requests_per_endpoint"].items():
        print(f"   {endpoint:<28} {count}")
    print(f"Served by {len(stats.pods)} pod(s):")
    for pod, count in summary["requests_per_pod"].items():
        print(f"   {pod:<40} {count}")
    print("Requests per 10 s:", " ".join(str(v) for v in summary["requests_per_10s"].values()))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:30080", help="TreasureBook API base URL")
    parser.add_argument("--duration", type=int, default=120, help="seconds of load (default 120)")
    parser.add_argument("--concurrency", type=int, default=20, help="parallel adventurers (default 20)")
    parser.add_argument("--json", help="also write the summary to this JSON file")
    args = parser.parse_args()

    stats = Stats()
    client, world = Client(args.url, stats), World()
    print(f"Seeding the treasure map at {args.url} ...")
    seed(client, world)

    print(f"Surge: {args.concurrency} adventurers for {args.duration}s ...", flush=True)
    stats = client.stats = Stats()   # measure the surge only, not the seeding
    started = time.time()
    threads = [threading.Thread(target=worker, args=(client, world, started + args.duration), daemon=True)
               for _ in range(args.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    summary = report(stats, time.time() - started, args.concurrency)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"Summary written to {args.json}")


if __name__ == "__main__":
    main()

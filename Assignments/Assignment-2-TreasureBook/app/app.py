"""TreasureBook API - a graph of treasures, locations and maps (nodes) connected by trails, hiding places and
leads (edges), stored in MongoDB. Modelled on Facebook's TAO: objects = nodes, associations = edges.

    Facebook (TAO)  TreasureBook     Endpoint
    User            Treasure         POST /node  {"type": "Treasure", ...}
    Page            Location         POST /node  {"type": "Location", ...}
    Message         Map              POST /node  {"type": "Map", ...}
    Friendship      Trail            POST /edge  {"type": "Trail",     Location -> Location}
    Likes           Hidden-At        POST /edge  {"type": "Hidden-At", Treasure -> Location}
    Comments        Leads-To         POST /edge  {"type": "Leads-To",  Map      -> Treasure}
"""
import os
import socket
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, jsonify, request
from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/treasurebook")

NODE_TYPES = {"treasure": "Treasure", "treasures": "Treasure",
              "location": "Location", "locations": "Location",
              "map": "Map", "maps": "Map"}
# edge type -> (canonical name, allowed source node type, allowed target node type)
EDGE_TYPES = {"trail": ("Trail", "Location", "Location"),
              "hidden-at": ("Hidden-At", "Treasure", "Location"),
              "leads-to": ("Leads-To", "Map", "Treasure")}

app = Flask(__name__)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client.get_default_database(default="treasurebook")
nodes = db["nodes"]
edges = db["edges"]
_indexes = {"ready": False}


def ensure_indexes():
    if not _indexes["ready"]:
        nodes.create_index([("type", ASCENDING), ("name", ASCENDING)])
        edges.create_index([("from", ASCENDING), ("type", ASCENDING)])
        edges.create_index([("to", ASCENDING), ("type", ASCENDING)])
        _indexes["ready"] = True


def now():
    return datetime.now(timezone.utc).isoformat()


def node_json(doc):
    return {"id": str(doc["_id"]), "type": doc["type"], "name": doc["name"],
            "properties": doc.get("properties", {}), "created_at": doc.get("created_at")}


def edge_json(doc):
    return {"id": str(doc["_id"]), "type": doc["type"], "from": str(doc["from"]), "to": str(doc["to"]),
            "properties": doc.get("properties", {}), "created_at": doc.get("created_at")}


def error(message, status=400):
    return jsonify(error=message), status


def limit_arg(default, maximum):
    try:
        return max(1, min(int(request.args.get("limit", default)), maximum))
    except ValueError:
        return default


def find_node(ref):
    """Look a node up by id, or by exact name if the reference is not an ObjectId."""
    if ref is None:
        return None
    try:
        return nodes.find_one({"_id": ObjectId(str(ref))})
    except InvalidId:
        return nodes.find_one({"name": str(ref)})


@app.after_request
def add_pod_header(response):
    response.headers["X-Served-By"] = socket.gethostname()   # shows load balancing across replicas
    return response


@app.errorhandler(PyMongoError)
def database_error(exc):
    return error(f"database unavailable: {exc}", 503)


@app.get("/")
def index():
    return jsonify(service="TreasureBook API", pod=socket.gethostname(),
                   endpoints=["POST /node", "GET /nodes", "GET /node/<id>", "GET /node/<id>/neighbors",
                              "POST /edge", "GET /edges", "GET /path?from=&to=", "GET /graph", "GET /stats",
                              "GET /health", "GET /ready"])


# ---------- Nodes ----------

@app.post("/node")
def create_node():
    data = request.get_json(silent=True) or {}
    node_type = NODE_TYPES.get(str(data.get("type", "")).strip().lower())
    name = str(data.get("name", "")).strip()
    if node_type is None:
        return error("type must be one of: Treasure, Location, Map")
    if not name:
        return error("name is required")
    ensure_indexes()
    doc = {"type": node_type, "name": name, "properties": data.get("properties") or {}, "created_at": now()}
    doc["_id"] = nodes.insert_one(doc).inserted_id
    return jsonify(node_json(doc)), 201


@app.get("/nodes")
def list_nodes():
    query = {}
    if request.args.get("type"):
        node_type = NODE_TYPES.get(request.args["type"].lower())
        if node_type is None:
            return error("unknown node type")
        query["type"] = node_type
    return jsonify([node_json(d) for d in nodes.find(query).sort("_id", -1).limit(limit_arg(100, 1000))])


@app.get("/node/<node_id>")
def get_node(node_id):
    doc = find_node(node_id)
    return jsonify(node_json(doc)) if doc else error("node not found", 404)


@app.get("/node/<node_id>/neighbors")
def neighbors(node_id):
    doc = find_node(node_id)
    if doc is None:
        return error("node not found", 404)
    outgoing = list(edges.find({"from": doc["_id"]}))
    incoming = list(edges.find({"to": doc["_id"]}))
    other_ids = {e["to"] for e in outgoing} | {e["from"] for e in incoming}
    others = {d["_id"]: d for d in nodes.find({"_id": {"$in": list(other_ids)}})}

    def describe(edge, other_id, direction):
        other = others.get(other_id)
        return {"edge": edge["type"], "direction": direction, "node": node_json(other) if other else None}

    return jsonify(node=node_json(doc),
                   neighbors=[describe(e, e["to"], "out") for e in outgoing] +
                             [describe(e, e["from"], "in") for e in incoming])


# ---------- Edges ----------

@app.post("/edge")
def create_edge():
    data = request.get_json(silent=True) or {}
    spec = EDGE_TYPES.get(str(data.get("type", "")).strip().lower())
    if spec is None:
        return error("type must be one of: Trail, Hidden-At, Leads-To")
    edge_type, from_type, to_type = spec
    source, target = find_node(data.get("from")), find_node(data.get("to"))
    if source is None or target is None:
        return error("'from' and 'to' must be existing node ids or names", 404)
    if source["type"] != from_type or target["type"] != to_type:
        return error(f"{edge_type} connects {from_type} -> {to_type}, "
                     f"got {source['type']} -> {target['type']}")
    if source["_id"] == target["_id"]:
        return error("an edge cannot connect a node to itself")
    ensure_indexes()
    doc = {"type": edge_type, "from": source["_id"], "to": target["_id"],
           "properties": data.get("properties") or {}, "created_at": now()}
    doc["_id"] = edges.insert_one(doc).inserted_id
    return jsonify({**edge_json(doc), "from_name": source["name"], "to_name": target["name"]}), 201


@app.get("/edges")
def list_edges():
    query = {}
    if request.args.get("type"):
        spec = EDGE_TYPES.get(request.args["type"].lower())
        if spec is None:
            return error("unknown edge type")
        query["type"] = spec[0]
    return jsonify([edge_json(d) for d in edges.find(query).sort("_id", -1).limit(limit_arg(100, 1000))])


# ---------- Graph queries ----------

@app.get("/path")
def path():
    """Shortest chain of edges (any type, either direction) between two nodes - breadth-first search."""
    start, goal = find_node(request.args.get("from")), find_node(request.args.get("to"))
    if start is None or goal is None:
        return error("from/to must be existing node ids or names", 404)
    previous = {start["_id"]: None}
    frontier = [start["_id"]]
    for _ in range(6):          # explorers do not follow more than 6 hops; one query per level
        if goal["_id"] in previous or not frontier:
            break
        level, frontier = set(frontier), []
        query = {"$or": [{"from": {"$in": list(level)}}, {"to": {"$in": list(level)}}]}
        for e in edges.find(query, {"from": 1, "to": 1, "type": 1}):
            for current, nxt in ((e["from"], e["to"]), (e["to"], e["from"])):
                if current in level and nxt not in previous:
                    previous[nxt] = (current, e["type"])
                    frontier.append(nxt)
    if goal["_id"] not in previous:
        return jsonify(found=False, path=[])
    chain, hops, cursor = [], [], goal["_id"]
    while cursor is not None:
        chain.append(cursor)
        step = previous[cursor]
        if step:
            hops.append(step[1])
        cursor = step[0] if step else None
    chain.reverse()
    hops.reverse()
    docs = {d["_id"]: d for d in nodes.find({"_id": {"$in": chain}})}
    return jsonify(found=True, hops=len(hops), path=[docs[c]["name"] for c in chain], via=hops)


@app.get("/graph")
def graph():
    limit = limit_arg(500, 2000)
    return jsonify(nodes=[node_json(d) for d in nodes.find().limit(limit)],
                   edges=[edge_json(d) for d in edges.find().limit(limit)])


@app.get("/stats")
def stats():
    group = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}]
    return jsonify(nodes={d["_id"]: d["count"] for d in nodes.aggregate(group)},
                   edges={d["_id"]: d["count"] for d in edges.aggregate(group)},
                   served_by=socket.gethostname())


# ---------- Probes ----------

@app.get("/health")
def health():
    """Liveness: the process is up (independent of MongoDB, so a DB outage does not restart every pod)."""
    return jsonify(status="alive", pod=socket.gethostname())


@app.get("/ready")
def ready():
    """Readiness: only receive traffic when MongoDB is reachable."""
    try:
        db.command("ping")
    except PyMongoError as exc:
        return jsonify(status="not ready", database=str(exc)), 503
    return jsonify(status="ready", database="up")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

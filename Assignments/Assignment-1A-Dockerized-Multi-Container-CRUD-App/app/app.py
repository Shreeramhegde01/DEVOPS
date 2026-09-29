"""Library catalogue - a Flask CRUD web application backed by MongoDB (running in its own container)."""
import os

from bson import ObjectId
from bson.errors import InvalidId
from flask import Flask, abort, jsonify, render_template, request
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/library")
FAULT_INJECTION = os.environ.get("ENABLE_FAULT_INJECTION") == "1"
FIELDS = ("title", "author", "year")

app = Flask(__name__)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client.get_default_database(default="library")
books = db["books"]
state = {"forced_unhealthy": False}


def serialize(doc):
    return {"id": str(doc["_id"]), **{field: doc.get(field) for field in FIELDS}}


def parse_book(data, partial=False):
    """Validate a JSON body; returns (book, error)."""
    if not isinstance(data, dict):
        return None, "a JSON object is required"
    book = {field: data[field] for field in FIELDS if field in data}
    if not partial and not str(book.get("title", "")).strip():
        return None, "'title' is required"
    if "year" in book and book["year"] not in (None, ""):
        try:
            book["year"] = int(book["year"])
        except (TypeError, ValueError):
            return None, "'year' must be a number"
    if partial and not book:
        return None, f"nothing to update - send at least one of {', '.join(FIELDS)}"
    return book, None


def object_id(book_id):
    try:
        return ObjectId(book_id)
    except InvalidId:
        abort(404)


@app.errorhandler(404)
def not_found(_):
    return jsonify(error="not found"), 404


@app.errorhandler(PyMongoError)
def database_error(exc):
    return jsonify(error="database unavailable", details=str(exc)), 503


@app.get("/")
def index():
    return render_template("index.html")


# ---------- CRUD API ----------

@app.post("/api/books")
def create_book():
    book, error = parse_book(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400
    result = books.insert_one(book)
    return jsonify(serialize({"_id": result.inserted_id, **book})), 201


@app.get("/api/books")
def list_books():
    return jsonify([serialize(doc) for doc in books.find().sort("_id", 1)])


@app.get("/api/books/<book_id>")
def get_book(book_id):
    doc = books.find_one({"_id": object_id(book_id)})
    if doc is None:
        abort(404)
    return jsonify(serialize(doc))


@app.put("/api/books/<book_id>")
def update_book(book_id):
    changes, error = parse_book(request.get_json(silent=True), partial=True)
    if error:
        return jsonify(error=error), 400
    doc = books.find_one_and_update(
        {"_id": object_id(book_id)}, {"$set": changes}, return_document=ReturnDocument.AFTER
    )
    if doc is None:
        abort(404)
    return jsonify(serialize(doc))


@app.delete("/api/books/<book_id>")
def delete_book(book_id):
    result = books.delete_one({"_id": object_id(book_id)})
    if result.deleted_count == 0:
        abort(404)
    return jsonify(deleted=book_id)


# ---------- Operations ----------

@app.get("/health")
def health():
    """Used by the Docker HEALTHCHECK and by scripts/container_manager.py."""
    if state["forced_unhealthy"]:
        return jsonify(status="unhealthy", reason="fault injected via /admin/fail"), 500
    try:
        db.command("ping")
    except PyMongoError as exc:
        return jsonify(status="unhealthy", database="down", details=str(exc)), 503
    return jsonify(status="healthy", database="up", books=books.count_documents({}))


@app.post("/admin/fail")
def inject_fault():
    """Demo only (ENABLE_FAULT_INJECTION=1): make /health fail so the auto-restart can be shown."""
    if not FAULT_INJECTION:
        abort(404)
    state["forced_unhealthy"] = True
    return jsonify(message="health endpoint will now report unhealthy until the container restarts")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

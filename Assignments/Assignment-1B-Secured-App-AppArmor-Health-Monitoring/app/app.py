"""SecureAuth - Flask user registration / login backed by MongoDB (separate container)."""
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/authdb")
FAULT_INJECTION = os.environ.get("ENABLE_FAULT_INJECTION") == "1"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LENGTH = 8

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
db = client.get_default_database(default="authdb")
users = db["users"]
state = {"login_broken": False}
_index_ready = {"done": False}


def ensure_indexes():
    """Unique usernames - created lazily so the app can start before MongoDB is up."""
    if not _index_ready["done"]:
        users.create_index("username", unique=True)
        _index_ready["done"] = True


def validate(username, password):
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3-32 characters: letters, digits, _ . -"
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    return None


def register_user(username, password):
    """Returns (ok, error)."""
    error = validate(username, password)
    if error:
        return False, error
    ensure_indexes()
    try:
        users.insert_one({
            "username": username,
            "password_hash": generate_password_hash(password),   # salted hash, never the plain password
            "created_at": datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        return False, "Username already taken"
    return True, None


def authenticate(username, password):
    if state["login_broken"]:
        raise RuntimeError("login service failure (fault injected)")
    user = users.find_one({"username": username})
    return user is not None and check_password_hash(user["password_hash"], password)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


@app.errorhandler(PyMongoError)
def database_error(exc):
    if request.path.startswith("/api/"):
        return jsonify(error="database unavailable"), 503
    return render_template("message.html", title="Service unavailable",
                           message="The user database is not reachable. Please try again shortly."), 503


# ---------- Web pages ----------

@app.get("/")
def index():
    return redirect(url_for("dashboard" if "username" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        ok, error = register_user(request.form.get("username", "").strip(), request.form.get("password", ""))
        if ok:
            flash("Account created - please log in.", "success")
            return redirect(url_for("login"))
        flash(error, "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if authenticate(username, request.form.get("password", "")):
            session.clear()
            session["username"] = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html")


@app.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session["username"], user_count=users.count_documents({}))


@app.get("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))


# ---------- JSON API (used by scripts and tests) ----------

@app.post("/api/register")
def api_register():
    data = request.get_json(silent=True) or {}
    ok, error = register_user(str(data.get("username", "")).strip(), str(data.get("password", "")))
    if ok:
        return jsonify(message="registered", username=data["username"]), 201
    return jsonify(error=error), 409 if error == "Username already taken" else 400


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    try:
        ok = authenticate(str(data.get("username", "")).strip(), str(data.get("password", "")))
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 500
    if not ok:
        return jsonify(error="invalid credentials"), 401
    return jsonify(message="login successful", username=data["username"])


# ---------- Operations ----------

@app.get("/health")
def health():
    """Healthy = database reachable AND the login service works."""
    if state["login_broken"]:
        return jsonify(status="unhealthy", login_service="failing"), 503
    try:
        db.command("ping")
        users.find_one({}, {"_id": 1})
    except PyMongoError as exc:
        return jsonify(status="unhealthy", database="down", details=str(exc)), 503
    return jsonify(status="healthy", database="up", login_service="ok")


@app.post("/admin/fail")
def inject_fault():
    """Demo only (ENABLE_FAULT_INJECTION=1): break the login service to trigger the health monitor."""
    if not FAULT_INJECTION:
        abort(404)
    state["login_broken"] = True
    return jsonify(message="login service is now failing until the container is restarted")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

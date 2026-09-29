"""Unit tests for registration, login and health. MongoDB is replaced by mongomock."""
import mongomock
import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch):
    fake_db = mongomock.MongoClient().db
    monkeypatch.setattr(app_module, "db", fake_db)
    monkeypatch.setattr(app_module, "users", fake_db["users"])
    monkeypatch.setitem(app_module._index_ready, "done", False)
    monkeypatch.setitem(app_module.state, "login_broken", False)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def api_register(client, username="alice", password="s3cure-pass"):
    return client.post("/api/register", json={"username": username, "password": password})


def test_register_and_login(client):
    assert api_register(client).status_code == 201
    response = client.post("/api/login", json={"username": "alice", "password": "s3cure-pass"})
    assert response.status_code == 200
    assert response.get_json()["message"] == "login successful"


def test_password_is_hashed(client):
    api_register(client)
    stored = app_module.users.find_one({"username": "alice"})
    assert "s3cure-pass" not in stored["password_hash"]


def test_duplicate_username(client):
    api_register(client)
    assert api_register(client).status_code == 409


def test_validation(client):
    assert api_register(client, username="a", password="s3cure-pass").status_code == 400
    assert api_register(client, username="bob", password="short").status_code == 400


def test_wrong_password(client):
    api_register(client)
    assert client.post("/api/login", json={"username": "alice", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/login", json={"username": "nobody", "password": "whatever1"}).status_code == 401


def test_web_flow(client):
    response = client.post("/register", data={"username": "carol", "password": "carol-pass-1"})
    assert response.status_code == 302
    response = client.post("/login", data={"username": "carol", "password": "carol-pass-1"}, follow_redirects=True)
    assert b"Welcome, carol!" in response.data
    assert b"Log in" in client.get("/logout", follow_redirects=True).data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_health_and_fault_injection(client, monkeypatch):
    assert client.get("/health").get_json() == {"status": "healthy", "database": "up", "login_service": "ok"}

    monkeypatch.setattr(app_module, "FAULT_INJECTION", True)
    api_register(client)
    assert client.post("/admin/fail").status_code == 200
    assert client.get("/health").status_code == 503
    assert client.post("/api/login", json={"username": "alice", "password": "s3cure-pass"}).status_code == 500


def test_fault_injection_disabled_by_default(client, monkeypatch):
    monkeypatch.setattr(app_module, "FAULT_INJECTION", False)
    assert client.post("/admin/fail").status_code == 404

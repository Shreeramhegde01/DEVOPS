"""Unit tests for the CRUD API. MongoDB is replaced by mongomock, so no database is needed."""
import mongomock
import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch):
    fake_db = mongomock.MongoClient().db
    monkeypatch.setattr(app_module, "db", fake_db)
    monkeypatch.setattr(app_module, "books", fake_db["books"])
    app_module.state["forced_unhealthy"] = False
    return app_module.app.test_client()


def create(client, **book):
    return client.post("/api/books", json=book)


def test_create_and_read(client):
    response = create(client, title="The Phoenix Project", author="Gene Kim", year="2013")
    assert response.status_code == 201
    book = response.get_json()
    assert book["year"] == 2013

    assert client.get(f"/api/books/{book['id']}").get_json()["title"] == "The Phoenix Project"
    assert len(client.get("/api/books").get_json()) == 1


def test_title_is_required(client):
    assert create(client, author="Nobody").status_code == 400


def test_invalid_year(client):
    assert create(client, title="Accelerate", year="soon").status_code == 400


def test_update(client):
    book_id = create(client, title="Site Reliability Engineering").get_json()["id"]
    response = client.put(f"/api/books/{book_id}", json={"author": "Google", "year": 2016})
    assert response.status_code == 200
    assert response.get_json()["author"] == "Google"


def test_update_unknown_id(client):
    assert client.put("/api/books/000000000000000000000000", json={"title": "x"}).status_code == 404


def test_delete(client):
    book_id = create(client, title="The DevOps Handbook").get_json()["id"]
    assert client.delete(f"/api/books/{book_id}").status_code == 200
    assert client.get(f"/api/books/{book_id}").status_code == 404


def test_malformed_id(client):
    assert client.get("/api/books/not-an-id").status_code == 404


def test_health_and_fault_injection(client, monkeypatch):
    assert client.get("/health").get_json()["status"] == "healthy"

    monkeypatch.setattr(app_module, "FAULT_INJECTION", False)
    assert client.post("/admin/fail").status_code == 404

    monkeypatch.setattr(app_module, "FAULT_INJECTION", True)
    assert client.post("/admin/fail").status_code == 200
    assert client.get("/health").status_code == 500


def test_index_page(client):
    assert b"Library Catalogue" in client.get("/").data

"""Unit tests for the gateway - the AI service is replaced by fakes, so these run before any deployment."""
import io
import sys
from pathlib import Path

import pytest
import requests
from prometheus_client import REGISTRY

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as gateway  # noqa: E402


class FakeResponse:
    def __init__(self, status_code, content=b"", content_type="application/json"):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Type": content_type, "Server": "Werkzeug"}


def count(status):
    labels = {"endpoint": "/styleTransfer", "method": "POST", "status": str(status)}
    return REGISTRY.get_sample_value("styletransfer_requests_total", labels) or 0


def upload(client, field="image"):
    data = {field: (io.BytesIO(b"\xff\xd8\xff\xe0fake-jpeg"), "photo.jpg", "image/jpeg")}
    return client.post("/styleTransfer", data=data, content_type="multipart/form-data")


@pytest.fixture
def client():
    return gateway.app.test_client()


def test_successful_transfer_is_proxied_and_counted(client, monkeypatch):
    captured = {}

    def fake_post(url, files, data, timeout):
        captured.update(url=url, files=files)
        return FakeResponse(200, b"\xff\xd8styled", "image/jpeg")

    monkeypatch.setattr(gateway.requests, "post", fake_post)
    before = count(200)

    response = upload(client)

    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"
    assert response.data == b"\xff\xd8styled"
    assert captured["url"].endswith("/styleTransfer")
    assert "image" in captured["files"]
    assert "Server" not in response.headers          # only content headers are passed through
    assert count(200) == before + 1


def test_missing_image_returns_upstream_400(client, monkeypatch):
    monkeypatch.setattr(gateway.requests, "post",
                        lambda *a, **k: FakeResponse(400, b'{"error": "No image uploaded"}'))
    before = count(400)
    response = client.post("/styleTransfer")
    assert response.status_code == 400
    assert response.get_json()["error"] == "No image uploaded"
    assert count(400) == before + 1


def test_upstream_failure_500_is_counted(client, monkeypatch):
    monkeypatch.setattr(gateway.requests, "post",
                        lambda *a, **k: FakeResponse(500, b'{"error": "Style transfer failed"}'))
    before = count(500)
    assert upload(client).status_code == 500
    assert count(500) == before + 1


def test_ai_service_down_returns_502(client, monkeypatch):
    def refuse(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(gateway.requests, "post", refuse)
    before = count(502)
    response = upload(client)
    assert response.status_code == 502
    assert response.get_json()["error"] == "AI service unavailable"
    assert count(502) == before + 1


def test_ai_service_timeout_returns_504(client, monkeypatch):
    def slow(*args, **kwargs):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(gateway.requests, "post", slow)
    assert upload(client).status_code == 504


def test_latency_and_in_progress_metrics(client, monkeypatch):
    monkeypatch.setattr(gateway.requests, "post", lambda *a, **k: FakeResponse(200, b"x", "image/jpeg"))
    observations = REGISTRY.get_sample_value("styletransfer_request_duration_seconds_count",
                                             {"endpoint": "/styleTransfer"}) or 0
    upload(client)
    assert REGISTRY.get_sample_value("styletransfer_request_duration_seconds_count",
                                     {"endpoint": "/styleTransfer"}) == observations + 1
    assert REGISTRY.get_sample_value("styletransfer_requests_in_progress") == 0


def test_metrics_endpoint(client, monkeypatch):
    monkeypatch.setattr(gateway, "upstream_reachable", lambda: False)
    body = client.get("/metrics").data.decode()
    assert "styletransfer_requests_total" in body
    assert "styletransfer_request_duration_seconds_bucket" in body
    assert "styletransfer_upstream_up 0.0" in body


def test_health(client, monkeypatch):
    monkeypatch.setattr(gateway, "upstream_reachable", lambda: True)
    assert client.get("/health").get_json() == {"gateway": "ok", "ai_service": "up"}

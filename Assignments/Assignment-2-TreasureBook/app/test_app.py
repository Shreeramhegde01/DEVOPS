"""Unit tests for the TreasureBook graph API (MongoDB replaced by mongomock)."""
import mongomock
import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch):
    fake_db = mongomock.MongoClient().db
    monkeypatch.setattr(app_module, "db", fake_db)
    monkeypatch.setattr(app_module, "nodes", fake_db["nodes"])
    monkeypatch.setattr(app_module, "edges", fake_db["edges"])
    monkeypatch.setitem(app_module._indexes, "ready", False)
    return app_module.app.test_client()


def node(client, node_type, name):
    response = client.post("/node", json={"type": node_type, "name": name})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def edge(client, edge_type, source, target):
    return client.post("/edge", json={"type": edge_type, "from": source, "to": target})


@pytest.fixture
def world(client):
    """The example graph from the assignment's analogy table."""
    ids = {
        "crown": node(client, "Treasures", "Golden Crown")["id"],
        "diamond": node(client, "Treasure", "Cursed Diamond")["id"],
        "cave": node(client, "Location", "Cave of Wonders")["id"],
        "forest": node(client, "Location", "Forest of Secrets")["id"],
        "lake": node(client, "Location", "Mystic Lake")["id"],
        "map": node(client, "Map", "Mystic Map")["id"],
    }
    assert edge(client, "Hidden-At", ids["crown"], ids["cave"]).status_code == 201
    assert edge(client, "Trail", ids["forest"], ids["lake"]).status_code == 201
    assert edge(client, "Trail", ids["lake"], ids["cave"]).status_code == 201
    assert edge(client, "Leads-to", ids["map"], ids["diamond"]).status_code == 201
    return ids


def test_node_types_are_normalised(client):
    assert node(client, "treasures", "Golden Crown")["type"] == "Treasure"
    assert client.post("/node", json={"type": "Dragon", "name": "Smaug"}).status_code == 400
    assert client.post("/node", json={"type": "Map"}).status_code == 400


def test_edges_accept_names_and_validate_types(client, world):
    response = edge(client, "Hidden-At", "Cursed Diamond", "Forest of Secrets")
    assert response.status_code == 201
    assert response.get_json()["from_name"] == "Cursed Diamond"

    wrong = edge(client, "Hidden-At", world["cave"], world["crown"])        # Location -> Treasure is invalid
    assert wrong.status_code == 400
    assert edge(client, "Trail", world["forest"], "Atlantis").status_code == 404
    assert edge(client, "Teleport", world["forest"], world["lake"]).status_code == 400


def test_list_and_filter(client, world):
    assert len(client.get("/nodes").get_json()) == 6
    assert {n["name"] for n in client.get("/nodes?type=Location").get_json()} == \
        {"Cave of Wonders", "Forest of Secrets", "Mystic Lake"}
    assert len(client.get("/edges?type=Trail").get_json()) == 2


def test_neighbors(client, world):
    data = client.get(f"/node/{world['cave']}/neighbors").get_json()
    assert {(n["edge"], n["node"]["name"]) for n in data["neighbors"]} == \
        {("Hidden-At", "Golden Crown"), ("Trail", "Mystic Lake")}


def test_path(client, world):
    data = client.get("/path?from=Forest of Secrets&to=Golden Crown").get_json()
    assert data["found"] is True
    assert data["path"] == ["Forest of Secrets", "Mystic Lake", "Cave of Wonders", "Golden Crown"]
    assert data["via"] == ["Trail", "Trail", "Hidden-At"]
    assert client.get("/path?from=Golden Crown&to=Mystic Map").get_json()["found"] is False


def test_stats_graph_and_probes(client, world):
    stats = client.get("/stats").get_json()
    assert stats["nodes"] == {"Treasure": 2, "Location": 3, "Map": 1}
    assert stats["edges"]["Trail"] == 2
    assert len(client.get("/graph").get_json()["edges"]) == 4
    assert client.get("/health").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 200 and "X-Served-By" in response.headers


def test_unknown_node(client):
    assert client.get("/node/000000000000000000000000").status_code == 404
    assert client.get("/node/NoSuchPlace").status_code == 404

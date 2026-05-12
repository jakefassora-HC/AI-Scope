"""Tests for the /api/graph Flask route."""
from app import app


def test_api_graph_returns_200_and_shape():
    client = app.test_client()
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "nodes" in data
    assert "edges" in data
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_api_graph_always_includes_home_node():
    client = app.test_client()
    resp = client.get("/api/graph")
    data = resp.get_json()
    home_nodes = [n for n in data["nodes"] if n.get("type") == "home"]
    assert len(home_nodes) == 1
    assert home_nodes[0]["id"] == "home"


def test_api_graph_node_types_are_valid():
    client = app.test_client()
    resp = client.get("/api/graph")
    data = resp.get_json()
    valid_types = {"home", "config", "repo", "worktree", "process"}
    for n in data["nodes"]:
        assert n.get("type") in valid_types, f"unexpected type: {n}"

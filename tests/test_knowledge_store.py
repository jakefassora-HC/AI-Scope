import sqlite3
import pytest
from pathlib import Path
from scope.knowledge_store import KnowledgeStore


@pytest.fixture
def store(tmp_path):
    db = tmp_path / "knowledge.db"
    return KnowledgeStore(db)


def test_upsert_entity_creates_row(store):
    store.upsert_entity("U123", "person", "Jake Fassora", {"department": "AI"})
    entities = store.list_entities()
    assert len(entities) == 1
    assert entities[0]["name"] == "Jake Fassora"
    assert entities[0]["type"] == "person"


def test_upsert_entity_is_idempotent(store):
    store.upsert_entity("U123", "person", "Jake Fassora", {"department": "AI"})
    store.upsert_entity("U123", "person", "Jake Fassora", {"department": "Engineering"})
    entities = store.list_entities()
    assert len(entities) == 1
    assert entities[0]["metadata"]["department"] == "Engineering"


def test_add_relationship_creates_edge(store):
    store.upsert_entity("U123", "person", "Jake", {})
    store.upsert_entity("P456", "project", "Scope", {})
    store.add_relationship("U123", "P456", "WORKS_ON", {"since": "2026-01"})
    rels = store.list_relationships()
    assert len(rels) == 1
    assert rels[0]["relation"] == "WORKS_ON"


def test_list_entities_since_filters_by_time(store):
    import time
    store.upsert_entity("A1", "person", "Alice", {})
    time.sleep(0.01)
    cutoff = time.time()
    time.sleep(0.01)
    store.upsert_entity("B2", "project", "Bob", {})
    recent = store.list_entities(since=cutoff)
    assert len(recent) == 1
    assert recent[0]["id"] == "B2"


def test_add_raw_episode_stores_text(store):
    store.add_raw_episode("slack", "msg-001", "Jake shipped the scope graph tab", {"channel": "#shipped"})
    episodes = store.list_raw_episodes()
    assert len(episodes) == 1
    assert "scope graph" in episodes[0]["content"]

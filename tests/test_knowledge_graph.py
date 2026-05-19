import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_mock_graphiti():
    g = MagicMock()
    g.add_episode = AsyncMock()
    g.search = AsyncMock(return_value=[])
    g.build_indices_and_constraints = AsyncMock()
    g.close = MagicMock()
    return g


def test_build_graph_calls_add_episode_per_raw_episode():
    from scope.knowledge_store import KnowledgeStore
    from scope.knowledge_graph import KnowledgeGraph
    import tempfile, pathlib, asyncio

    with tempfile.TemporaryDirectory() as tmp:
        store = KnowledgeStore(pathlib.Path(tmp) / "k.db")
        store.add_raw_episode("slack", "s1", "Jake shipped the scope graph tab", {"channel": "#shipped"})
        store.add_raw_episode("miro", "m1", "Board: Toolshed architecture with sticky notes", {"board": "abc"})

        mock_g = make_mock_graphiti()
        with patch("scope.knowledge_graph.Graphiti", return_value=mock_g):
            kg = KnowledgeGraph(store, neo4j_uri="bolt://localhost:7687",
                                neo4j_user="neo4j", neo4j_password="scopepassword")
            asyncio.get_event_loop().run_until_complete(kg.sync())

        assert mock_g.add_episode.call_count == 2


def test_to_d3_returns_nodes_and_links():
    from scope.knowledge_graph import KnowledgeGraph
    from scope.knowledge_store import KnowledgeStore
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        store = KnowledgeStore(pathlib.Path(tmp) / "k.db")
        store.upsert_entity("A", "person", "Jake", {})
        store.upsert_entity("B", "project", "Scope", {})
        store.add_relationship("A", "B", "WORKS_ON", {})

        mock_g = make_mock_graphiti()
        with patch("scope.knowledge_graph.Graphiti", return_value=mock_g):
            kg = KnowledgeGraph(store)
            result = kg.to_d3()

        assert len(result["nodes"]) == 2
        assert len(result["links"]) == 1
        assert result["links"][0]["relation"] == "WORKS_ON"

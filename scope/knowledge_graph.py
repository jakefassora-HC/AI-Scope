"""Graphiti knowledge graph — syncs episodes from KnowledgeStore, exposes D3 payload."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from scope.knowledge_store import KnowledgeStore

_DEFAULT_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_DEFAULT_USER = os.getenv("NEO4J_USER", "neo4j")
_DEFAULT_PASS = os.getenv("NEO4J_PASSWORD", "scopepassword")


class KnowledgeGraph:
    def __init__(
        self,
        store: KnowledgeStore,
        neo4j_uri: str = _DEFAULT_URI,
        neo4j_user: str = _DEFAULT_USER,
        neo4j_password: str = _DEFAULT_PASS,
    ) -> None:
        self._store = store
        self._graphiti = Graphiti(neo4j_uri, neo4j_user, neo4j_password)

    async def sync(self) -> int:
        """Push unprocessed raw episodes to Graphiti. Returns count added."""
        episodes = self._store.list_raw_episodes()
        count = 0
        for ep in episodes:
            await self._graphiti.add_episode(
                name=f"{ep['source']}:{ep['source_id']}",
                episode_body=ep["content"],
                source=EpisodeType.text,
                source_description=f"Ingested from {ep['source']}",
                group_id="scope-cockpit",
            )
            count += 1
        return count

    def sync_blocking(self) -> int:
        """Sync in a blocking context (for Flask route handlers)."""
        return asyncio.get_event_loop().run_until_complete(self.sync())

    def to_d3(self) -> dict[str, Any]:
        """Return nodes + links payload ready for D3 force graph.

        Falls back to the SQLite store when Neo4j is unavailable so the UI
        always renders something.
        """
        entities = self._store.list_entities()
        relationships = self._store.list_relationships()

        nodes = [
            {
                "id": e["id"],
                "name": e["name"],
                "type": e["type"],
                "metadata": e["metadata"],
            }
            for e in entities
        ]
        links = [
            {
                "source": r["source_id"],
                "target": r["target_id"],
                "relation": r["relation"],
                "metadata": r["metadata"],
            }
            for r in relationships
        ]
        return {"nodes": nodes, "links": links}

    def close(self) -> None:
        self._graphiti.close()

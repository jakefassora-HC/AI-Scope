"""SQLite store for raw ingested knowledge — entities, relationships, episodes."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


_DEFAULT_DB = Path.home() / ".scope" / "knowledge.db"


class KnowledgeStore:
    def __init__(self, db_path: Path = _DEFAULT_DB) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id       TEXT PRIMARY KEY,
                type     TEXT NOT NULL,
                name     TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                updated  REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relationships (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id  TEXT NOT NULL REFERENCES entities(id),
                target_id  TEXT NOT NULL REFERENCES entities(id),
                relation   TEXT NOT NULL,
                metadata   TEXT NOT NULL DEFAULT '{}',
                created    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS raw_episodes (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                source    TEXT NOT NULL,
                source_id TEXT NOT NULL UNIQUE,
                content   TEXT NOT NULL,
                metadata  TEXT NOT NULL DEFAULT '{}',
                created   REAL NOT NULL
            );
        """)
        self._conn.commit()

    def upsert_entity(self, id: str, type: str, name: str, metadata: dict) -> None:
        self._conn.execute(
            """INSERT INTO entities (id, type, name, metadata, updated)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 type=excluded.type, name=excluded.name,
                 metadata=excluded.metadata, updated=excluded.updated""",
            (id, type, name, json.dumps(metadata), time.time()),
        )
        self._conn.commit()

    def list_entities(self, since: float | None = None) -> list[dict]:
        if since is not None:
            rows = self._conn.execute(
                "SELECT * FROM entities WHERE updated > ?", (since,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM entities").fetchall()
        return [
            {**dict(r), "metadata": json.loads(r["metadata"])} for r in rows
        ]

    def add_relationship(
        self, source_id: str, target_id: str, relation: str, metadata: dict
    ) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO relationships
               (source_id, target_id, relation, metadata, created)
               VALUES (?, ?, ?, ?, ?)""",
            (source_id, target_id, relation, json.dumps(metadata), time.time()),
        )
        self._conn.commit()

    def list_relationships(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM relationships").fetchall()
        return [{**dict(r), "metadata": json.loads(r["metadata"])} for r in rows]

    def add_raw_episode(
        self, source: str, source_id: str, content: str, metadata: dict
    ) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO raw_episodes
               (source, source_id, content, metadata, created)
               VALUES (?, ?, ?, ?, ?)""",
            (source, source_id, content, json.dumps(metadata), time.time()),
        )
        self._conn.commit()

    def list_raw_episodes(self, limit: int = 200) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM raw_episodes ORDER BY created DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{**dict(r), "metadata": json.loads(r["metadata"])} for r in rows]

    def close(self) -> None:
        self._conn.close()

"""
Memory module — shared + per-agent.

Two layers:
  * Short-term (turn buffer) per conversation
  * Long-term vector memory via Chroma + sentence-transformers
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("memory")

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except Exception:  # pragma: no cover - optional during early install
    chromadb = None
    ChromaSettings = None


class TurnBuffer:
    """Sliding window of recent messages per (agent, session)."""

    def __init__(self, max_turns: int = 32) -> None:
        self._store: dict[str, deque[dict]] = {}
        self.max_turns = max_turns

    def add(self, scope: str, role: str, content: str) -> None:
        buf = self._store.setdefault(scope, deque(maxlen=self.max_turns))
        buf.append({"role": role, "content": content, "ts": time.time()})

    def messages(self, scope: str) -> list[dict]:
        """Return clean role/content dicts (drop internal ts field for API safety)."""
        return [{"role": m["role"], "content": m["content"]} for m in self._store.get(scope, [])]

    def clear(self, scope: str) -> None:
        self._store.pop(scope, None)


class VectorMemory:
    """Long-term memory backed by Chroma."""

    def __init__(self, persist_dir: Path | None = None) -> None:
        self.persist_dir = persist_dir or (ROOT / ".cache" / "chroma")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        if chromadb is None:
            log.warning("chromadb not installed — vector memory disabled.")
            self.client = None
            return
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

    def _coll(self, name: str):
        return self.client.get_or_create_collection(name=name)

    def remember(self, namespace: str, text: str, metadata: dict | None = None) -> str:
        if not self.client:
            return ""
        doc_id = str(uuid.uuid4())
        coll = self._coll(namespace)
        coll.add(documents=[text], metadatas=[metadata or {}], ids=[doc_id])
        return doc_id

    def recall(self, namespace: str, query: str, k: int = 5) -> list[dict]:
        if not self.client:
            return []
        coll = self._coll(namespace)
        try:
            res = coll.query(query_texts=[query], n_results=k)
        except Exception as exc:  # noqa: BLE001
            log.warning(f"vector recall failed: {exc}")
            return []
        out = []
        for doc, meta in zip(
            res.get("documents", [[]])[0], res.get("metadatas", [[]])[0]
        ):
            out.append({"text": doc, "meta": meta or {}})
        return out


class Memory:
    """Unified short-term + long-term memory."""

    def __init__(self) -> None:
        self.turn_buffer = TurnBuffer()
        self.vector = VectorMemory()

    # short term
    def push(self, scope: str, role: str, content: str) -> None:
        self.turn_buffer.add(scope, role, content)

    def history(self, scope: str) -> list[dict]:
        return self.turn_buffer.messages(scope)

    # long term
    def remember(self, namespace: str, text: str, metadata: dict | None = None) -> str:
        return self.vector.remember(namespace, text, metadata)

    def recall(self, namespace: str, query: str, k: int = 5) -> list[dict[str, Any]]:
        return self.vector.recall(namespace, query, k)

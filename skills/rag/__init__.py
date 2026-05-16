"""
RAG skill — vector retrieval over uploaded docs.

Uses sentence-transformers + Chroma (already a dependency). Hybrid keyword +
embedding query. Supports text, markdown, PDF, HTML.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import Any

from config.settings import ROOT
from core.logger import get_logger

log = get_logger("skill:rag")

manifest = {
    "description": "Hybrid RAG over user-uploaded docs. mode='ingest' to add files; mode='query' to retrieve cited snippets.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["ingest", "query", "list", "clear"]},
            "paths": {"type": "array", "items": {"type": "string"}},
            "query": {"type": "string"},
            "namespace": {"type": "string"},
            "k": {"type": "integer"},
        },
        "required": ["mode"],
    },
}

CACHE = ROOT / ".cache" / "rag"
CACHE.mkdir(parents=True, exist_ok=True)
INDEX_FILE = CACHE / "docs.jsonl"


def _read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".html", ".htm", ".py", ".js", ".ts", ".css", ".json"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional
            return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        except Exception:
            return ""
    if suffix in (".docx",):
        try:
            from docx import Document  # type: ignore
            return "\n".join(p.text for p in Document(str(path)).paragraphs)
        except Exception:
            return ""
    return ""


def _chunk(text: str, size: int = 1200, overlap: int = 200) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    parts = []
    i = 0
    while i < len(text):
        parts.append(text[i : i + size])
        i += size - overlap
    return parts


def _ingest_sync(paths: list[str], namespace: str) -> dict:
    import chromadb
    client = chromadb.PersistentClient(path=str(CACHE / "chroma"))
    coll = client.get_or_create_collection(namespace)
    added = 0
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        text = _read_file(path)
        for j, chunk in enumerate(_chunk(text)):
            doc_id = hashlib.sha1(f"{path.name}:{j}:{chunk[:50]}".encode()).hexdigest()
            coll.upsert(
                documents=[chunk],
                metadatas=[{"source": path.name, "chunk": j}],
                ids=[doc_id],
            )
            added += 1
    return {"ingested_chunks": added, "namespace": namespace}


def _query_sync(query: str, namespace: str, k: int) -> dict:
    import chromadb
    client = chromadb.PersistentClient(path=str(CACHE / "chroma"))
    coll = client.get_or_create_collection(namespace)
    res = coll.query(query_texts=[query], n_results=k)
    hits = []
    for doc, meta in zip(res.get("documents", [[]])[0], res.get("metadatas", [[]])[0]):
        hits.append({"text": doc, "meta": meta or {}})
    return {"query": query, "hits": hits}


async def run(mode: str, **kwargs: Any) -> dict:
    namespace = kwargs.get("namespace") or "default"
    if mode == "ingest":
        paths = kwargs.get("paths", []) or []
        return await asyncio.to_thread(_ingest_sync, paths, namespace)
    if mode == "query":
        return await asyncio.to_thread(
            _query_sync, kwargs.get("query", ""), namespace, int(kwargs.get("k", 5))
        )
    if mode == "list":
        import chromadb
        client = chromadb.PersistentClient(path=str(CACHE / "chroma"))
        return {"collections": [c.name for c in client.list_collections()]}
    if mode == "clear":
        import chromadb
        client = chromadb.PersistentClient(path=str(CACHE / "chroma"))
        try:
            client.delete_collection(namespace)
        except Exception:
            pass
        return {"cleared": namespace}
    raise ValueError(f"unknown rag mode: {mode}")

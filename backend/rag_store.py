"""
Real RAG: chunking + Ollama embeddings + local vector index (numpy cosine).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

from config import VECTOR_STORE_CONFIG, VECTOR_DIR
from ollama_client import embed, embed_one, ollama_reachable

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    title: str
    content: str
    source_url: str
    file_path: str
    doc_type: str
    tags: list
    related_stocks: list
    index: int


class RAGParameterStore:
    """Mutable RAG parameters (in-memory + JSON persistence)."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (VECTOR_DIR / "rag_params.json")
        self._lock = threading.Lock()
        self.params = {
            "enabled": VECTOR_STORE_CONFIG.get("enabled", True),
            "top_k": VECTOR_STORE_CONFIG.get("top_k", 5),
            "chunk_size": VECTOR_STORE_CONFIG.get("chunk_size", 800),
            "chunk_overlap": VECTOR_STORE_CONFIG.get("chunk_overlap", 120),
            "score_threshold": VECTOR_STORE_CONFIG.get("score_threshold", 0.15),
            "embedding_model": None,  # use config default
        }
        self.load()

    def load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.params.update({k: v for k, v in data.items() if k in self.params or True})
            except Exception as e:
                logger.warning("[RAG] load params failed: %s", e)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.params, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self) -> dict:
        with self._lock:
            return dict(self.params)

    def update(self, updates: dict) -> dict:
        with self._lock:
            for k, v in updates.items():
                if v is None:
                    continue
                if k == "enabled":
                    self.params["enabled"] = bool(v)
                elif k in ("top_k", "chunk_size", "chunk_overlap"):
                    self.params[k] = int(v)
                elif k == "score_threshold":
                    self.params[k] = float(v)
                elif k == "embedding_model":
                    self.params[k] = v
            self.save()
            return dict(self.params)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks by characters (Chinese-friendly)."""
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= 0:
        return [text]
    # Prefer splitting on paragraph/sentence boundaries when possible
    parts = re.split(r"(?<=[。！？\n])", text)
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if not p:
            continue
        if len(buf) + len(p) <= chunk_size:
            buf += p
        else:
            if buf:
                chunks.append(buf.strip())
            if len(p) > chunk_size:
                start = 0
                while start < len(p):
                    end = start + chunk_size
                    chunks.append(p[start:end].strip())
                    start = max(end - overlap, start + 1)
                buf = ""
            else:
                # keep overlap from previous
                if chunks and overlap > 0:
                    prev = chunks[-1]
                    tail = prev[-overlap:] if len(prev) > overlap else prev
                    buf = tail + p
                else:
                    buf = p
    if buf.strip():
        chunks.append(buf.strip())
    return [c for c in chunks if c]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class VectorStore:
    """Persistent local vector index using JSON metadata + .npy matrix."""

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory or VECTOR_DIR)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.directory / "chunks.json"
        self.matrix_path = self.directory / "embeddings.npy"
        self._lock = threading.Lock()
        self.chunks: list[dict] = []
        self.matrix: Optional[np.ndarray] = None
        self._load()

    def _load(self):
        if self.meta_path.exists():
            try:
                self.chunks = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:
                self.chunks = []
        if self.matrix_path.exists() and self.chunks:
            try:
                self.matrix = np.load(self.matrix_path)
                if len(self.matrix) != len(self.chunks):
                    logger.warning("[RAG] matrix/chunk size mismatch; rebuilding empty")
                    self.chunks = []
                    self.matrix = None
            except Exception:
                self.matrix = None

    def _persist(self):
        self.meta_path.write_text(
            json.dumps(self.chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if self.matrix is not None and len(self.matrix):
            np.save(self.matrix_path, self.matrix)

    @property
    def doc_count(self) -> int:
        return len({c.get("doc_id") for c in self.chunks})

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        source_url: str = "",
        file_path: str = "",
        doc_type: str = "自定义",
        tags: Optional[list] = None,
        related_stocks: Optional[list] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        embedding_model: Optional[str] = None,
    ) -> dict:
        params = rag_params.get()
        chunk_size = chunk_size or params.get("chunk_size", 800)
        chunk_overlap = chunk_overlap or params.get("chunk_overlap", 120)
        pieces = chunk_text(content, chunk_size=chunk_size, overlap=chunk_overlap)
        if not pieces:
            return {"status": "error", "message": "empty content after chunking"}

        vectors = embed(pieces, model=embedding_model or params.get("embedding_model") or None)
        new_records = []
        for i, (piece, vec) in enumerate(zip(pieces, vectors)):
            if not vec:
                continue
            rec = {
                "chunk_id": str(uuid.uuid4()),
                "doc_id": str(doc_id),
                "title": title,
                "content": piece,
                "source_url": source_url or "",
                "file_path": file_path or "",
                "doc_type": doc_type,
                "tags": tags or [],
                "related_stocks": related_stocks or [],
                "index": i,
                "created_at": datetime.utcnow().isoformat(),
            }
            new_records.append((rec, vec))

        with self._lock:
            # remove old chunks for same doc_id
            keep_idx = [i for i, c in enumerate(self.chunks) if c.get("doc_id") != str(doc_id)]
            if self.matrix is not None and len(keep_idx) < len(self.chunks):
                self.matrix = self.matrix[keep_idx] if keep_idx else None
                self.chunks = [self.chunks[i] for i in keep_idx]
            elif not keep_idx and self.chunks:
                # all were same doc
                if all(c.get("doc_id") == str(doc_id) for c in self.chunks):
                    self.chunks = []
                    self.matrix = None

            for rec, vec in new_records:
                arr = np.array(vec, dtype=np.float32)
                if self.matrix is None or len(self.chunks) == 0:
                    self.matrix = arr.reshape(1, -1)
                    self.chunks = [rec]
                else:
                    # pad if dims differ (shouldn't for same model)
                    if arr.shape[0] != self.matrix.shape[1]:
                        raise RuntimeError(
                            f"embedding dim mismatch: {arr.shape[0]} vs {self.matrix.shape[1]}"
                        )
                    self.matrix = np.vstack([self.matrix, arr.reshape(1, -1)])
                    self.chunks.append(rec)
            self._persist()

        return {
            "status": "ok",
            "doc_id": str(doc_id),
            "chunks": len(new_records),
            "title": title,
        }

    def delete_document(self, doc_id: str) -> dict:
        doc_id = str(doc_id)
        with self._lock:
            keep = [i for i, c in enumerate(self.chunks) if c.get("doc_id") != doc_id]
            removed = len(self.chunks) - len(keep)
            if removed == 0:
                return {"status": "ok", "removed_chunks": 0}
            self.chunks = [self.chunks[i] for i in keep]
            if self.matrix is not None and keep:
                self.matrix = self.matrix[keep]
            else:
                self.matrix = None
            self._persist()
            return {"status": "ok", "removed_chunks": removed}

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        doc_type: str = "全部",
        embedding_model: Optional[str] = None,
    ) -> list[dict]:
        params = rag_params.get()
        if not params.get("enabled", True):
            return []
        top_k = top_k if top_k is not None else int(params.get("top_k", 5))
        score_threshold = (
            score_threshold
            if score_threshold is not None
            else float(params.get("score_threshold", 0.15))
        )
        if not query.strip() or self.matrix is None or not self.chunks:
            return []

        qvec = np.array(
            embed_one(query, model=embedding_model or params.get("embedding_model") or None),
            dtype=np.float32,
        )
        if qvec.size == 0:
            return []
        if qvec.shape[0] != self.matrix.shape[1]:
            raise RuntimeError("query embedding dimension mismatch with index")

        # cosine similarity batch
        mat = self.matrix
        norms = np.linalg.norm(mat, axis=1) * (np.linalg.norm(qvec) + 1e-12)
        scores = (mat @ qvec) / (norms + 1e-12)

        ranked = []
        for i, score in enumerate(scores):
            chunk = self.chunks[i]
            if doc_type and doc_type != "全部" and chunk.get("doc_type") != doc_type:
                continue
            s = float(score)
            if s < score_threshold:
                continue
            ranked.append({
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "title": chunk.get("title"),
                "content": chunk.get("content"),
                "source_url": chunk.get("source_url"),
                "file_path": chunk.get("file_path"),
                "doc_type": chunk.get("doc_type"),
                "tags": chunk.get("tags"),
                "related_stocks": chunk.get("related_stocks"),
                "score": round(s, 4),
                "search_method": "vector",
            })
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    def list_sources(self) -> list[dict]:
        by_doc: dict[str, dict] = {}
        for c in self.chunks:
            did = c.get("doc_id")
            if did not in by_doc:
                by_doc[did] = {
                    "doc_id": did,
                    "title": c.get("title"),
                    "source_url": c.get("source_url") or "",
                    "file_path": c.get("file_path") or "",
                    "doc_type": c.get("doc_type"),
                    "chunk_count": 0,
                }
            by_doc[did]["chunk_count"] += 1
        return list(by_doc.values())


def check_source_reachable(source_url: str = "", file_path: str = "") -> dict:
    """Check whether a knowledge source is reachable (URL or local file)."""
    result = {
        "source_url": source_url or "",
        "file_path": file_path or "",
        "reachable": False,
        "kind": "none",
        "detail": "",
    }
    if file_path:
        p = Path(file_path)
        result["kind"] = "file"
        if p.exists() and p.is_file():
            result["reachable"] = True
            result["detail"] = f"file exists, size={p.stat().st_size}"
        else:
            result["detail"] = "file missing"
        return result
    if source_url:
        result["kind"] = "url"
        if source_url.startswith("seed://") or source_url.startswith("internal://"):
            result["reachable"] = True
            result["detail"] = "internal seed source"
            return result
        try:
            import requests
            resp = requests.head(source_url, timeout=5, allow_redirects=True)
            if resp.status_code >= 400:
                resp = requests.get(source_url, timeout=5, stream=True)
            result["reachable"] = resp.status_code < 500
            result["detail"] = f"HTTP {resp.status_code}"
        except Exception as e:
            result["detail"] = str(e)
        return result
    result["detail"] = "no source"
    return result


def kb_status() -> dict:
    """Overall knowledge base + RAG health."""
    ollama = ollama_reachable()
    sources = vector_store.list_sources()
    source_checks = []
    for s in sources:
        chk = check_source_reachable(s.get("source_url", ""), s.get("file_path", ""))
        source_checks.append({**s, **chk})
    params = rag_params.get()
    return {
        "status": "ok",
        "rag_enabled": params.get("enabled", True),
        "rag_params": params,
        "vector_store": {
            "path": str(vector_store.directory),
            "document_count": vector_store.doc_count,
            "chunk_count": vector_store.chunk_count,
            "usable": vector_store.chunk_count > 0 and ollama.get("ok", False),
        },
        "embedding": {
            "reachable": ollama.get("ok", False),
            "models": ollama.get("models", []),
            "base_url": ollama.get("base_url"),
            "error": ollama.get("error"),
        },
        "sources": source_checks,
    }


# Singletons
rag_params = RAGParameterStore()
vector_store = VectorStore()

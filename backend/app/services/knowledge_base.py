"""Chunk, embed, index, query. Includes the similarity floor from spec 7.1.

Embeddings are computed explicitly via Ollama (`nomic-embed-text`) and passed
to Chroma as vectors. We never let Chroma pick an embedding function, so the
default ONNX/MiniLM model is never downloaded and the index always matches the
model named in config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import chromadb
import numpy as np
from chromadb.api.models.Collection import Collection
from ollama import Client as OllamaSDK

from app.config import settings

COLLECTION_NAME = "sops"

# Chroma 1.x types `include` as a list of IncludeEnum. Plain strings work at
# runtime; the cast just stops the type checker complaining.
INCLUDE_QUERY = cast(Any, ["documents", "metadatas", "distances"])
INCLUDE_GET = cast(Any, ["documents", "metadatas"])

_ollama = OllamaSDK(host=settings.ollama_host)


def embed_texts(texts: list[str]) -> Any:
    """Embed a batch of strings with nomic-embed-text. Order is preserved.

    Returns float32 ndarrays. Chroma 1.x types `Embedding` as an NDArray, so a
    plain list[list[float]] fails the type check on add()/query().
    """
    if not texts:
        return []
    response = _ollama.embed(model=settings.embed_model, input=texts)
    return [np.asarray(vector, dtype=np.float32) for vector in response["embeddings"]]


class KnowledgeBase:
    def __init__(self, persist_dir: str | None = None) -> None:
        self.client = chromadb.PersistentClient(path=persist_dir or settings.chroma_path)
        # Assign in __init__, not in a helper. Otherwise the type checker infers
        # `None` for self.collection and flags .count()/.add()/.query().
        self.collection: Collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,  # we always supply vectors ourselves
        )

    # ---------------------------------------------------------------- indexing

    def index_sops(self, sops_dir: str | None = None, force: bool = False) -> int:
        """Read markdown SOPs, chunk, embed, index. Idempotent unless force=True."""
        if force:
            self.reset()

        existing = self.collection.count()
        if existing > 0:
            print(f"[kb] already indexed ({existing} chunks)")
            return existing

        sops_path = Path(sops_dir or settings.sop_dir)
        files = sorted(sops_path.glob("*.md"))
        if not files:
            print(f"[kb] WARNING: no .md files found in {sops_path}")
            return 0

        print(f"[kb] indexing {len(files)} SOPs from {sops_path}")

        for sop_file in files:
            meta, body = self._parse_front_matter(sop_file.read_text(encoding="utf-8"))
            doc_id = meta.get("doc_id") or sop_file.stem
            title = meta.get("title") or sop_file.stem

            chunks = self._chunk_document(body, doc_id)
            if not chunks:
                continue

            vectors = embed_texts([c["text"] for c in chunks])

            # One batched add per document, not one call per chunk.
            self.collection.add(
                ids=[c["id"] for c in chunks],
                documents=[c["text"] for c in chunks],
                embeddings=vectors,
                metadatas=[
                    {
                        "doc_id": doc_id,
                        "title": title,
                        "section": c["section"],
                        "revision": meta.get("revision", ""),
                        "department": meta.get("department", ""),
                    }
                    for c in chunks
                ],
            )
            print(f"[kb]   {doc_id} {title} -> {len(chunks)} chunks")

        total = self.collection.count()
        print(f"[kb] done, {total} chunks in collection")
        return total

    def reset(self) -> None:
        """Drop and recreate the collection. Use after editing SOPs."""
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=None,
        )

    # ---------------------------------------------------------------- parsing

    @staticmethod
    def _parse_front_matter(content: str) -> tuple[dict[str, str], str]:
        """Split YAML-ish front matter from the body.

        Splitting on every '---' breaks on horizontal rules inside the body,
        so we split at most twice and only when the file opens with a fence.
        """
        meta: dict[str, str] = {}
        text = content.lstrip()
        if not text.startswith("---"):
            return meta, text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return meta, text

        for line in parts[1].splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        return meta, parts[2].strip()

    @staticmethod
    def _chunk_document(text: str, doc_id: str, chunk_size: int = 800) -> list[dict]:
        """Chunk on heading boundaries, flushing when a chunk gets long.

        Chunks never straddle a heading, so the cited `section` is always the
        section the text actually came from.
        """
        chunks: list[dict] = []
        section = "General"
        buffer: list[str] = []
        n = 0

        def flush(current_section: str) -> None:
            nonlocal buffer, n
            body = "\n".join(buffer).strip()
            buffer = []
            if not body:
                return
            n += 1
            chunks.append(
                {"id": f"{doc_id}#{n}", "text": body, "section": current_section}
            )

        for line in text.splitlines():
            is_heading = line.lstrip().startswith("#")
            if is_heading and buffer:
                flush(section)
            if is_heading:
                section = line.lstrip("#").strip() or section
            buffer.append(line)
            if len("\n".join(buffer)) >= chunk_size:
                flush(section)

        flush(section)
        return chunks

    # ---------------------------------------------------------------- querying

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Return chunks above the similarity floor. Empty list means off-topic."""
        k = top_k or settings.retrieval_top_k
        if self.collection.count() == 0:
            return []

        query_vector = embed_texts([query])[0]
        raw = self.collection.query(
            query_embeddings=[query_vector],
            n_results=k,
            include=INCLUDE_QUERY,
        )

        ids = (raw.get("ids") or [[]])[0]
        if not ids:
            return []

        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results = []
        for i, chunk_id in enumerate(ids):
            distance = float(distances[i]) if distances else 1.0
            # Spec 7.1: cosine DISTANCE ceiling. Above it, not really a match.
            if distance > settings.max_match_distance:
                continue
            meta = dict(metadatas[i] or {})
            results.append(
                {
                    "id": chunk_id,
                    "doc_id": meta.get("doc_id", chunk_id.split("#")[0]),
                    "title": meta.get("title", ""),
                    "section": meta.get("section", "General"),
                    "content": documents[i],
                    "distance": distance,
                    "metadata": meta,
                }
            )
        return results

    def debug_distances(self, queries: list[str], top_k: int = 4) -> None:
        """Calibration helper for spec 7.1. Prints raw distances, no filtering."""
        for q in queries:
            vector = embed_texts([q])[0]
            raw = self.collection.query(
                query_embeddings=[vector], n_results=top_k, include=INCLUDE_QUERY
            )
            best = (raw.get("distances") or [[]])[0]
            metas = (raw.get("metadatas") or [[]])[0]
            head = f"{best[0]:.3f} {metas[0].get('doc_id')}" if best else "no results"
            print(f"[calib] {head:<28} <- {q}")


_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
        _kb.index_sops()
    return _kb

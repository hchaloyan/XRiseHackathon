"""Chunk, embed, index, query. Includes the similarity floor from spec 7.1.

Embeddings are computed explicitly via Ollama (`nomic-embed-text`) and passed
to Chroma as vectors. We never let Chroma pick an embedding function, so the
default ONNX/MiniLM model is never downloaded and the index always matches the
model named in config.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import chromadb
import numpy as np
from chromadb.api.models.Collection import Collection
from ollama import Client as OllamaSDK

from app.config import settings

COLLECTION_NAME = "sops"

# nomic-embed-text is trained with task prefixes and the two sides are NOT
# interchangeable. Embedding both bare collapses every distance into one narrow
# band: in-corpus and factory-data queries then sit 0.018 apart and no cutoff
# can separate them. With the prefixes that gap is 0.045. See calibrate_kb.py.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

# Bump whenever embeddings or chunking change. A stale index is silent: the
# vectors still resolve, the distances are just wrong, and the ask bar answers
# "off topic" to everything.
INDEX_VERSION = "nomic-prefixed/sections-no-scope/headers-v1"
_COLLECTION_META = {"hnsw:space": "cosine", "index_version": INDEX_VERSION}

# Chroma 1.x types `include` as a list of IncludeEnum. Plain strings work at
# runtime; the cast just stops the type checker complaining.
INCLUDE_QUERY = cast(Any, ["documents", "metadatas", "distances"])
INCLUDE_GET = cast(Any, ["documents", "metadatas"])

# Words that name a factory metric rather than a procedure. The lexical
# fallback refuses any query containing one, because several of them do occur
# in SOP prose - "downtime" is in six documents - and a bare metric word
# retrieving a maintenance procedure is exactly the rule 8 failure the
# similarity floor exists to prevent. OEE, availability and inventory appear in
# none of the SOPs, but they are listed for the day someone adds a document
# that mentions them.
METRIC_TERMS = frozenset({
    "oee", "scrap", "downtime", "availability", "performance", "utilisation",
    "utilization", "throughput", "yield", "inventory", "uptime",
})

_ollama = OllamaSDK(host=settings.ollama_host)


def read_sop(doc_id: str) -> dict | None:
    """The whole document as written, for the in-app viewer.

    Read from disk rather than reassembled from chunks: chunking splits on
    headings and drops nothing, but stitching pieces back together would put
    the viewer's fidelity at the mercy of the indexer.
    """
    wanted = doc_id.strip().upper()
    for path in sorted(Path(settings.sop_dir).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = KnowledgeBase._parse_front_matter(raw)
        if (meta.get("doc_id") or path.stem).upper() != wanted:
            continue
        return {
            "doc_id": meta.get("doc_id", path.stem),
            "title": meta.get("title", path.stem),
            "revision": meta.get("revision", ""),
            "department": meta.get("department", ""),
            "markdown": body,
        }
    return None


def embed_texts(texts: list[str], prefix: str) -> Any:
    """Embed a batch of strings with nomic-embed-text. Order is preserved.

    `prefix` is required rather than defaulted: passing the wrong side is
    invisible at runtime and only shows up as a badly calibrated cutoff.

    Returns float32 ndarrays. Chroma 1.x types `Embedding` as an NDArray, so a
    plain list[list[float]] fails the type check on add()/query().
    """
    if not texts:
        return []
    response = _ollama.embed(model=settings.embed_model, input=[prefix + t for t in texts])
    return [np.asarray(vector, dtype=np.float32) for vector in response["embeddings"]]


def embed_query(text: str) -> Any:
    """One query vector. Every read path goes through here so the query-side
    prefix can't be forgotten at a call site."""
    return embed_texts([text], QUERY_PREFIX)[0]


# "SOP 1", "sop-001", "SOP_23". Anchored on the SOP token so a bare number or a
# machine id (M-22) never trips it.
_DOC_REFERENCE = re.compile(r"\bSOP[\s\-_]*(\d{1,3})\b", re.IGNORECASE)


def _doc_reference(query: str) -> str | None:
    """The doc_id a query names outright, or None."""
    match = _DOC_REFERENCE.search(query)
    return f"SOP-{int(match.group(1)):03d}" if match else None


class KnowledgeBase:
    def __init__(self, persist_dir: str | None = None) -> None:
        self.client = chromadb.PersistentClient(path=persist_dir or settings.chroma_path)
        # Assign in __init__, not in a helper. Otherwise the type checker infers
        # `None` for self.collection and flags .count()/.add()/.query().
        self.collection: Collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata=_COLLECTION_META,
            embedding_function=None,  # we always supply vectors ourselves
        )
        # Built on first lexical lookup, invalidated by reset().
        self._lexical_cache: list[dict] | None = None

    # ---------------------------------------------------------------- indexing

    def index_sops(self, sops_dir: str | None = None, force: bool = False) -> int:
        """Read markdown SOPs, chunk, embed, index. Idempotent unless force=True."""
        if force:
            self.reset()

        existing = self.collection.count()
        if existing and (self.collection.metadata or {}).get("index_version") != INDEX_VERSION:
            print("[kb] index predates the current embedding/chunking scheme, rebuilding")
            self.reset()
            existing = 0

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

            # Scope statements answer nothing - they just name the machines and
            # defect codes the document covers. Indexed, they outranked the
            # procedure that actually answers ("what causes porosity" returned
            # SOP-008's blurb instead of its WELD_POROSITY steps) because they
            # are short and densely on-topic, and they pulled in factory-data
            # questions for the same reason.
            chunks = [
                c
                for c in self._chunk_document(body, doc_id)
                if not c["section"].lower().startswith("purpose")
            ]
            if not chunks:
                continue

            # Embed the chunk WITH its document identity and heading; store the
            # raw body. Without this the doc_id and title exist only in Chroma
            # metadata, so nothing in the vector space knows a chunk belongs to
            # "SOP-002 Preventive Maintenance" - "tell me about preventive
            # maintenance" retrieved SOP-003. Display is unaffected.
            vectors = embed_texts(
                [f"{doc_id} {title} - {c['section']}\n\n{c['text']}" for c in chunks],
                DOC_PREFIX,
            )

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
            metadata=_COLLECTION_META,
            embedding_function=None,
        )
        self._lexical_cache = None  # would otherwise survive the reindex

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
    def _chunk_document(
        text: str, doc_id: str, chunk_size: int = 1500, min_chunk: int = 260
    ) -> list[dict]:
        """Chunk on heading boundaries, flushing when a chunk gets long.

        Chunks never straddle a heading, so the cited `section` is always the
        section the text actually came from.

        `chunk_size` sits above the longest section in the corpus (~1100 chars,
        well inside nomic's 2048-token window) so sections stay whole. At 800 it
        split them, and the halves surfaced as two search rows under one
        identical heading, the second often a stray fragment - one was 14
        characters. Anything short enough to still fall out of a split is folded
        back rather than indexed on its own.
        """
        chunks: list[dict] = []
        section = "General"
        buffer: list[str] = []

        def flush(current_section: str) -> None:
            nonlocal buffer
            body = "\n".join(buffer).strip()
            buffer = []
            if not body:
                return
            if chunks and len(body) < min_chunk and chunks[-1]["section"] == current_section:
                chunks[-1]["text"] += "\n" + body
                return
            chunks.append(
                {"id": f"{doc_id}#{len(chunks) + 1}", "text": body, "section": current_section}
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

    def _by_doc_id(self, doc_id: str) -> list[dict]:
        """Every section of one document, in document order."""
        got = self.collection.get(where={"doc_id": doc_id}, include=INCLUDE_GET)
        ids = got.get("ids") or []
        if not ids:
            return []
        documents = got.get("documents") or []
        metadatas = got.get("metadatas") or []

        rows = []
        for i, chunk_id in enumerate(ids):
            meta = dict(metadatas[i] or {})
            rows.append(
                {
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "title": meta.get("title", ""),
                    "section": meta.get("section", "General"),
                    "content": documents[i],
                    # Exact reference, not a similarity judgement.
                    "distance": 0.0,
                    "metadata": meta,
                }
            )
        # `get` does not promise an order; ids are "<doc_id>#<n>".
        rows.sort(key=lambda r: int(r["id"].rsplit("#", 1)[-1]))
        return rows

    def _all_chunks(self) -> list[dict]:
        """Every chunk, cached. 61 chunks - small enough to scan in Python."""
        if self._lexical_cache is None:
            got = self.collection.get(include=INCLUDE_GET)
            ids = got.get("ids") or []
            documents = got.get("documents") or []
            metadatas = got.get("metadatas") or []
            self._lexical_cache = [
                {
                    "id": chunk_id,
                    "content": documents[i],
                    "metadata": dict(metadatas[i] or {}),
                    # Precomputed once: title and section are weighted more
                    # heavily than body text, so a term in a heading wins.
                    "haystack": (
                        f"{(metadatas[i] or {}).get('title', '')} "
                        f"{(metadatas[i] or {}).get('section', '')} "
                        f"{documents[i]}"
                    ).lower(),
                    "heading": (
                        f"{(metadatas[i] or {}).get('title', '')} "
                        f"{(metadatas[i] or {}).get('section', '')}"
                    ).lower(),
                }
                for i, chunk_id in enumerate(ids)
            ]
        return self._lexical_cache

    def lexical_search(self, query: str, top_k: int) -> list[dict]:
        """Substring fallback for terse queries the embedding cannot place.

        "3d", "sls", "recoater" carry almost no semantic signal at two or
        three characters, so they land above the distance floor and get
        rejected even though the corpus plainly contains them. A literal term
        match recovers exactly those cases.

        Runs only when vector search returned nothing, so it can never
        outrank a real semantic match. Guarded by METRIC_TERMS as well:
        "downtime" appears in six SOPs, and letting a bare metric word
        retrieve a maintenance procedure is the rule 8 failure the similarity
        floor exists to prevent.
        """
        terms = [t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) >= 2]
        if not terms or any(t in METRIC_TERMS for t in terms):
            return []

        scored = []
        for chunk in self._all_chunks():
            hits = sum(1 for t in terms if t in chunk["haystack"])
            if hits != len(terms):
                continue  # every term must appear; partial matches are noise
            heading_hits = sum(1 for t in terms if t in chunk["heading"])
            scored.append((heading_hits, chunk))

        if not scored:
            return []

        # Heading matches first, then document order for stability.
        scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))

        results = []
        seen: set[str] = set()
        for _, chunk in scored:
            meta = chunk["metadata"]
            doc_id = meta.get("doc_id", chunk["id"].split("#")[0])
            if doc_id in seen:
                continue
            seen.add(doc_id)
            results.append(
                {
                    "id": chunk["id"],
                    "doc_id": doc_id,
                    "title": meta.get("title", ""),
                    "section": meta.get("section", "General"),
                    "content": chunk["content"],
                    # A literal term match, not a similarity judgement - same
                    # convention as _by_doc_id.
                    "distance": 0.0,
                    "metadata": meta,
                }
            )
            if len(results) == top_k:
                break
        return results

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Return the best-matching chunk per SOP, above the similarity floor.

        One result per document, most relevant section only. Empty list means
        off-topic.

        A query that names a document by id ("summarize SOP 001") is answered by
        exact lookup instead, returning that document's sections. Naming a
        document is a reference, not a question about content, and the two are
        not separable by distance: post-fix "summarize SOP 001" scores 0.362 and
        "which machine had the most downtime this week" 0.366. This is a literal
        id match inside document search, never a route between documents and
        factory data - rule 8 still holds.
        """
        k = top_k or settings.retrieval_top_k
        count = self.collection.count()
        if count == 0:
            return []

        referenced = _doc_reference(query)
        if referenced:
            rows = self._by_doc_id(referenced)
            if rows:
                return rows

        raw = self.collection.query(
            query_embeddings=[embed_query(query)],
            # Over-fetch. Sections of one SOP are similar to each other, so a
            # single document otherwise sweeps the whole top-k and the user
            # reads the same procedure four times.
            n_results=min(k * 5, count),
            include=INCLUDE_QUERY,
        )

        ids = (raw.get("ids") or [[]])[0]
        if not ids:
            return []

        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results = []
        seen: set[str] = set()
        for i, chunk_id in enumerate(ids):
            distance = float(distances[i]) if distances else 1.0
            # Spec 7.1: cosine DISTANCE ceiling. Above it, not really a match.
            if distance > settings.max_match_distance:
                continue
            meta = dict(metadatas[i] or {})
            doc_id = meta.get("doc_id", chunk_id.split("#")[0])
            # Chroma returns ascending distance, so the first chunk seen from a
            # document is its best one.
            if doc_id in seen:
                continue
            seen.add(doc_id)
            results.append(
                {
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "title": meta.get("title", ""),
                    "section": meta.get("section", "General"),
                    "content": documents[i],
                    "distance": distance,
                    "metadata": meta,
                }
            )
            if len(results) == k:
                break

        # Nothing cleared the floor. Before declaring the query off-topic, try
        # a literal term match - this is what rescues "3d" and "sls".
        if not results:
            return self.lexical_search(query, k)

        return results

    def debug_distances(self, queries: list[str], top_k: int = 4) -> None:
        """Calibration helper for spec 7.1. Prints raw distances, no filtering."""
        for q in queries:
            raw = self.collection.query(
                query_embeddings=[embed_query(q)], n_results=top_k, include=INCLUDE_QUERY
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

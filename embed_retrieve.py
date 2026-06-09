"""
embed_retrieve.py

Embedding and retrieval stage for the campus survival guide RAG pipeline.

Architecture (from planning.md):
    Chunking → Embedding + Vector Store → Retrieval
    Model  : sentence-transformers/all-MiniLM-L6-v2
    Store  : FAISS IndexFlatL2
    Top-k  : 5
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Module-level model — loaded once, reused across all calls
# ---------------------------------------------------------------------------
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# 1. Build index
# ---------------------------------------------------------------------------

def build_index(chunks: list[dict]) -> tuple[faiss.Index, list[dict]]:
    """Encode every chunk and store vectors in a FAISS IndexFlatL2.

    Args:
        chunks: List of chunk dicts as produced by chunk_text(). Each must
                have at least a "text" key plus the six metadata keys.

    Returns:
        index    : FAISS IndexFlatL2 with one row per chunk.
        metadata : Parallel list of dicts (same order as index rows) containing
                   all chunk fields *except* "text".
    """
    model = _get_model()
    texts = [c["text"] for c in chunks]

    print(f"Encoding {len(texts)} chunks with {_MODEL_NAME} …")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    # Store ALL fields (including text) so retrieve() is self-contained
    # and never needs a separate chunk list for text lookup.
    metadata = [dict(chunk) for chunk in chunks]

    return index, metadata


# ---------------------------------------------------------------------------
# 2. Retrieve
# ---------------------------------------------------------------------------

def retrieve(
    query: str,
    index: faiss.Index,
    metadata: list[dict],
    chunks: list[dict] | None = None,   # kept for backward compat, ignored
    k: int = 5,
) -> list[dict]:
    """Embed a query and return the top-k nearest chunks with metadata.

    Text is read directly from metadata (stored there by build_index), so
    this function is fully self-contained — no separate chunk list needed.

    Args:
        query    : Natural-language query string.
        index    : FAISS index built by build_index().
        metadata : Parallel metadata list returned by build_index(). Each
                   entry includes all chunk fields plus "text".
        chunks   : Ignored (kept for backward compatibility).
        k        : Number of results to return (default 5).

    Returns:
        List of result dicts, each containing all metadata fields plus
        score (FAISS L2 distance; lower = more similar).
        Ordered from most to least similar.
    """
    model = _get_model()
    query_vec = model.encode([query], convert_to_numpy=True).astype(np.float32)

    distances, indices = index.search(query_vec, k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:          # FAISS returns -1 when fewer than k vectors exist
            continue
        result = dict(metadata[idx])
        result["score"] = float(dist)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# 3. Persistence
# ---------------------------------------------------------------------------

def save_index(
    index: faiss.Index,
    metadata: list[dict],
    index_path: str,
    meta_path: str,
) -> None:
    """Save the FAISS index and metadata list to disk.

    Args:
        index      : FAISS index to persist.
        metadata   : Parallel metadata list to persist as JSON.
        index_path : Destination path for the FAISS binary (e.g. docs/index.faiss).
        meta_path  : Destination path for the JSON metadata (e.g. docs/index_meta.json).
    """
    Path(index_path).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, index_path)

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Saved index  → {index_path}")
    print(f"Saved metadata → {meta_path}")


def load_index(index_path: str, meta_path: str) -> tuple[faiss.Index, list[dict]]:
    """Load a previously saved FAISS index and metadata list from disk.

    Args:
        index_path : Path to the FAISS binary file.
        meta_path  : Path to the JSON metadata file.

    Returns:
        (index, metadata) tuple ready for use with retrieve().
    """
    index = faiss.read_index(index_path)

    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    print(f"Loaded index ({index.ntotal} vectors) from {index_path}")
    return index, metadata


# ---------------------------------------------------------------------------
# Main — end-to-end smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from chunk_pipeline import chunk_text, ingest_sources

    base_dir = Path(__file__).parent
    raw_dir = base_dir / "docs" / "raw"
    meta_file = base_dir / "docs" / "sources.json"
    index_path = str(base_dir / "docs" / "index.faiss")
    meta_path = str(base_dir / "docs" / "index_meta.json")

    # ── Ingest + chunk ──────────────────────────────────────────────────────
    print("=== Ingesting sources ===")
    docs = ingest_sources(str(raw_dir), str(meta_file))
    print(f"Loaded {len(docs)} documents.\n")

    print("=== Chunking ===")
    all_chunks: list[dict] = []
    for doc in docs:
        all_chunks.extend(chunk_text(doc))
    print(f"Total chunks after cleaning: {len(all_chunks)}\n")

    # ── Build + save index ──────────────────────────────────────────────────
    print("=== Building FAISS index ===")
    index, metadata = build_index(all_chunks)
    print(f"Total vectors indexed: {index.ntotal}\n")

    save_index(index, metadata, index_path, meta_path)
    print()

    # ── Test queries ────────────────────────────────────────────────────────
    test_queries = [
        "what do students say about dorm safety at night",
        "tips for managing stress and mental health in college",
        "how to find free food and resources on campus",
    ]

    print("=== Retrieval test (top-3 per query) ===\n")
    for query in test_queries:
        print(f"Query: {query!r}")
        results = retrieve(query, index, metadata, k=3)
        for rank, r in enumerate(results, 1):
            preview = r["text"][:200].replace("\n", " ")
            print(f"  [{rank}] chunk_id={r['chunk_id']}  score={r['score']:.4f}")
            print(f"       {preview!r}")
        print()

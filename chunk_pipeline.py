"""
chunk_pipeline.py

Ingests .txt source files and chunks them using LangChain's
RecursiveCharacterTextSplitter, attaching metadata to every chunk.
"""

import json
import os
import random
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

BOILERPLATE_SIGNALS = [
    "sponsored", "disclosure", "compensation", "cookie",
    "privacy policy", "terms of use", "all rights reserved",
    "sign up", "log in", "advertisement","get unlimited access",
"subscribe to continue",
"create a free account",
]

def is_boilerplate(text: str) -> bool:
    t = text.lower()
    return any(signal in t for signal in BOILERPLATE_SIGNALS)

def clean_markdown(text: str) -> str:
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}.*?`{1,3}", "", text)
    text = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", text)
    text = re.sub(r"^\s*[-*>]\s+", "", text, flags=re.MULTILINE)
    return text.strip()

# ---------------------------------------------------------------------------
# 1. Ingestion
# ---------------------------------------------------------------------------

def ingest_sources(raw_dir: str, meta_file: str) -> list[dict]:
    """Load every .txt file from raw_dir and merge metadata from meta_file.

    Args:
        raw_dir:   Path to the directory containing .txt source files.
        meta_file: Path to the JSON file with a list of source metadata dicts.

    Returns:
        List of document dicts with keys:
            text, source_type, subtopic, url, published_date, filename
    """
    with open(meta_file, "r", encoding="utf-8") as f:
        meta_list: list[dict] = json.load(f)
    meta_by_filename: dict[str, dict] = {m["filename"]: m for m in meta_list}

    documents: list[dict] = []
    raw_path = Path(raw_dir)

    for txt_file in sorted(raw_path.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        meta = meta_by_filename.get(txt_file.name, {})

        documents.append(
            {
                "text": text,
                "source_type": meta.get("source_type", "unknown"),
                "subtopic": meta.get("subtopic", []),
                "url": meta.get("url", ""),
                "published_date": meta.get("published_date", ""),
                "filename": txt_file.name,
            }
        )

    return documents


# ---------------------------------------------------------------------------
# 2. Chunking
# ---------------------------------------------------------------------------

def chunk_text(doc: dict) -> list[dict]:
    """Split a document into overlapping chunks, preserving all metadata.

    Uses RecursiveCharacterTextSplitter with:
        chunk_size=400, chunk_overlap=50
        separators=["\n\n", "\n", ". "]

    Each output chunk dict contains all six metadata keys from the input doc
    plus a unique `chunk_id` derived from the filename stem, e.g.
        reddit_college_tips_0, reddit_college_tips_1, ...

    Args:
        doc: A document dict as returned by ingest_sources().

    Returns:
        List of chunk dicts, with boilerplate and fragments removed.
    """
    # FIX 1: clean FIRST, then split the cleaned text (not doc["text"])
    text = clean_markdown(doc["text"])

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". "],
    )

    stem = Path(doc["filename"]).stem

    base_meta = {
        "source_type": doc["source_type"],
        "subtopic": doc["subtopic"],
        "url": doc["url"],
        "published_date": doc["published_date"],
        "filename": doc["filename"],
    }

    chunks: list[dict] = []
    for idx, chunk_content in enumerate(splitter.split_text(text)):  # FIX 2: use cleaned text
        chunks.append(
            {
                "text": chunk_content,
                "chunk_id": f"{stem}_{idx}",
                **base_meta,
            }
        )

    # FIX 3: filter out fragments and boilerplate
    chunks = [c for c in chunks if len(c["text"].split()) >= 25]
    chunks = [c for c in chunks if not is_boilerplate(c["text"])]

    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "docs" / "raw"
    meta_file = base_dir / "docs" / "sources.json"

    print("=== Ingesting sources ===")
    docs = ingest_sources(str(raw_dir), str(meta_file))
    print(f"Loaded {len(docs)} documents.\n")

    print("=== Chunking ===")
    all_chunks: list[dict] = []
    for doc in docs:
        all_chunks.extend(chunk_text(doc))

    total = len(all_chunks)
    print(f"Total chunks: {total}\n")

    print("=== 5 random chunks ===")
    sample = random.sample(all_chunks, min(5, total))
    for i, chunk in enumerate(sample, 1):
        print(f"--- Chunk {i} ---")
        print(f"  chunk_id     : {chunk['chunk_id']}")
        print(f"  source_type  : {chunk['source_type']}")
        print(f"  subtopic     : {chunk['subtopic']}")
        print(f"  url          : {chunk['url']}")
        print(f"  published_date: {chunk['published_date']}")
        print(f"  filename     : {chunk['filename']}")
        preview = chunk["text"][:200].replace("\n", " ")
        print(f"  text preview : {preview!r}")
        print()
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from rag.chunking import heading_aware_chunks
from rag.embeddings import sparse_vector
from rag.ingestion import load_cached_documents, refresh_corpus


@dataclass
class ChunkRecord:
    chunk_id: str
    source: str
    title: str
    product: str
    section_path: list[str]
    text: str
    excerpt: str
    sparse: Any


@dataclass
class CorpusIndex:
    version: str
    chunks: list[ChunkRecord]


_corpus_index: CorpusIndex | None = None


def _build_index() -> CorpusIndex:
    docs = load_cached_documents()
    if not docs:
        refresh_corpus(force=False)
        docs = load_cached_documents()

    chunks: list[ChunkRecord] = []
    for doc in docs:
        title = str(doc.get("title", "")).strip() or str(doc.get("url", ""))
        source = str(doc.get("url", "")).strip()
        products = list(doc.get("products", []))
        chunk_entries = doc.get("chunks")
        if not isinstance(chunk_entries, list):
            chunk_entries = list(heading_aware_chunks(str(doc.get("text", ""))))
        for idx, chunk in enumerate(chunk_entries):
            if isinstance(chunk, dict):
                chunk_payload = chunk
            elif isinstance(chunk, str):
                chunk_payload = {"text": chunk, "section_path": []}
            else:
                chunk_payload = {}
            text = str(chunk_payload.get("text", "")).strip()
            if not text:
                continue
            section_path = [str(item) for item in chunk_payload.get("section_path", [])]
            excerpt = text[:320]
            for product in products or [""]:
                chunk_id = hashlib.sha1(f"{source}|{product}|{idx}|{text[:120]}".encode("utf-8")).hexdigest()[:16]
                chunks.append(
                    ChunkRecord(
                        chunk_id=chunk_id,
                        source=source,
                        title=title,
                        product=product,
                        section_path=section_path,
                        text=text,
                        excerpt=excerpt,
                        sparse=sparse_vector(f"{title} {' '.join(section_path)} {text}"),
                    )
                )
    version = hashlib.sha256(
        json.dumps(
            [{"chunk_id": chunk.chunk_id, "source": chunk.source, "product": chunk.product} for chunk in chunks],
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return CorpusIndex(version=version, chunks=chunks)


def get_corpus_index(force_refresh: bool = False) -> CorpusIndex:
    global _corpus_index
    if _corpus_index is None or force_refresh:
        _corpus_index = _build_index()
    return _corpus_index

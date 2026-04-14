from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.schemas import IngestResponse
from rag.chunking import heading_aware_chunks

settings = get_settings()


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _fetch_text(url: str) -> str:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "CodeLens-RAG/2.0"})
            response.raise_for_status()
    except Exception:
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def load_registry_sources() -> list[dict[str, Any]]:
    records = _read_json(settings.source_registry_file, [])
    return records if isinstance(records, list) else []


def load_cached_documents() -> list[dict[str, Any]]:
    docs = _read_json(settings.oracle_cache_file, [])
    if not isinstance(docs, list):
        return []

    registry_urls = {
        str(source.get("url", "")).strip()
        for source in load_registry_sources()
        if str(source.get("url", "")).strip()
    }
    normalized_docs: list[dict[str, Any]] = []
    for raw_doc in docs:
        if not isinstance(raw_doc, dict):
            continue
        url = str(raw_doc.get("url", "")).strip()
        if registry_urls and url not in registry_urls:
            continue
        text = str(raw_doc.get("text", "")).strip()
        raw_chunks = raw_doc.get("chunks")
        chunks: list[dict[str, Any]] = []
        if isinstance(raw_chunks, list):
            for chunk in raw_chunks:
                if isinstance(chunk, dict):
                    chunk_text = str(chunk.get("text", "")).strip()
                    if not chunk_text:
                        continue
                    chunks.append(
                        {
                            "text": chunk_text,
                            "section_path": [str(item) for item in chunk.get("section_path", [])],
                            "start_token": int(chunk.get("start_token") or 0),
                            "end_token": int(chunk.get("end_token") or 0),
                        }
                    )
                elif isinstance(chunk, str):
                    chunk_text = chunk.strip()
                    if chunk_text:
                        chunks.append({"text": chunk_text, "section_path": []})
        if not chunks and text:
            chunks = list(heading_aware_chunks(text))
        normalized_docs.append(
            {
                **raw_doc,
                "url": url,
                "text": text,
                "products": [str(item).strip() for item in raw_doc.get("products", []) if str(item).strip()],
                "chunks": chunks,
            }
        )
    return normalized_docs


def refresh_corpus(*, force: bool = False) -> IngestResponse:
    registry = load_registry_sources()
    allowed_urls = {str(source.get("url", "")).strip() for source in registry if str(source.get("url", "")).strip()}
    docs = [doc for doc in load_cached_documents() if str(doc.get("url", "")).strip() in allowed_urls]
    seen = {str(doc.get("url", "")) for doc in docs}

    if force:
        docs = []
        seen = set()

    for source in registry:
        url = str(source.get("url", "")).strip()
        if not url or url in seen:
            continue
        text = _fetch_text(url)
        if not text:
            continue
        docs.append(
            {
                "title": source.get("title", url),
                "url": url,
                "products": source.get("products", []),
                "keywords": source.get("keywords", []),
                "domain": source.get("domain", "oracle"),
                "text": text,
            }
        )
        seen.add(url)

    normalized_docs = []
    chunk_count = 0
    for doc in docs:
        text = str(doc.get("text", "")).strip()
        chunks = list(heading_aware_chunks(text))
        chunk_count += len(chunks)
        normalized_docs.append({**doc, "chunks": chunks})

    settings.oracle_cache_file.write_text(
        json.dumps(normalized_docs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    corpus_version = hashlib.sha256(
        json.dumps(
            [{"url": doc.get("url"), "products": doc.get("products"), "text": doc.get("text", "")[:500]} for doc in normalized_docs],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return IngestResponse(
        corpus_version=corpus_version,
        source_count=len(registry),
        document_count=len(normalized_docs),
        chunk_count=chunk_count,
        refreshed=True,
    )

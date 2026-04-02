"""
Hybrid Oracle-focused RAG store.

This module keeps the existing Vertex AI RAG integration, but adds:
- Oracle source registry and product tagging
- Optional ingestion of ORACLE_LINKS documentation pages
- Product-aware retrieval filtering
- Exact source-to-excerpt citation mapping for UI grounding

If network, GCP, or parsing is unavailable, the module degrades gracefully.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

CORPUS_NAME_FILE = Path(__file__).parent / "rag_corpus.txt"
ORACLE_SOURCE_FILE = Path(__file__).parent / "oracle_rag_sources.json"
ORACLE_CACHE_FILE = Path(__file__).parent / "oracle_docs_cache.json"

_rag_corpus_name: str | None = None
_rag_ready = False
_init_attempted = False
_oracle_docs: list[dict[str, Any]] = []
_oracle_docs_loaded = False

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in",
    "is", "it", "of", "on", "or", "that", "the", "to", "was", "with", "using",
    "use", "this", "these", "those", "into", "your", "their", "than", "then",
    "when", "where", "which", "while", "code", "query", "table", "flow", "data",
}

_PRODUCT_PATTERNS: dict[str, tuple[str, ...]] = {
    "fusion": ("fusion", "oracle fusion", "fusion applications", "saas", "financials", "hcm", "scm"),
    "jde": ("jde", "jd edwards", "enterpriseone", "orchestrator", "ubes", "business function"),
    "ebs": ("ebs", "e-business suite", "ebusiness suite", "concurrent program", "adop", "forms personalization"),
    "epm": ("epm", "enterprise performance management", "planning", "calc manager", "smart view", "fccs"),
}

_GENERIC_HUB_PATTERNS = (
    "/en/applications/",
    "/en/cloud/saas/",
    "/index.html",
    "/nav/",
)


def _cfg(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]{1,}", text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def _normalize_source_url(url: str) -> str:
    clean = url.strip()
    if not clean:
        return ""
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc.lower()}{path}"


def _import_vertexai() -> bool:
    try:
        import vertexai  # noqa: F401
        from vertexai.preview import rag  # noqa: F401
        return True
    except ImportError:
        print("[rag_store] google-cloud-aiplatform[preview] not installed. Vertex RAG disabled.")
        return False


def _resolve_corpus_name(corpus_id: str, project: str, location: str) -> str:
    if corpus_id.startswith("projects/"):
        return corpus_id
    return f"projects/{project}/locations/{location}/ragCorpora/{corpus_id}"


def _save_corpus_name(name: str) -> None:
    try:
        CORPUS_NAME_FILE.write_text(name, encoding="utf-8")
    except OSError as e:
        print(f"[rag_store] Could not save corpus name: {e}")


def _load_corpus_name_from_file() -> str:
    try:
        if CORPUS_NAME_FILE.exists():
            return CORPUS_NAME_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _poll_import_operation(operation, timeout_s: int = 300, poll_interval_s: int = 10) -> None:
    if hasattr(operation, "result"):
        try:
            operation.result(timeout=timeout_s)
        except Exception as e:
            print(f"[rag_store] Operation polling warning: {e}")
        return
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if getattr(operation, "done", lambda: True)():
            return
        time.sleep(poll_interval_s)


def _load_registry_sources() -> list[dict[str, Any]]:
    try:
        data = json.loads(ORACLE_SOURCE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[rag_store] Could not load Oracle source registry: {e}")
        return []


def _parse_oracle_links_env() -> list[dict[str, Any]]:
    raw = _cfg("ORACLE_LINKS")
    if not raw:
        return []
    items: list[dict[str, Any]] = []
    for index, url in enumerate(raw.split(","), start=1):
        clean = url.strip()
        if not clean:
            continue
        items.append(
            {
                "title": f"Oracle Link {index}",
                "url": clean,
                "products": list(_detect_oracle_products(clean)),
                "domain": "oracle" if "oracle.com" in clean else "external",
                "keywords": [],
            }
        )
    return items


def _detect_oracle_products(text: str) -> set[str]:
    haystack = text.lower()
    matched: set[str] = set()
    for product, patterns in _PRODUCT_PATTERNS.items():
        if any(pattern in haystack for pattern in patterns):
            matched.add(product)
    return matched


def _domain_score(url: str) -> int:
    host = urlparse(url).netloc.lower()
    if host.endswith("docs.oracle.com"):
        return 30
    if host.endswith("oracle.com"):
        return 20
    return 0


def _product_keyword_score(text: str, products: set[str]) -> int:
    if not products:
        return 0
    haystack = text.lower()
    score = 0
    for product in products:
        for pattern in _PRODUCT_PATTERNS.get(product, ()):
            if pattern in haystack:
                score += 4
    return score


def _generic_hub_penalty(url: str, text: str) -> int:
    haystack = f"{url.lower()} {text.lower()[:500]}"
    penalty = 0
    if any(pattern in url.lower() for pattern in _GENERIC_HUB_PATTERNS):
        penalty += 12
    if "get started" in haystack or "all books" in haystack or "top tasks" in haystack:
        penalty += 8
    return penalty


def _extract_best_snippet(text: str, query: str, max_len: int = 320) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    terms = [term for term in _tokenize(query) if len(term) > 2]
    if not terms:
        return normalized[:max_len]

    best_start = 0
    best_score = -1
    window = max_len * 2
    for index in range(0, len(normalized), max_len // 2):
        segment = normalized[index:index + window]
        if not segment:
            break
        lowered = segment.lower()
        score = sum(lowered.count(term) for term in terms)
        if score > best_score:
            best_score = score
            best_start = index

    snippet = normalized[best_start:best_start + max_len].strip()
    if best_start > 0:
        snippet = f"... {snippet}"
    if best_start + max_len < len(normalized):
        snippet = f"{snippet} ..."
    return snippet


def _source_quality(source: dict[str, Any], products: set[str]) -> int:
    score = _domain_score(str(source.get("url", "")))
    source_products = set(source.get("products", []))
    if products and source_products.intersection(products):
        score += 35
    elif products and source_products:
        score -= 10
    return score


def _oracle_focus_query(query: str) -> tuple[str, set[str]]:
    products = _detect_oracle_products(query)
    product_text = ", ".join(sorted(products)) if products else "fusion, jde, ebs, epm"
    focused = (
        f"Oracle documentation grounding only. Prioritize {product_text}. "
        f"Reject generic guidance. Query: {query}"
    )
    return focused, products


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunks.append(normalized[start:end].strip())
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _fetch_page_text(url: str) -> str:
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "CodeLens-RAG/1.0"})
            response.raise_for_status()
    except Exception as e:
        print(f"[rag_store] Could not fetch {url}: {e}")
        return ""
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{2,}", "\n", text)


def _refresh_oracle_docs_cache() -> None:
    global _oracle_docs, _oracle_docs_loaded
    if _oracle_docs_loaded:
      return

    registry = _load_registry_sources() + _parse_oracle_links_env()
    seen_urls: set[str] = set()
    docs: list[dict[str, Any]] = []

    try:
        if ORACLE_CACHE_FILE.exists():
            cached = json.loads(ORACLE_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                docs.extend(cached)
    except Exception as e:
        print(f"[rag_store] Could not read Oracle cache: {e}")

    for doc in docs:
        url = str(doc.get("url", "")).strip()
        if url:
            seen_urls.add(url)

    for source in registry:
        url = str(source.get("url", "")).strip()
        if not url or url in seen_urls:
            continue
        text = _fetch_page_text(url)
        if not text:
            continue
        docs.append(
            {
                "title": source.get("title", url),
                "url": url,
                "products": source.get("products", []),
                "keywords": source.get("keywords", []),
                "domain": source.get("domain", "oracle"),
                "text": text[:50000],
                "chunks": _chunk_text(text[:50000]),
            }
        )
        seen_urls.add(url)

    if docs:
        try:
            ORACLE_CACHE_FILE.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"[rag_store] Could not write Oracle cache: {e}")

    _oracle_docs = docs
    _oracle_docs_loaded = True


def _local_oracle_retrieval(query: str, k: int, products: set[str]) -> list[dict[str, Any]]:
    _refresh_oracle_docs_cache()
    if not _oracle_docs:
        return []

    query_terms = Counter(_tokenize(query))
    ranked: list[tuple[float, dict[str, Any]]] = []

    for doc in _oracle_docs:
        doc_products = set(doc.get("products", []))
        if products and doc_products and not doc_products.intersection(products):
            continue
        keywords = " ".join(doc.get("keywords", []))
        for chunk in doc.get("chunks", []):
            chunk_terms = Counter(_tokenize(f"{keywords} {chunk}"))
            overlap = sum(min(query_terms[token], chunk_terms[token]) for token in query_terms)
            if overlap <= 0:
                continue
            score = float(
                overlap * 5
                + _source_quality(doc, products)
                + _product_keyword_score(f"{keywords} {chunk}", products)
                - _generic_hub_penalty(str(doc.get("url", "")), chunk)
            )
            ranked.append(
                (
                    score,
                    {
                        "source": doc.get("url", ""),
                        "excerpt": _extract_best_snippet(chunk, query),
                        "text": chunk,
                        "products": list(doc_products),
                        "score": score,
                    },
                )
            )

    ranked.sort(key=lambda item: item[0], reverse=True)
    deduped: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for _, item in ranked:
        source_key = _normalize_source_url(item["source"])
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        deduped.append(item)
        if len(deduped) >= k:
            break
    return deduped


def init_rag_store() -> None:
    global _rag_corpus_name, _rag_ready, _init_attempted

    _refresh_oracle_docs_cache()

    if _rag_ready or _init_attempted:
        return
    _init_attempted = True

    project = _cfg("GCP_PROJECT_ID")
    location = _cfg("GCP_LOCATION", "us-central1")
    gcs_uri = _cfg("GCS_BUCKET_URI")
    corpus_id = _cfg("RAG_CORPUS_ID")

    if not project or not _import_vertexai():
        return

    import vertexai
    from vertexai.preview import rag

    credentials = None
    creds_path = _cfg("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        try:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except Exception as e:
            print(f"[rag_store] Could not load service account credentials: {e}")

    try:
        vertexai.init(project=project, location=location, credentials=credentials)
    except Exception as e:
        print(f"[rag_store] vertexai.init failed: {e}")
        return

    corpus_name = (_resolve_corpus_name(corpus_id, project, location) if corpus_id else "") or _load_corpus_name_from_file()
    if corpus_name:
        try:
            rag.get_corpus(name=corpus_name)
            _rag_corpus_name = corpus_name
            _rag_ready = True
            return
        except Exception:
            corpus_name = ""

    if not gcs_uri:
        return

    try:
        corpus = rag.create_corpus(
            display_name="codelens-rag",
            description="CodeLens Oracle org standards",
        )
        corpus_name = corpus.name
    except Exception as e:
        print(f"[rag_store] Failed to create corpus: {e}")
        return

    try:
        op = rag.import_files(
            corpus_name,
            paths=[gcs_uri.rstrip("/") + "/"],
            chunk_size=1024,
            chunk_overlap=120,
        )
        _poll_import_operation(op)
    except Exception as e:
        print(f"[rag_store] PDF import failed: {e}")

    _rag_corpus_name = corpus_name
    _rag_ready = True
    _save_corpus_name(corpus_name)


def _vertex_retrieval(query: str, k: int, products: set[str]) -> list[dict[str, Any]]:
    global _rag_corpus_name, _rag_ready
    if not _rag_ready:
        init_rag_store()
    if not _rag_ready or not _rag_corpus_name or not _import_vertexai():
        return []

    from vertexai.preview import rag

    try:
        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=_rag_corpus_name)],
            text=query,
            similarity_top_k=max(k * 2, 6),
        )
    except Exception as e:
        print(f"[rag_store] retrieval_query failed: {e}")
        return []

    items: list[dict[str, Any]] = []
    try:
        for ctx in response.contexts.contexts:
            source = getattr(ctx, "source_uri", "") or getattr(ctx, "source_display_name", "oracle-source")
            text = getattr(ctx, "text", "").strip()
            if not text:
                continue
            detected = _detect_oracle_products(f"{source}\n{text}")
            if products and detected and not detected.intersection(products):
                continue
            source_meta = {"url": source, "products": list(detected)}
            score = (
                _source_quality(source_meta, products)
                + len(set(_tokenize(query)).intersection(set(_tokenize(text)))) * 4
                + _product_keyword_score(text, products)
                - _generic_hub_penalty(source, text)
            )
            items.append(
                {
                    "source": source,
                    "excerpt": _extract_best_snippet(text, query),
                    "text": text,
                    "products": list(detected),
                    "score": score,
                }
            )
    except Exception as e:
        print(f"[rag_store] Response parsing error: {e}")
        return []

    items.sort(key=lambda item: item["score"], reverse=True)
    return items[:k]


def _merge_hits(primary: list[dict[str, Any]], secondary: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for collection in (primary, secondary):
        for item in collection:
            key = _normalize_source_url(item["source"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    merged.sort(key=lambda item: item.get("score", 0), reverse=True)
    return merged[:k]


def _retrieve_chunks(query: str, k: int = 5) -> tuple[list[str], list[dict[str, str]], dict[str, Any]]:
    focused_query, products = _oracle_focus_query(query)
    local_hits = _local_oracle_retrieval(focused_query, max(k, 5), products)
    vertex_hits = _vertex_retrieval(focused_query, max(k, 5), products)
    hits = _merge_hits(local_hits, vertex_hits, max(k, 5))

    if products:
        strict_hits = [hit for hit in hits if set(hit.get("products", [])).intersection(products)]
        if strict_hits:
            hits = strict_hits[: max(k, 5)]

    prompt_chunks: list[str] = []
    citations: list[dict[str, str]] = []
    for hit in hits:
        prompt_chunks.append(f"Oracle Source ({hit['source']}):\n{hit['text'].strip()}")
        citations.append({"source": hit["source"], "excerpt": hit["excerpt"]})

    diagnostics = {
        "products": sorted(products),
        "local_hits": len(local_hits),
        "vertex_hits": len(vertex_hits),
        "returned_hits": len(hits),
        "source_domains": sorted({urlparse(hit["source"]).netloc.lower() for hit in hits if hit.get("source")}),
    }
    return prompt_chunks, citations, diagnostics


def get_rag_context(query: str, k: int = 5) -> str:
    prompt_chunks, _, _ = _retrieve_chunks(query, k)
    return "\n\n".join(prompt_chunks)


def get_rag_citations(query: str, k: int = 5) -> list[dict[str, str]]:
    _, citations, _ = _retrieve_chunks(query, k)
    return citations


def get_rag_diagnostics(query: str, k: int = 5) -> dict[str, Any]:
    _, _, diagnostics = _retrieve_chunks(query, k)
    return diagnostics

from __future__ import annotations

import re

from app.config import get_settings
from app.schemas import RetrievalBundle, RetrievalHit
from rag.embeddings import cosine_sparse, dense_similarity, sparse_vector
from rag.indexing import get_corpus_index

settings = get_settings()

PRODUCT_PATTERNS: dict[str, tuple[str, ...]] = {
    "fusion": ("fusion", "saas", "poz_suppliers", "bi publisher", "procurement"),
    "jde": ("jde", "jd edwards", "enterpriseone", "orchestration"),
    "ebs": ("ebs", "e-business", "ap_invoices_all", "concurrent", "sqlplus"),
    "epm": ("epm", "planning", "budget", "hyperion"),
}


def infer_product(text: str) -> str:
    lowered = text.lower()
    for product, patterns in PRODUCT_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return product
    return ""


def build_query(*, code: str, language: str, label: str) -> str:
    return f"Artifact label: {label}\nLanguage: {language}\nArtifact:\n{code[:1600]}"


def retrieve_bundle(query: str, *, preferred_product: str = "") -> RetrievalBundle:
    corpus = get_corpus_index()
    inferred_product = preferred_product or infer_product(query)
    query_sparse = sparse_vector(query)
    hits: list[RetrievalHit] = []

    for chunk in corpus.chunks:
        if inferred_product and chunk.product and chunk.product != inferred_product:
            continue
        sparse_score = cosine_sparse(query_sparse, chunk.sparse)
        if sparse_score <= 0:
            continue
        dense_score = dense_similarity(query, chunk.text)
        fused_score = sparse_score * 0.7 + dense_score * 0.3
        hits.append(
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                title=chunk.title,
                section_path=chunk.section_path,
                product=chunk.product,
                text=chunk.text,
                excerpt=chunk.excerpt,
                dense_score=round(dense_score, 6),
                sparse_score=round(sparse_score, 6),
                fused_score=round(fused_score, 6),
            )
        )

    if not hits and inferred_product:
        return retrieve_bundle(query, preferred_product="")

    hits.sort(key=lambda item: (item.fused_score, item.sparse_score), reverse=True)
    return RetrievalBundle(
        query=query,
        inferred_product=inferred_product,
        corpus_version=corpus.version,
        lexical_candidates=hits[: settings.lexical_top_k],
        reranked_hits=[],
    )


def sanitize_source_name(source: str) -> str:
    return re.sub(r"^https?://", "", source.lower()).rstrip("/")

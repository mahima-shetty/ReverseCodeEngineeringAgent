from __future__ import annotations

import re

from app.config import get_settings
from app.schemas import RetrievalHit

settings = get_settings()


def rerank_hits(query: str, hits: list[RetrievalHit], *, top_k: int | None = None) -> list[RetrievalHit]:
    query_terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]+", query.lower()))
    reranked: list[RetrievalHit] = []
    for hit in hits:
        text_terms = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]+", hit.text.lower()))
        overlap = len(query_terms.intersection(text_terms))
        source_bonus = 1.0 if hit.product and hit.product in query.lower() else 0.0
        hit.rerank_score = round(hit.fused_score + overlap * 0.01 + source_bonus * 0.05, 6)
        reranked.append(hit)
    reranked.sort(key=lambda item: item.rerank_score, reverse=True)
    return reranked[: top_k or settings.top_reranked_hits]

from __future__ import annotations

from app.schemas import RagCitation, RetrievalHit


def build_citations(hits: list[RetrievalHit]) -> list[RagCitation]:
    return [
        RagCitation(
            chunk_id=hit.chunk_id,
            source=hit.source,
            excerpt=hit.excerpt,
            product=hit.product,
        )
        for hit in hits
    ]

"""
Compatibility shim for the legacy RAG API.

The old backend called `get_rag_context`, `get_rag_citations`, and
`get_rag_diagnostics` separately, which triggered repeated retrieval work and
source-level dedupe bugs. The redesigned backend uses a single-pass retrieval
bundle. These helpers now expose the same legacy functions on top of the new
retrieval path.
"""

from __future__ import annotations

from app.schemas import RetrievalBundle
from rag.rerank import rerank_hits
from rag.retrieval import retrieve_bundle


def init_rag_store() -> None:
    """No-op retained for backwards compatibility."""


def _bundle(query: str, k: int = 5) -> RetrievalBundle:
    bundle = retrieve_bundle(query)
    bundle.reranked_hits = rerank_hits(query, bundle.lexical_candidates, top_k=k)
    return bundle


def get_rag_context(query: str, k: int = 5) -> str:
    bundle = _bundle(query, k=k)
    return "\n\n".join(f"Source: {hit.source}\n{hit.text}" for hit in bundle.reranked_hits)


def get_rag_citations(query: str, k: int = 5) -> list[dict[str, str]]:
    bundle = _bundle(query, k=k)
    return [
        {
            "chunk_id": hit.chunk_id,
            "source": hit.source,
            "excerpt": hit.excerpt,
        }
        for hit in bundle.reranked_hits
    ]


def get_rag_diagnostics(query: str, k: int = 5) -> dict[str, object]:
    bundle = _bundle(query, k=k)
    return {
        "products": [hit.product for hit in bundle.reranked_hits if hit.product],
        "returned_hits": len(bundle.reranked_hits),
        "candidate_hits": len(bundle.lexical_candidates),
        "corpus_version": bundle.corpus_version,
    }


def retrieve_context_bundle(query: str, k: int = 5) -> RetrievalBundle:
    return _bundle(query, k=k)

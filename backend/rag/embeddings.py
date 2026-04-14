from __future__ import annotations

import math
import re
from collections import Counter

from app.config import get_settings

settings = get_settings()

_encoder = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]+", text.lower())


def sparse_vector(text: str) -> Counter[str]:
    return Counter(_tokenize(text))


def cosine_sparse(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    numerator = sum(a[token] * b.get(token, 0) for token in a)
    a_norm = math.sqrt(sum(value * value for value in a.values()))
    b_norm = math.sqrt(sum(value * value for value in b.values()))
    if not a_norm or not b_norm:
        return 0.0
    return numerator / (a_norm * b_norm)


def dense_encoder():
    global _encoder
    if _encoder is not None:
        return _encoder
    try:
        from sentence_transformers import SentenceTransformer

        _encoder = SentenceTransformer(settings.local_embedding_model)
    except Exception:
        _encoder = False
    return _encoder


def dense_similarity(query: str, text: str) -> float:
    model = dense_encoder()
    if not model:
        return 0.0
    try:
        query_vec = model.encode([query], normalize_embeddings=True)
        text_vec = model.encode([text], normalize_embeddings=True)
        return float((query_vec[0] * text_vec[0]).sum())
    except Exception:
        return 0.0

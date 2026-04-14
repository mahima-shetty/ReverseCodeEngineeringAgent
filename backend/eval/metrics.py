from __future__ import annotations


def bounded_percent(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def recall_at_k(qrels: list[str], ranked_ids: list[str], k: int) -> float:
    gold = list(dict.fromkeys(qrels))
    if not gold:
        return 100.0
    retrieved = set(ranked_ids[:k])
    hits = sum(1 for item in gold if item in retrieved)
    return bounded_percent((hits / len(gold)) * 100)


def mrr(qrels: list[str], ranked_ids: list[str]) -> float:
    gold = set(qrels)
    if not gold:
        return 100.0
    for index, item in enumerate(ranked_ids, start=1):
        if item in gold:
            return bounded_percent((1 / index) * 100)
    return 0.0


def citation_precision(expected_sources: list[str], actual_sources: list[str]) -> float:
    if not actual_sources:
        return 0.0
    expected = [item.lower() for item in expected_sources]
    hits = 0
    for source in actual_sources:
        source_lower = source.lower()
        if any(expected_source in source_lower for expected_source in expected):
            hits += 1
    return bounded_percent((hits / len(actual_sources)) * 100)


def claim_support_rate(expected_claims: list[str], actual_claims: list[str]) -> float:
    if not expected_claims:
        return 100.0
    matches = 0
    actual_lower = [item.lower() for item in actual_claims]
    for claim in expected_claims:
        if any(claim.lower() in candidate for candidate in actual_lower):
            matches += 1
    return bounded_percent((matches / len(expected_claims)) * 100)


def unsupported_claim_rate(forbidden_claims: list[str], actual_claims: list[str], unsupported_claims: list[str]) -> float:
    actual_lower = [item.lower() for item in actual_claims]
    forbidden_hits = 0
    for claim in forbidden_claims:
        if any(claim.lower() in candidate for candidate in actual_lower):
            forbidden_hits += 1
    total = max(1, len(actual_claims))
    rate = ((forbidden_hits + len(unsupported_claims)) / total) * 100
    return bounded_percent(rate)


def grounded_accuracy(
    *,
    claim_support: float,
    unsupported_rate: float,
    citation_precision_value: float,
    recall_value: float,
) -> float:
    return bounded_percent(
        (claim_support + max(0.0, 100.0 - unsupported_rate) + citation_precision_value + recall_value) / 4
    )

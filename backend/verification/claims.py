from __future__ import annotations

import re

from app.schemas import AnalysisOutput, ClaimVerification, RetrievalHit, VerificationSummary


def extract_claims(output: AnalysisOutput) -> list[tuple[str, list[str]]]:
    claims: list[tuple[str, list[str]]] = []
    if output.summary_oneliner:
        claims.append((output.summary_oneliner, ["summary_oneliner"]))
    if output.functional_purpose:
        claims.append((output.functional_purpose, ["functional_purpose"]))
    for field_name, values in (
        ("business_logic", output.business_logic),
        ("dataflow_steps", output.dataflow_steps),
        ("functional_inputs", output.functional_inputs),
        ("functional_outputs", output.functional_outputs),
    ):
        for value in values:
            claims.append((value, [field_name]))
    for issue in output.security_issues:
        claims.append((issue.description, ["security_issues"]))
    for item in output.antipatterns:
        claims.append((item.description or item.pattern, ["antipatterns"]))
    for item in output.refactor_recommendations:
        claims.append((item.description or item.title, ["refactor_recommendations"]))
    return claims


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]+", text.lower()))


def verify_claims(output: AnalysisOutput, hits: list[RetrievalHit]) -> VerificationSummary:
    verification_items: list[ClaimVerification] = []
    unsupported: list[str] = []
    hit_tokens = {hit.chunk_id: _tokens(hit.text) for hit in hits}

    for claim_text, source_fields in extract_claims(output):
        claim_tokens = _tokens(claim_text)
        best_chunk_id = ""
        best_score = 0.0
        for hit in hits:
            evidence_tokens = hit_tokens[hit.chunk_id]
            if not claim_tokens or not evidence_tokens:
                continue
            overlap = len(claim_tokens.intersection(evidence_tokens)) / max(1, len(claim_tokens))
            if overlap > best_score:
                best_score = overlap
                best_chunk_id = hit.chunk_id
        if best_score >= 0.45:
            status = "supported"
        elif best_score >= 0.2:
            status = "weakly_supported"
        else:
            status = "unsupported"
            unsupported.append(claim_text)
        verification_items.append(
            ClaimVerification(
                claim=claim_text,
                source_fields=source_fields,
                status=status,
                evidence_chunk_ids=[best_chunk_id] if best_chunk_id else [],
                confidence=round(best_score * 100, 2),
            )
        )

    total = len(verification_items)
    supported_count = sum(1 for item in verification_items if item.status == "supported")
    unsupported_count = sum(1 for item in verification_items if item.status == "unsupported")
    supported_rate = round((supported_count / max(1, total)) * 100, 2)
    unsupported_rate = round((unsupported_count / max(1, total)) * 100, 2)
    grounded_accuracy = round(max(0.0, min(100.0, supported_rate - (unsupported_rate * 0.25))), 2)
    return VerificationSummary(
        claims=verification_items,
        supported_claim_rate=supported_rate,
        unsupported_claim_rate=unsupported_rate,
        grounded_accuracy=grounded_accuracy,
        unsupported_claims=unsupported[:20],
    )

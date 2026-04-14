from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from app.config import get_settings
from app.schemas import (
    AnalysisOutput,
    AnalyzeInput,
    AnalyzeItemResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeSummary,
    JudgeEvaluation,
    ProviderUsage,
)
from agents.state import ReviewGraphState
from agents.tools import heuristic_analysis
from observability.tracing import TraceRecorder, overwrite_latest_usage, write_llm_output, write_llm_request, write_usage_entry
from providers.blueverse import call_blueverse
from providers.groq import call_groq
from providers.openai import call_openai
from rag.citations import build_citations
from rag.rerank import rerank_hits
from rag.retrieval import build_query, infer_product, retrieve_bundle, sanitize_source_name
from verification.claims import verify_claims

settings = get_settings()


def _strip_json_schema_metadata(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if key in {"title", "default", "examples"}:
                continue
            cleaned[key] = _strip_json_schema_metadata(item)
        return cleaned
    if isinstance(value, list):
        return [_strip_json_schema_metadata(item) for item in value]
    return value


def _analysis_output_response_schema() -> dict[str, object]:
    raw_schema = AnalysisOutput.model_json_schema()
    schema = _strip_json_schema_metadata(raw_schema)
    return {
        "name": "analysis_output",
        "strict": False,
        "schema": schema,
    }


def _normalize_confidence(value: object) -> int:
    if value is None or value == "":
        return 0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0
    if 0.0 <= numeric <= 1.0:
        numeric *= 100.0
    return max(0, min(100, int(round(numeric))))


def _normalize_list_of_dicts(value: object, *, confidence_key: str = "confidence_score") -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    normalized_items: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        normalized = dict(item)
        if confidence_key in normalized:
            normalized[confidence_key] = _normalize_confidence(normalized.get(confidence_key))
        normalized_items.append(normalized)
    return normalized_items


def _trim_text(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit - 3].rstrip()}..."


def _prompt_citations(state: ReviewGraphState) -> list[dict[str, object]]:
    citations: list[dict[str, object]] = []
    for hit in state.retrieval.reranked_hits[:3]:
        citations.append(
            {
                "chunk_id": hit.chunk_id,
                "source": hit.source,
                "title": hit.title,
                "section_path": hit.section_path,
                "product": hit.product,
                "excerpt": _trim_text(hit.excerpt or hit.text, 320),
                "rerank_score": hit.rerank_score,
            }
        )
    return citations


def _coerce_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _append_security_issue(
    issues: list[dict[str, object]],
    *,
    issue_type: str,
    description: str,
    evidence_items: object,
    severity: str = "HIGH",
    confidence: int = 85,
) -> None:
    evidence_list = _coerce_str_list(evidence_items)
    issues.append(
        {
            "severity": severity,
            "type": issue_type,
            "description": description,
            "confidence_score": confidence,
            "evidence": "; ".join(evidence_list[:3]),
        }
    )


def _append_antipattern(
    antipatterns: list[dict[str, object]],
    *,
    pattern: str,
    description: str,
    recommendation: str,
    evidence_items: object,
    severity: str = "HIGH",
    confidence: int = 85,
) -> None:
    evidence_list = _coerce_str_list(evidence_items)
    antipatterns.append(
        {
            "severity": severity,
            "pattern": pattern,
            "description": description,
            "recommendation": recommendation,
            "confidence_score": confidence,
            "evidence": "; ".join(evidence_list[:3]),
        }
    )


def _append_refactor(
    refactors: list[dict[str, object]],
    *,
    title: str,
    description: str,
    benefit: str,
    code_hint: str,
    evidence_items: object,
    priority: str = "HIGH",
    confidence: int = 80,
) -> None:
    evidence_list = _coerce_str_list(evidence_items)
    refactors.append(
        {
            "priority": priority,
            "title": title,
            "description": description,
            "benefit": benefit,
            "codeHint": code_hint,
            "confidence_score": confidence,
            "evidence": "; ".join(evidence_list[:3]),
        }
    )


def _merge_provider_alias_findings(normalized: dict[str, object]) -> None:
    security_issues = _normalize_list_of_dicts(normalized.get("security_issues"))
    antipatterns = _normalize_list_of_dicts(normalized.get("antipatterns"))
    refactors = _normalize_list_of_dicts(normalized.get("refactor_recommendations"))
    hardcoded_items = _normalize_list_of_dicts(normalized.get("hardcoded_items"), confidence_key="unused")

    if _coerce_str_list(normalized.get("dynamic_sql")):
        _append_security_issue(
            security_issues,
            issue_type="Dynamic SQL execution",
            description="The artifact constructs and executes dynamic SQL, increasing injection and auditability risk.",
            evidence_items=normalized.get("dynamic_sql"),
        )
        _append_antipattern(
            antipatterns,
            pattern="Dynamic SQL built by concatenation",
            description="SQL text is assembled by string concatenation instead of bind-safe parameterization.",
            recommendation="Replace concatenated dynamic SQL with static SQL or bind variables.",
            evidence_items=normalized.get("dynamic_sql"),
        )

    if _coerce_str_list(normalized.get("broad_exception_handlers")):
        _append_security_issue(
            security_issues,
            issue_type="Broad exception handling",
            description="The artifact catches all exceptions and hides the specific failure mode.",
            evidence_items=normalized.get("broad_exception_handlers"),
        )

    if _coerce_str_list(normalized.get("hardcoded_constants")):
        for evidence in _coerce_str_list(normalized.get("hardcoded_constants")):
            hardcoded_items.append(
                {
                    "type": "constant",
                    "description": "Business or environment literal is embedded directly in code.",
                    "evidence": evidence,
                }
            )
        _append_antipattern(
            antipatterns,
            pattern="Hardcoded business rules and constants",
            description="Business thresholds, rates, or environment constants are embedded directly in code.",
            recommendation="Move business constants into configuration or rule tables.",
            evidence_items=normalized.get("hardcoded_constants"),
        )
        _append_refactor(
            refactors,
            title="Externalize business constants",
            description="Extract hardcoded limits, rates, regions, and currency values into configuration or reference tables.",
            benefit="Improves maintainability and reduces release risk when business rules change.",
            code_hint="Replace literals with lookups from configuration tables or package constants.",
            evidence_items=normalized.get("hardcoded_constants"),
        )

    if _coerce_str_list(normalized.get("transaction_control")):
        _append_antipattern(
            antipatterns,
            pattern="Commit inside procedure or script",
            description="Internal transaction control can break caller-managed transaction boundaries.",
            recommendation="Remove internal commits or isolate transaction ownership behind a well-defined boundary.",
            evidence_items=normalized.get("transaction_control"),
        )

    if _coerce_str_list(normalized.get("dml_without_column_lists")):
        _append_antipattern(
            antipatterns,
            pattern="INSERT without explicit column list",
            description="Positional INSERT statements are brittle and can break when the schema changes.",
            recommendation="Specify column names explicitly in every INSERT statement.",
            evidence_items=normalized.get("dml_without_column_lists"),
        )

    if _coerce_str_list(normalized.get("row_by_row_processing")):
        _append_antipattern(
            antipatterns,
            pattern="Row-by-row query processing",
            description="Loop-driven row processing is less scalable than set-based SQL and bulk operations.",
            recommendation="Replace row-by-row loops with set-based DML or BULK COLLECT/FORALL where feasible.",
            evidence_items=normalized.get("row_by_row_processing"),
        )

    if _coerce_str_list(normalized.get("credential_exposure")):
        _append_security_issue(
            security_issues,
            issue_type="Sensitive identity handling",
            description="The provider flagged possible handling of sensitive user or credential-like values that should be reviewed.",
            evidence_items=normalized.get("credential_exposure"),
            severity="MEDIUM",
            confidence=60,
        )

    if _coerce_str_list(normalized.get("endpoint_hardcoding")):
        _append_antipattern(
            antipatterns,
            pattern="Hardcoded endpoint or routing value",
            description="Environment- or routing-specific values appear to be embedded directly in code.",
            recommendation="Move endpoint and routing values into configuration.",
            evidence_items=normalized.get("endpoint_hardcoding"),
            severity="MEDIUM",
            confidence=60,
        )

    normalized["security_issues"] = security_issues
    normalized["hardcoded_items"] = hardcoded_items
    normalized["antipatterns"] = antipatterns
    normalized["refactor_recommendations"] = refactors


def _ensure_inputs(req: AnalyzeRequest) -> list[AnalyzeInput]:
    if req.inputs:
        return [item for item in req.inputs if item.code.strip()]
    if req.code.strip():
        return [AnalyzeInput(id="input-1", code=req.code, language="auto", label="Input 1")]
    return []


def _coerce_output(payload: dict[str, object]) -> AnalysisOutput:
    if not payload:
        raise ValueError("Provider returned empty JSON object")
    allowed = AnalysisOutput.model_fields.keys()
    normalized = {key: value for key, value in payload.items() if key in allowed}
    for alias in (
        "hardcoded_constants",
        "dynamic_sql",
        "broad_exception_handlers",
        "transaction_control",
        "dml_without_column_lists",
        "row_by_row_processing",
        "credential_exposure",
        "endpoint_hardcoding",
    ):
        if alias in payload:
            normalized[alias] = payload.get(alias)
    _merge_provider_alias_findings(normalized)
    normalized["hardcoded_items"] = _normalize_list_of_dicts(normalized.get("hardcoded_items"), confidence_key="unused")
    normalized["test_scenarios"] = _normalize_list_of_dicts(normalized.get("test_scenarios"), confidence_key="unused")
    if "summary_oneliner" not in normalized or not str(normalized.get("summary_oneliner", "")).strip():
        fallback_summary = str(normalized.get("functional_purpose", "")).strip()
        normalized["summary_oneliner"] = fallback_summary or "Structured analysis generated by provider."
    return AnalysisOutput.model_validate(normalized)


def _build_provider_prompt(input_item: AnalyzeInput, state: ReviewGraphState) -> str:
    instruction = {
        "task": "Analyze the artifact and return ONLY one JSON object that matches the response schema enforced by the API.",
        "rules": [
            "Do not return markdown, explanations, or code fences.",
            "Do not return an empty object.",
            "Always populate summary_oneliner, functional_purpose, summary_complexity, and summary_risk.",
            "Always populate functional_inputs, functional_outputs, and testable_interpretation with concrete bullet-sized strings when they can be inferred from the artifact.",
            "Populate jira_tickets with concrete remediation tasks when you identify high-severity security issues, high-severity anti-patterns, or high-priority refactor recommendations. Use an empty list only when no actionable remediation ticket is justified.",
            "If you have no values for a list field, return an empty list.",
            "Ground claims in the provided citations when relevant and do not invent Oracle product facts.",
            "Use integer confidence_score values in the range 0-100.",
            "For PL/SQL, SQL, Groovy, and BIP artifacts explicitly look for hardcoded constants, business rules, dynamic SQL, SQL string concatenation, broad exception handlers, transaction control, DML without column lists, row-by-row processing, credential exposure, and endpoint hardcoding.",
            "For functional_inputs include procedure parameters, key tables read, or external inputs. For functional_outputs include tables updated/inserted, statuses changed, or externally visible outputs. For testable_interpretation include concrete checks that QA can validate from the artifact behavior.",
            "Populate dataflow_steps with concrete processing steps. Populate dataflow_tables and dataflow_transformations when they can be inferred from the artifact.",
            "Populate complexity_score, nesting_depth, maintainability, readability, and testability with concise values that reflect code complexity and maintainability.",
            "Populate hardcoded_items when literals, thresholds, credentials, currencies, regions, or endpoints are embedded directly in code.",
            "Populate test_scenarios with QA-ready scenarios when behavior, edge cases, security risks, or regressions can be tested from the artifact.",
            "Populate impact_summary with business_impact, risk_overview, risk_level, and top_actions for project-manager consumption.",
            "For jira_tickets include title, description, story_points, and type. Prefer Task, Bug, or Security as the type.",
        ],
        "artifact_label": input_item.label or input_item.id,
        "language": input_item.language or "auto",
        "product": state.inferred_product or "",
        "artifact": _trim_text(input_item.code, 5000),
        "citations": _prompt_citations(state),
    }
    return json.dumps(instruction, ensure_ascii=False)


def _build_repair_prompt(original_prompt: str, raw_output: str, validation_error: str) -> str:
    return json.dumps(
        {
            "task": "Repair the previous JSON so it matches the enforced schema exactly.",
            "rules": [
                "Return only corrected JSON.",
                "Do not omit required fields.",
                "Use integer confidence_score values in the range 0-100.",
                "Preserve semantic content where possible while fixing schema violations.",
            ],
            "original_request": json.loads(original_prompt),
            "previous_output": raw_output,
            "validation_error": validation_error,
        },
        ensure_ascii=False,
    )


async def _provider_call(
    provider: str,
    prompt: str,
    req: AnalyzeRequest,
    *,
    response_schema: dict[str, object] | None = None,
) -> dict[str, object]:
    if provider == "groq":
        return await call_groq(prompt, response_schema=response_schema)
    if provider == "blueverse":
        return await call_blueverse(
            prompt=prompt,
            endpoint=req.endpoint,
            token=req.token,
            response_schema=response_schema,
        )
    if provider == "openai":
        return await call_openai(prompt, response_schema=response_schema)
    raise RuntimeError(f"Unsupported provider: {provider}")


async def _provider_analysis(
    prompt: str,
    req: AnalyzeRequest,
    *,
    input_id: str,
) -> tuple[AnalysisOutput | None, ProviderUsage | None, list[str]]:
    failures: list[str] = []
    response_schema = _analysis_output_response_schema()
    for provider in settings.provider_order:
        usage = ProviderUsage(provider=provider, model=provider)
        try:
            if provider == "heuristic":
                return None, ProviderUsage(provider="heuristic", model="local", raw_status="ok"), failures
            attempt_prompt = prompt
            usage_totals = {"input_tokens": 0, "output_tokens": 0}
            last_usage = usage
            for attempt in range(settings.provider_validation_retries + 1):
                result = await _provider_call(provider, attempt_prompt, req, response_schema=response_schema)
                write_llm_request(
                    provider=result["provider"],
                    input_id=input_id,
                    attempt=attempt + 1,
                    request_url=str(result.get("request_url", "")),
                    request_body=result.get("request_body"),
                )
                provider_usage = result.get("usage", {})
                usage_totals["input_tokens"] += int(provider_usage.get("input_tokens") or 0)
                usage_totals["output_tokens"] += int(provider_usage.get("output_tokens") or 0)
                last_usage = ProviderUsage(
                    provider=result["provider"],
                    model=result["model"],
                    input_tokens=usage_totals["input_tokens"],
                    output_tokens=usage_totals["output_tokens"],
                    total_tokens=usage_totals["input_tokens"] + usage_totals["output_tokens"],
                    cost_usd=0.0,
                    raw_status="ok",
                )
                try:
                    output = _coerce_output(result["payload"])
                    write_llm_output(
                        provider=result["provider"],
                        input_id=input_id,
                        attempt=attempt + 1,
                        prompt=attempt_prompt,
                        raw_text=str(result.get("raw_text", "")),
                        payload=result.get("payload"),
                        validation_status="passed",
                    )
                    return output, last_usage, failures
                except (ValidationError, ValueError) as exc:
                    write_llm_output(
                        provider=result["provider"],
                        input_id=input_id,
                        attempt=attempt + 1,
                        prompt=attempt_prompt,
                        raw_text=str(result.get("raw_text", "")),
                        payload=result.get("payload"),
                        validation_status="failed",
                        validation_error=str(exc),
                    )
                    if attempt >= settings.provider_validation_retries:
                        raise
                    attempt_prompt = _build_repair_prompt(prompt, str(result.get("raw_text", "")), str(exc))
                    continue
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            usage.raw_status = "failed"
            usage.error_message = message
            failures.append(f"{provider} failed: {message}")
            write_usage_entry(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "provider": provider,
                    "status": "failed",
                    "error_message": message,
                }
            )
            continue
    return None, None, failures


def _judge_from_state(state: ReviewGraphState) -> JudgeEvaluation:
    verification = state.verification
    retrieval = state.retrieval
    supported_rate = verification.supported_claim_rate if verification else 0.0
    unsupported_rate = verification.unsupported_claim_rate if verification else 100.0
    citation_sources = [sanitize_source_name(hit.source) for hit in (retrieval.reranked_hits if retrieval else [])]
    product = state.inferred_product
    oracle_grounding = 100.0 if citation_sources and all((not product) or product in source for source in citation_sources) else 60.0 if citation_sources else 0.0
    accuracy = round((supported_rate + max(0.0, 100.0 - unsupported_rate) + oracle_grounding) / 3, 2)
    if accuracy >= 80 and unsupported_rate <= 15:
        status = "approved"
    elif accuracy >= 55 and unsupported_rate <= 40:
        status = "flagged"
    else:
        status = "rejected"
    return JudgeEvaluation(
        scores={
            "completeness": round(supported_rate, 2),
            "correctness": round(accuracy, 2),
            "hallucination": round(unsupported_rate, 2),
        },
        validation={
            "accuracy": round(accuracy, 2),
            "oracle_grounding": round(oracle_grounding, 2),
            "oracle_specificity": round(oracle_grounding, 2),
        },
        finding_metrics={
            "precision": round(max(0.0, 100.0 - unsupported_rate), 2),
            "recall": round(supported_rate, 2),
            "false_positive_rate": round(unsupported_rate, 2),
        },
        latency_metrics={},
        thresholds={
            "approved": {"completeness_min": 80, "correctness_min": 80, "hallucination_max": 15, "oracle_grounding_min": 80},
            "flagged": {"completeness_min": 55, "correctness_min": 55, "hallucination_max": 40, "oracle_grounding_min": 40},
        },
        status=status,
        deliverable=status == "approved",
        summary=f"Claim support {supported_rate:.1f}%, unsupported {unsupported_rate:.1f}%, Oracle grounding {oracle_grounding:.1f}%.",
        blocking_issues=(verification.unsupported_claims[:5] if verification else []),
        recommended_action="Deliver response." if status == "approved" else "Hold response and review manually.",
        provider_metadata=state.provider_usage[-1].model_dump() if state.provider_usage else {},
    )


async def _run_review_graph(input_item: AnalyzeInput, req: AnalyzeRequest) -> AnalyzeItemResponse:
    trace = TraceRecorder()
    state = ReviewGraphState(
        input_id=input_item.id,
        label=input_item.label or input_item.id,
        language=input_item.language or "auto",
        artifact=input_item.code,
    )

    with trace.step("classify") as step:
        query = build_query(code=input_item.code, language=input_item.language or "auto", label=input_item.label or input_item.id)
        state.inferred_product = infer_product(query)
        step["details"] = {"inferred_product": state.inferred_product or "unknown"}

    with trace.step("retrieve") as step:
        retrieval = retrieve_bundle(query, preferred_product=state.inferred_product)
        state.retrieval = retrieval
        step["details"] = {"corpus_version": retrieval.corpus_version, "candidate_count": len(retrieval.lexical_candidates)}
        if not retrieval.lexical_candidates:
            step["status"] = "degraded"

    with trace.step("rerank") as step:
        assert state.retrieval is not None
        state.retrieval.reranked_hits = rerank_hits(query, state.retrieval.lexical_candidates)
        step["details"] = {"reranked_count": len(state.retrieval.reranked_hits)}
        if not state.retrieval.reranked_hits:
            step["status"] = "degraded"

    with trace.step("analyze") as step:
        provider_prompt = _build_provider_prompt(input_item, state)
        provider_output, provider_usage, provider_failures = await _provider_analysis(
            provider_prompt,
            req,
            input_id=input_item.id,
        )
        state.provider_failures = provider_failures
        if provider_output is None:
            step["status"] = "degraded"
            state.failure_reason = "; ".join(provider_failures) if provider_failures else "No provider returned valid structured output."
            provider_output = heuristic_analysis(
                code=input_item.code,
                language=input_item.language or "auto",
                inferred_product=state.inferred_product,
            )
            provider_usage = provider_usage or ProviderUsage(provider="heuristic", model="local", raw_status="ok")
            provider_usage.error_message = state.failure_reason
        state.provider_usage.append(provider_usage)
        step["provider"] = provider_usage.provider
        step["details"] = {"provider": provider_usage.provider}
        if provider_failures:
            step["details"]["provider_failures"] = provider_failures
        state.final_output = provider_output

    with trace.step("attach_citations") as step:
        state.final_output.rag_citations = build_citations(state.retrieval.reranked_hits)
        llm_metadata = state.provider_usage[-1].model_dump()
        if state.provider_failures:
            llm_metadata["provider_failures"] = list(state.provider_failures)
        if state.failure_reason:
            llm_metadata["failure_reason"] = state.failure_reason
        state.final_output.llm_metadata = llm_metadata
        step["details"] = {"citation_count": len(state.final_output.rag_citations)}

    with trace.step("verify_claims") as step:
        state.verification = verify_claims(state.final_output, state.retrieval.reranked_hits)
        step["details"] = {
            "supported_claim_rate": state.verification.supported_claim_rate,
            "unsupported_claim_rate": state.verification.unsupported_claim_rate,
        }
        if state.verification.unsupported_claim_rate > 30:
            step["status"] = "degraded"

    judge = _judge_from_state(state)
    analysis_state = "ok"
    if (
        not state.retrieval.reranked_hits
        or state.verification.unsupported_claim_rate > 30
        or (state.provider_usage and state.provider_usage[-1].provider == "heuristic")
    ):
        analysis_state = "degraded"
    total_runtime = round(sum(event.duration_ms for event in trace.events) / 1000, 3)
    first_useful = next((round(event.duration_ms / 1000, 3) for event in trace.events if event.step == "analyze"), total_runtime)
    judge.latency_metrics = {
        "time_to_first_useful_output": first_useful,
        "total_runtime": total_runtime,
    }

    return AnalyzeItemResponse(
        id=input_item.id,
        label=input_item.label or input_item.id,
        language=input_item.language or "auto",
        original_input=input_item.code,
        primary_output=state.final_output,
        final_output=state.final_output,
        retrieval=state.retrieval,
        verification=state.verification,
        execution_trace=trace.events,
        judge_evaluation=judge,
        final_status=judge.status,
        deliverable=judge.deliverable,
        analysis_state=analysis_state,
        render_source="heuristic" if state.provider_usage and state.provider_usage[-1].provider == "heuristic" else "graph",
        failure_reason=state.failure_reason,
        session_id=req.session_id,
    )


async def analyze_batch(req: AnalyzeRequest) -> AnalyzeResponse:
    inputs = _ensure_inputs(req)
    if not inputs:
        raise ValueError("At least one input is required")

    items: list[AnalyzeItemResponse] = []
    usage_entries: list[dict[str, object]] = []
    for input_item in inputs:
        result = await _run_review_graph(input_item, req)
        items.append(result)
        usage_payload = dict(result.final_output.llm_metadata)
        usage_payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        usage_entries.append(usage_payload)
        write_usage_entry(usage_payload)

    overwrite_latest_usage(usage_entries)
    summary = AnalyzeSummary(
        total=len(items),
        approved=sum(1 for item in items if item.final_status == "approved"),
        flagged=sum(1 for item in items if item.final_status == "flagged"),
        rejected=sum(1 for item in items if item.final_status == "rejected"),
    )
    return AnalyzeResponse(items=items, summary=summary)

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from statistics import mean
from uuid import uuid4

from pydantic import ValidationError

from agents.review_graph import analyze_batch
from app.config import get_settings
from app.schemas import (
    AnalyzeInput,
    AnalyzeRequest,
    BenchmarkCase,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    BenchmarkSampleResult,
    BenchmarkSummary,
    CaseKpis,
)
from eval.metrics import (
    claim_support_rate,
    citation_precision,
    grounded_accuracy,
    mrr,
    recall_at_k,
    unsupported_claim_rate,
)

settings = get_settings()


def _load_cases() -> list[BenchmarkCase]:
    payload = json.loads(settings.benchmark_fixture_file.read_text(encoding="utf-8"))
    return [BenchmarkCase.model_validate(item) for item in payload]


def _case_to_request(case: BenchmarkCase, req: BenchmarkRunRequest) -> AnalyzeRequest:
    return AnalyzeRequest(
        endpoint=req.endpoint,
        token=req.token,
        inputs=[
            AnalyzeInput(
                id=case.id,
                label=case.label,
                language=case.language,
                code=case.artifact,
            )
        ],
    )


def _review_time_reduction(baseline_seconds: float, runtime_seconds: float) -> float:
    if baseline_seconds <= 0:
        return 0.0
    return round(max(0.0, ((baseline_seconds - runtime_seconds) / baseline_seconds) * 100), 2)


def _match_lists(expected: list[str], actual: list[str]) -> tuple[list[str], list[str]]:
    actual_lower = [item.lower() for item in actual]
    matched = [item for item in expected if any(item.lower() in candidate for candidate in actual_lower)]
    missed = [item for item in expected if item not in matched]
    return matched, missed


def _write_exports(run_id: str, payload: dict) -> dict[str, str]:
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = settings.evidence_dir / f"{run_id}.json"
    csv_path = settings.evidence_dir / f"{run_id}.csv"
    manifest_path = settings.evidence_dir / f"{run_id}.manifest.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case_id",
                "label",
                "artifact_type",
                "oracle_product",
                "final_status",
                "grounded_accuracy",
                "claim_support_rate",
                "unsupported_claim_rate",
                "citation_precision",
                "recall_at_k",
                "mrr",
                "workflow_success",
                "latency_seconds",
                "cost_per_bundle_usd",
            ]
        )
        for sample in payload["sample_results"]:
            case_kpis = sample["case_kpis"]
            writer.writerow(
                [
                    sample["case_id"],
                    sample["analysis_item"]["label"],
                    sample["artifact_type"],
                    sample["oracle_product"],
                    sample["final_status"],
                    case_kpis["grounded_accuracy"],
                    case_kpis["claim_support_rate"],
                    case_kpis["unsupported_claim_rate"],
                    case_kpis["citation_precision"],
                    case_kpis["recall_at_k"],
                    case_kpis["mrr"],
                    case_kpis["workflow_success"],
                    case_kpis["latency_seconds"],
                    case_kpis["cost_per_bundle_usd"],
                ]
            )
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "generated_at": payload["generated_at"],
                "json_report": str(json_path),
                "csv_report": str(csv_path),
                "sample_count": len(payload["sample_results"]),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"json_report": str(json_path), "csv_report": str(csv_path), "manifest": str(manifest_path)}


def get_latest_benchmark_report() -> BenchmarkRunResponse | None:
    if not settings.evidence_dir.exists():
        return None
    candidates = sorted(settings.evidence_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        if path.name.endswith(".manifest.json"):
            continue
        try:
            return BenchmarkRunResponse.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            continue
    return None


async def run_benchmark(req: BenchmarkRunRequest) -> BenchmarkRunResponse:
    cases = _load_cases()
    selected_ids = set(req.benchmark_case_ids)
    selected_cases = [case for case in cases if not selected_ids or case.id in selected_ids]

    sample_results: list[BenchmarkSampleResult] = []
    for case in selected_cases:
        analysis = await analyze_batch(_case_to_request(case, req))
        item = analysis.items[0]
        claims = [claim.claim for claim in item.verification.claims]
        citations = [citation.source for citation in item.final_output.rag_citations]
        ranked_ids = [hit.chunk_id for hit in item.retrieval.reranked_hits]
        claim_rate = claim_support_rate(case.expected_claims, claims)
        unsupported_rate = unsupported_claim_rate(case.forbidden_claims, claims, item.verification.unsupported_claims)
        citation_precision_value = citation_precision(case.expected_sources, citations)
        recall_value = recall_at_k(case.qrels, ranked_ids, settings.top_reranked_hits)
        mrr_value = mrr(case.qrels, ranked_ids)
        grounded_accuracy_value = grounded_accuracy(
            claim_support=claim_rate,
            unsupported_rate=unsupported_rate,
            citation_precision_value=citation_precision_value,
            recall_value=recall_value,
        )
        workflow_success = item.analysis_state == "ok" and item.final_status != "rejected"
        latency_seconds = item.judge_evaluation.latency_metrics.get("total_runtime", 0.0)
        review_time_reduction = _review_time_reduction(case.baseline_manual_review_seconds, latency_seconds)
        matched_claims, missed_claims = _match_lists(case.expected_claims, claims)
        matched_sources, missed_sources = _match_lists(case.expected_sources, citations)
        category_scores = {
            "claim_support_rate": claim_rate,
            "citation_precision": citation_precision_value,
            "recall_at_k": recall_value,
            "mrr": mrr_value,
        }
        case_kpis = CaseKpis(
            grounded_accuracy=grounded_accuracy_value,
            claim_support_rate=claim_rate,
            unsupported_claim_rate=unsupported_rate,
            citation_precision=citation_precision_value,
            recall_at_k=recall_value,
            mrr=mrr_value,
            workflow_success=workflow_success,
            latency_seconds=latency_seconds,
            cost_per_bundle_usd=float(item.final_output.llm_metadata.get("cost_usd") or 0.0),
        )
        sample_results.append(
            BenchmarkSampleResult(
                case_id=case.id,
                artifact_type=case.artifact_type,
                oracle_product=case.oracle_product,
                baseline_manual_review_seconds=case.baseline_manual_review_seconds,
                review_time_reduction_percent=review_time_reduction,
                category_scores=category_scores,
                matched_keywords={"expected_claims": matched_claims, "expected_sources": matched_sources},
                missed_keywords={"expected_claims": missed_claims, "expected_sources": missed_sources},
                unsupported_findings=item.verification.unsupported_claims,
                grounding={
                    "expected_sources": case.expected_sources,
                    "matched_sources": matched_sources,
                    "citation_sources": citations,
                },
                judge_evaluation=item.judge_evaluation,
                final_status=item.final_status,
                deliverable=item.deliverable,
                actual_result=item.final_output,
                expected_answer={
                    "summary": case.query,
                    "raw_expected": {
                        "query": case.query,
                        "expected_claims": case.expected_claims,
                        "forbidden_claims": case.forbidden_claims,
                        "expected_sources": case.expected_sources,
                        "qrels": case.qrels,
                    },
                },
                case_kpis=case_kpis,
                analysis_item=item,
            )
        )

    summary = BenchmarkSummary(
        total_cases=len(sample_results),
        approved=sum(1 for sample in sample_results if sample.final_status == "approved"),
        flagged=sum(1 for sample in sample_results if sample.final_status == "flagged"),
        rejected=sum(1 for sample in sample_results if sample.final_status == "rejected"),
        kpis={
            "grounded_accuracy_percent": round(mean([sample.case_kpis.grounded_accuracy for sample in sample_results]) if sample_results else 0.0, 2),
            "claim_support_rate_percent": round(mean([sample.case_kpis.claim_support_rate for sample in sample_results]) if sample_results else 0.0, 2),
            "unsupported_claim_rate_percent": round(mean([sample.case_kpis.unsupported_claim_rate for sample in sample_results]) if sample_results else 0.0, 2),
            "citation_precision_percent": round(mean([sample.case_kpis.citation_precision for sample in sample_results]) if sample_results else 0.0, 2),
            "recall_at_k_percent": round(mean([sample.case_kpis.recall_at_k for sample in sample_results]) if sample_results else 0.0, 2),
            "mrr_percent": round(mean([sample.case_kpis.mrr for sample in sample_results]) if sample_results else 0.0, 2),
            "workflow_success_rate_percent": round(mean([100.0 if sample.case_kpis.workflow_success else 0.0 for sample in sample_results]) if sample_results else 0.0, 2),
            "p95_latency_seconds": round(max((sample.case_kpis.latency_seconds for sample in sample_results), default=0.0), 3),
            "cost_per_bundle_usd": round(mean([sample.case_kpis.cost_per_bundle_usd for sample in sample_results]) if sample_results else 0.0, 6),
            "review_time_reduction_percent": round(mean([sample.review_time_reduction_percent for sample in sample_results]) if sample_results else 0.0, 2),
        },
        artifact_type_breakdown={},
        oracle_product_breakdown={},
    )
    for sample in sample_results:
        artifact_bucket = summary.artifact_type_breakdown.setdefault(sample.artifact_type, {"count": 0, "approved": 0, "avg_grounded_accuracy": 0.0})
        artifact_bucket["count"] += 1
        artifact_bucket["approved"] += 1 if sample.final_status == "approved" else 0
        artifact_bucket["avg_grounded_accuracy"] += sample.case_kpis.grounded_accuracy
        product_bucket = summary.oracle_product_breakdown.setdefault(sample.oracle_product, {"count": 0, "approved": 0, "avg_grounded_accuracy": 0.0})
        product_bucket["count"] += 1
        product_bucket["approved"] += 1 if sample.final_status == "approved" else 0
        product_bucket["avg_grounded_accuracy"] += sample.case_kpis.grounded_accuracy
    for bucket in summary.artifact_type_breakdown.values():
        bucket["avg_grounded_accuracy"] = round(bucket["avg_grounded_accuracy"] / max(1, bucket["count"]), 2)
    for bucket in summary.oracle_product_breakdown.values():
        bucket["avg_grounded_accuracy"] = round(bucket["avg_grounded_accuracy"] / max(1, bucket["count"]), 2)

    run_id = f"benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
    response = BenchmarkRunResponse(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        sample_results=sample_results,
        exports={},
    )
    payload = response.model_dump(mode="json")
    payload["exports"] = _write_exports(run_id, payload)
    return BenchmarkRunResponse.model_validate(payload)

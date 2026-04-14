from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AnalyzeInput(BaseModel):
    id: str
    code: str
    language: str = "auto"
    label: str = ""


class AnalyzeRequest(BaseModel):
    inputs: list[AnalyzeInput] = Field(default_factory=list)
    code: str = ""
    content: str = ""
    artifact_name: str = ""
    artifact_type: str = ""
    language: str = "auto"
    label: str = ""
    input_id: str = ""
    product: str = ""
    endpoint: str = ""
    token: str = Field(default="", description="Optional main provider token override. For Blueverse, this token must return an AnalysisOutput JSON object.")
    judge_token: str = Field(default="", description="Deprecated and ignored by the current runtime. Legacy Blueverse judge token is no longer used.")
    session_id: str = ""

    @model_validator(mode="before")
    @classmethod
    def coerce_single_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if data.get("inputs"):
            return data

        raw_code = str(data.get("code") or data.get("content") or "").strip()
        if not raw_code:
            return data

        inferred_language = str(data.get("language") or data.get("artifact_type") or "auto").strip() or "auto"
        inferred_label = (
            str(data.get("label") or data.get("artifact_name") or data.get("input_id") or "Input 1").strip() or "Input 1"
        )
        inferred_id = str(data.get("input_id") or data.get("artifact_name") or "input-1").strip() or "input-1"
        normalized = dict(data)
        normalized["inputs"] = [
            {
                "id": inferred_id,
                "code": raw_code,
                "language": inferred_language,
                "label": inferred_label,
            }
        ]
        normalized["code"] = raw_code
        return normalized


class IngestRequest(BaseModel):
    force_refresh: bool = False


class IngestResponse(BaseModel):
    corpus_version: str
    source_count: int
    document_count: int
    chunk_count: int
    refreshed: bool


class RagCitation(BaseModel):
    chunk_id: str
    source: str
    excerpt: str
    product: str = ""


class RetrievalHit(BaseModel):
    chunk_id: str
    source: str
    title: str
    section_path: list[str] = Field(default_factory=list)
    product: str = ""
    text: str
    excerpt: str
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fused_score: float = 0.0
    rerank_score: float = 0.0


class RetrievalBundle(BaseModel):
    query: str
    inferred_product: str = ""
    corpus_version: str = ""
    lexical_candidates: list[RetrievalHit] = Field(default_factory=list)
    reranked_hits: list[RetrievalHit] = Field(default_factory=list)


class ClaimVerification(BaseModel):
    claim: str
    source_fields: list[str] = Field(default_factory=list)
    status: Literal["supported", "weakly_supported", "unsupported"]
    evidence_chunk_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class VerificationSummary(BaseModel):
    claims: list[ClaimVerification] = Field(default_factory=list)
    supported_claim_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    grounded_accuracy: float = 0.0
    unsupported_claims: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    step: str
    started_at: str
    finished_at: str
    duration_ms: float
    status: Literal["ok", "degraded", "failed"]
    provider: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ProviderUsage(BaseModel):
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    raw_status: str = "ok"
    error_message: str = ""


class Finding(BaseModel):
    severity: str = "MEDIUM"
    type: str = ""
    description: str = ""
    line: str = ""
    confidence_score: int = 0
    evidence: str = ""


class HardcodedItem(BaseModel):
    type: str = Field(default="", description="Kind of hardcoded value such as constant, endpoint, credential, region, or threshold.")
    description: str = Field(default="", description="Why this hardcoded value is risky or brittle.")
    evidence: str = Field(default="", description="Short code excerpt or literal showing the hardcoded item.")


class AntiPattern(BaseModel):
    severity: str = "MEDIUM"
    pattern: str
    description: str
    recommendation: str = ""
    confidence_score: int = 0
    evidence: str = ""


class RefactorRecommendation(BaseModel):
    priority: str = "MEDIUM"
    title: str
    description: str
    benefit: str = ""
    codeHint: str = ""
    confidence_score: int = 0
    evidence: str = ""


class JiraTicket(BaseModel):
    title: str = Field(description="Short remediation ticket title.")
    description: str = Field(description="Actionable implementation task that addresses a concrete finding.")
    story_points: int = Field(default=0, description="Estimated effort as an integer story point value.")
    type: str = Field(default="Task", description="Ticket category such as Task, Bug, Security, Story, or Epic.")


class TestScenario(BaseModel):
    title: str = Field(description="Short test scenario title.")
    type: str = Field(default="functional", description="Scenario category such as positive, negative, edge, security, or regression.")
    description: str = Field(description="Concrete behavior the QA engineer should verify.")
    source: str = Field(default="", description="Finding or code behavior that motivated the scenario.")


class ImpactSummary(BaseModel):
    business_impact: str = Field(default="", description="High-level business effect of the artifact or its risks.")
    risk_overview: str = Field(default="", description="Executive summary of current delivery risk.")
    risk_level: str = Field(default="Medium", description="Overall risk level: Low, Medium, or High.")
    top_actions: list[str] = Field(default_factory=list, description="Priority actions the project manager should track.")


class AnalysisOutput(BaseModel):
    summary_oneliner: str
    summary_complexity: str = "UNKNOWN"
    summary_risk: str = "UNKNOWN"
    functional_purpose: str = ""
    business_logic: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    functional_inputs: list[str] = Field(default_factory=list)
    functional_outputs: list[str] = Field(default_factory=list)
    testable_interpretation: list[str] = Field(default_factory=list)
    dataflow_steps: list[str] = Field(default_factory=list)
    dataflow_tables: list[str] = Field(default_factory=list)
    dataflow_transformations: list[str] = Field(default_factory=list)
    complexity_score: float = 0.0
    nesting_depth: int = 0
    maintainability: str = "Not scored"
    readability: str = "Not scored"
    testability: str = "Not scored"
    security_score: float = 0.0
    security_issues: list[Finding] = Field(default_factory=list)
    hardcoded_items: list[HardcodedItem] = Field(default_factory=list)
    antipatterns: list[AntiPattern] = Field(default_factory=list)
    refactor_recommendations: list[RefactorRecommendation] = Field(default_factory=list)
    jira_tickets: list[JiraTicket] = Field(
        default_factory=list,
        description="Concrete remediation tickets derived from high-risk findings and high-priority refactors.",
    )
    test_scenarios: list[TestScenario] = Field(default_factory=list)
    impact_summary: ImpactSummary = Field(default_factory=ImpactSummary)
    rag_citations: list[RagCitation] = Field(default_factory=list)
    llm_metadata: dict[str, Any] = Field(default_factory=dict)


class JudgeEvaluation(BaseModel):
    scores: dict[str, float] = Field(default_factory=dict)
    validation: dict[str, float] = Field(default_factory=dict)
    finding_metrics: dict[str, float] = Field(default_factory=dict)
    latency_metrics: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, dict[str, float]] = Field(default_factory=dict)
    status: Literal["approved", "flagged", "rejected"] = "rejected"
    deliverable: bool = False
    summary: str = ""
    blocking_issues: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class AnalyzeItemResponse(BaseModel):
    id: str
    label: str
    language: str
    original_input: str
    primary_output: AnalysisOutput
    final_output: AnalysisOutput
    retrieval: RetrievalBundle
    verification: VerificationSummary
    execution_trace: list[TraceEvent] = Field(default_factory=list)
    judge_evaluation: JudgeEvaluation
    final_status: Literal["approved", "flagged", "rejected"] = "rejected"
    deliverable: bool = False
    analysis_state: Literal["ok", "degraded", "failed"] = "failed"
    render_source: Literal["graph", "heuristic", "failed", "none"] = "graph"
    failure_reason: str = ""
    session_id: str = ""


class AnalyzeSummary(BaseModel):
    total: int = 0
    approved: int = 0
    flagged: int = 0
    rejected: int = 0


class AnalyzeResponse(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    items: list[AnalyzeItemResponse]
    summary: AnalyzeSummary


class BenchmarkCase(BaseModel):
    id: str
    label: str
    language: str
    artifact_type: str
    oracle_product: Literal["fusion", "jde", "ebs", "epm"]
    baseline_manual_review_seconds: float
    query: str
    artifact: str
    expected_claims: list[str]
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_sources: list[str] = Field(default_factory=list)
    qrels: list[str] = Field(default_factory=list)


class BenchmarkRunRequest(BaseModel):
    endpoint: str = ""
    token: str = ""
    judge_token: str = Field(default="", description="Deprecated and ignored by the current runtime. Benchmark judge token is no longer used.")
    benchmark_case_ids: list[str] = Field(default_factory=list)


class CaseKpis(BaseModel):
    grounded_accuracy: float = 0.0
    claim_support_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    citation_precision: float = 0.0
    recall_at_k: float = 0.0
    mrr: float = 0.0
    workflow_success: bool = False
    latency_seconds: float = 0.0
    cost_per_bundle_usd: float = 0.0


class BenchmarkSampleResult(BaseModel):
    case_id: str
    artifact_type: str
    oracle_product: str
    baseline_manual_review_seconds: float
    review_time_reduction_percent: float
    category_scores: dict[str, float] = Field(default_factory=dict)
    matched_keywords: dict[str, list[str]] = Field(default_factory=dict)
    missed_keywords: dict[str, list[str]] = Field(default_factory=dict)
    unsupported_findings: list[str] = Field(default_factory=list)
    grounding: dict[str, list[str]] = Field(default_factory=dict)
    judge_evaluation: JudgeEvaluation
    final_status: str
    deliverable: bool
    actual_result: AnalysisOutput
    expected_answer: dict[str, Any]
    case_kpis: CaseKpis
    analysis_item: AnalyzeItemResponse


class BenchmarkSummary(BaseModel):
    total_cases: int
    approved: int
    flagged: int
    rejected: int
    kpis: dict[str, float | bool | str]
    artifact_type_breakdown: dict[str, dict[str, float | int]]
    oracle_product_breakdown: dict[str, dict[str, float | int]]


class BenchmarkRunResponse(BaseModel):
    run_id: str
    generated_at: datetime
    summary: BenchmarkSummary
    sample_results: list[BenchmarkSampleResult]
    exports: dict[str, str] = Field(default_factory=dict)

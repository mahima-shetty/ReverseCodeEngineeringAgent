from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas import AnalysisOutput, ProviderUsage, RetrievalBundle, VerificationSummary


class ReviewGraphState(BaseModel):
    input_id: str
    label: str
    language: str
    artifact: str
    inferred_product: str = ""
    retrieval: RetrievalBundle | None = None
    provider_usage: list[ProviderUsage] = Field(default_factory=list)
    provider_failures: list[str] = Field(default_factory=list)
    final_output: AnalysisOutput | None = None
    verification: VerificationSummary | None = None
    failure_reason: str = ""
    analysis_state: str = "failed"

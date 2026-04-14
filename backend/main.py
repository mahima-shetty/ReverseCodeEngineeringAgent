from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.review_graph import analyze_batch
from app.config import get_settings
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
    IngestRequest,
    IngestResponse,
)
from eval.benchmark_runner import get_latest_benchmark_report, run_benchmark
from observability.tracing import latest_usage_entries
from rag.ingestion import refresh_corpus

settings = get_settings()

app = FastAPI(title="CodeLens Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    return refresh_corpus(force=req.force_refresh)


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return await analyze_batch(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/benchmark/run", response_model=BenchmarkRunResponse)
async def benchmark_run(req: BenchmarkRunRequest) -> BenchmarkRunResponse:
    return await run_benchmark(req)


@app.post("/api/evaluate-benchmark", response_model=BenchmarkRunResponse)
async def benchmark_run_legacy(req: BenchmarkRunRequest) -> BenchmarkRunResponse:
    return await run_benchmark(req)


@app.get("/api/benchmark/latest", response_model=BenchmarkRunResponse)
def latest_benchmark() -> BenchmarkRunResponse:
    latest = get_latest_benchmark_report()
    if latest is None:
        raise HTTPException(status_code=404, detail="No benchmark evidence runs available yet")
    return latest


@app.get("/api/benchmark/run/latest", response_model=BenchmarkRunResponse)
def latest_benchmark_run_alias() -> BenchmarkRunResponse:
    latest = get_latest_benchmark_report()
    if latest is None:
        raise HTTPException(status_code=404, detail="No benchmark evidence runs available yet")
    return latest


@app.get("/api/evaluate-benchmark/latest", response_model=BenchmarkRunResponse)
def latest_benchmark_legacy() -> BenchmarkRunResponse:
    latest = get_latest_benchmark_report()
    if latest is None:
        raise HTTPException(status_code=404, detail="No benchmark evidence runs available yet")
    return latest


@app.get("/api/llm-usage/latest")
def latest_llm_usage(limit: int = 50) -> dict[str, list[dict[str, Any]]]:
    return {"items": latest_usage_entries(limit=max(1, min(limit, 200)))}

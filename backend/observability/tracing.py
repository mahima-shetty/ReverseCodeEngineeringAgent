from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings
from app.schemas import TraceEvent

settings = get_settings()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TraceRecorder:
    events: list[TraceEvent] = field(default_factory=list)

    @contextmanager
    def step(self, name: str, *, provider: str = "", details: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
        started_at = _utcnow()
        started = time.perf_counter()
        state: dict[str, Any] = {"status": "ok", "details": details or {}, "provider": provider}
        try:
            yield state
        except Exception as exc:
            state["status"] = "failed"
            state.setdefault("details", {})["error"] = str(exc)
            raise
        finally:
            finished_at = _utcnow()
            self.events.append(
                TraceEvent(
                    step=name,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    status=state.get("status", "ok"),
                    provider=state.get("provider", provider),
                    details=state.get("details", {}),
                )
            )


def write_usage_entry(entry: dict[str, Any]) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    with settings.llm_usage_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def overwrite_latest_usage(entries: list[dict[str, Any]]) -> None:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    with settings.latest_run_usage_log.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def latest_usage_entries(limit: int = 50) -> list[dict[str, Any]]:
    path = settings.llm_usage_log
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
    items: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def write_llm_output(
    *,
    provider: str,
    input_id: str,
    attempt: int,
    prompt: str,
    raw_text: str,
    payload: Any,
    validation_status: str,
    validation_error: str = "",
) -> Path:
    settings.llm_outputs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_input_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in input_id) or "input"
    filename = f"{provider}_output_{timestamp}_{safe_input_id}_attempt{attempt}.json"
    path = settings.llm_outputs_dir / filename
    path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "input_id": input_id,
                "attempt": attempt,
                "validation_status": validation_status,
                "validation_error": validation_error,
                "prompt": prompt,
                "raw_text": raw_text,
                "payload": payload,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return path


def write_llm_request(
    *,
    provider: str,
    input_id: str,
    attempt: int,
    request_url: str,
    request_body: Any,
) -> Path:
    settings.llm_requests_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_input_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in input_id) or "input"
    filename = f"{provider}_request_{timestamp}_{safe_input_id}_attempt{attempt}.json"
    path = settings.llm_requests_dir / filename
    path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provider": provider,
                "input_id": input_id,
                "attempt": attempt,
                "request_url": request_url,
                "request_body": request_body,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    return path

"""
CodeLens backend: proxies analysis to LTM Blueverse with Bearer auth.
Secrets: use backend/.env (see .env.example) or pass endpoint + token from the UI.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load backend/.env if present (never commit .env)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = FastAPI(title="CodeLens Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class AnalyzeRequest(BaseModel):
    code: str
    language: str = ""
    endpoint: str = ""
    token: str = ""
    # Optional overrides (else use BLUEVERSE_SPACE_NAME / BLUEVERSE_FLOW_ID in .env)
    space_name: str = ""
    flow_id: str = ""


@app.get("/health")
def health():
    return {"status": "ok"}


def _try_parse_json_object(text: str) -> dict[str, Any] | None:
    if not text or not isinstance(text, str):
        return None
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(t[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                pass
    return None


def _is_flat_schema(d: dict[str, Any]) -> bool:
    return "summary_oneliner" in d and "functional_purpose" in d


def _extract_steps_from_markdown(text: str) -> list[str]:
    """Pull bullet lines from a 'DATA FLOW' (or similar) section, if present."""
    steps: list[str] = []
    m = re.search(
        r"(?is)##\s*[^\n]*(?:DATA\s*FLOW|Data\s*Flow)[^\n]*\n(.*?)(?=\n##\s|\Z)",
        text,
    )
    if not m:
        return steps
    block = m.group(1)
    for line in block.splitlines():
        raw = line.strip()
        if raw.startswith(("-", "*", "•")):
            steps.append(raw.lstrip("-*• ").strip())
        elif raw.startswith("|") or raw.startswith("```"):
            continue
    return steps[:40]


def _markdown_report_to_flat(
    markdown: str, envelope: dict[str, Any]
) -> dict[str, Any]:
    """
    Blueverse chatservice often returns agent prose/markdown in the top-level
    'response' field instead of the CodeLens flat JSON schema.
    """
    text = markdown.strip()
    if not text:
        return {}

    oneliner = "Analysis report from agent"
    for line in text.split("\n"):
        s = line.strip().lstrip("#").strip()
        if s and len(s) > 5:
            oneliner = s[:220]
            break

    et = envelope.get("execution_time")
    if isinstance(et, (int, float)):
        oneliner = f"{oneliner} (≈{float(et):.1f}s)"[:220]

    steps = _extract_steps_from_markdown(text)
    loc = max(1, min(100, text.count("\n") // 5 or 1))

    return {
        "summary_oneliner": oneliner,
        "summary_complexity": "MEDIUM",
        "summary_risk": "MEDIUM",
        "functional_purpose": text,
        "functional_inputs": json.dumps([]),
        "functional_outputs": json.dumps([]),
        "dataflow_steps": json.dumps(steps) if steps else json.dumps([]),
        "complexity_score": loc,
        "security_score": 70,
        "security_issues": json.dumps([]),
        "antipatterns": json.dumps([]),
        "refactor_recommendations": json.dumps([]),
    }


def _extract_flat_payload(data: Any) -> dict[str, Any] | None:
    """Find the flat CodeLens response dict inside varied Blueverse / LLM wrappers."""
    if data is None:
        return None
    if isinstance(data, str):
        return _try_parse_json_object(data)

    if not isinstance(data, dict):
        return None

    if _is_flat_schema(data):
        return data

    # Blueverse Foundry chatservice: { "response": "# Markdown report\\n...", "flow_id": "...", ... }
    resp = data.get("response")
    if isinstance(resp, str) and resp.strip():
        j = _try_parse_json_object(resp.strip())
        if j and _is_flat_schema(j):
            return j
        # Prose / markdown — not our JSON schema
        return _markdown_report_to_flat(resp, data)

    for key in (
        "data",
        "result",
        "output",
        "response",
        "agent_response",
        "body",
        "answer",
        "message",
        "chatResponse",
        "botResponse",
    ):
        inner = data.get(key)
        if isinstance(inner, dict):
            got = _extract_flat_payload(inner)
            if got:
                return got
        if isinstance(inner, str):
            got = _try_parse_json_object(inner)
            if got and _is_flat_schema(got):
                return got

    # OpenAI-style
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            got = _try_parse_json_object(content)
            if got and _is_flat_schema(got):
                return got

    # Anthropic-style
    parts = data.get("content")
    if isinstance(parts, list):
        text = "".join(
            p.get("text", "") if isinstance(p, dict) else "" for p in parts
        )
        if text.strip():
            got = _try_parse_json_object(text)
            if got and _is_flat_schema(got):
                return got

    for key in ("text", "message", "content"):
        v = data.get(key)
        if isinstance(v, str) and "{" in v:
            got = _try_parse_json_object(v)
            if got and _is_flat_schema(got):
                return got

    return None


def _build_request_body(
    code: str,
    language: str,
    space_name: str,
    flow_id: str,
) -> dict[str, Any]:
    """
    Blueverse Foundry chat API (see chatservice/chat):
      {"query": "...", "space_name": "...", "flowId": "..."}

    Set BLUEVERSE_USE_MESSAGES=1 to use legacy PRD {messages:[...]} shape instead.
    """
    user_block = f"Language: {language or 'auto'}\n\nCode to analyze:\n{code}"

    if _env("BLUEVERSE_USE_MESSAGES") in ("1", "true", "yes"):
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": user_block}],
        }
        model = _env("BLUEVERSE_MODEL")
        if model:
            body["model"] = model
    else:
        if not space_name:
            raise HTTPException(
                status_code=400,
                detail="space_name missing: set BLUEVERSE_SPACE_NAME in backend/.env or pass space_name from the client",
            )
        if not flow_id:
            raise HTTPException(
                status_code=400,
                detail="flow_id missing: set BLUEVERSE_FLOW_ID in backend/.env or pass flow_id from the client",
            )
        body = {
            "query": user_block,
            "space_name": space_name,
            "flowId": flow_id,
        }

    extra = _env("BLUEVERSE_EXTRA_JSON")
    if extra:
        try:
            extra_obj = json.loads(extra)
            if isinstance(extra_obj, dict):
                body.update(extra_obj)
        except json.JSONDecodeError:
            pass
    return body


def _fallback_flat_from_error(lines_of_code: int, message: str) -> dict[str, Any]:
    return {
        "summary_oneliner": "Could not parse agent output as the expected JSON schema.",
        "summary_complexity": "MEDIUM",
        "summary_risk": "HIGH",
        "functional_purpose": message[:2000],
        "functional_inputs": json.dumps([]),
        "functional_outputs": json.dumps([]),
        "dataflow_steps": json.dumps([]),
        "complexity_score": max(1, min(50, lines_of_code // 20 or 1)),
        "security_score": 0,
        "security_issues": json.dumps(
            [{"severity": "HIGH", "type": "ParseError", "description": message[:500]}]
        ),
        "antipatterns": json.dumps([]),
        "refactor_recommendations": json.dumps([]),
    }


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Code is required")

    default_chat_url = "https://blueverse-foundry.ltimindtree.com/chatservice/chat"
    endpoint = (
        req.endpoint
        or _env("BLUEVERSE_URL")
        or _env("BLUEVERSE_BASE_URL")
        or default_chat_url
    ).strip()
    token = (req.token or _env("BLUEVERSE_BEARER_TOKEN")).strip()

    # Defaults match CodeReverseSimpleAgent; override via .env or request fields.
    space_name = (
        req.space_name or _env("BLUEVERSE_SPACE_NAME", "CodeReverseSimpleAgent_2b2a9f68")
    ).strip()
    flow_id = (req.flow_id or _env("BLUEVERSE_FLOW_ID", "69c35f4bfc57495a91cffadf")).strip()

    if not endpoint:
        raise HTTPException(
            status_code=400,
            detail="Blueverse URL missing: set ENDPOINT in the UI or BLUEVERSE_URL in backend/.env",
        )
    if not token:
        raise HTTPException(
            status_code=400,
            detail="Bearer token missing: paste token in the UI or set BLUEVERSE_BEARER_TOKEN in backend/.env",
        )

    if not endpoint.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Endpoint must be a full URL (https://...)")

    body = _build_request_body(req.code, req.language, space_name, flow_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    timeout_sec = float(_env("BLUEVERSE_TIMEOUT_SECONDS", "120") or "120")

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            response = await client.post(endpoint, headers=headers, json=body)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Blueverse request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Blueverse connection failed: {e!s}")

    raw_text = response.text
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="Forbidden — check token permissions")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=raw_text[:2000] or f"Blueverse error HTTP {response.status_code}",
        )

    try:
        parsed: Any = response.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Blueverse returned non-JSON response",
        )

    flat = _extract_flat_payload(parsed)
    lines_of_code = len(req.code.splitlines())

    if not flat:
        snippet = raw_text[:1500]
        flat = _fallback_flat_from_error(
            lines_of_code,
            f"Unexpected response shape. First bytes: {snippet}",
        )

    return flat

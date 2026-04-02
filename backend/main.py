"""
CodeLens backend: proxies analysis to LTM Blueverse with Bearer auth.
Secrets: use backend/.env (see .env.example) or pass endpoint + token from the UI.
"""

from __future__ import annotations

import json
import os
import re
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load backend/.env if present (never commit .env)
# override=True ensures .env values win over existing OS env vars
# (e.g. GOOGLE_APPLICATION_CREDENTIALS set by gcloud ADC must be replaced by the SA key)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Eagerly warm up RAG store now that .env is loaded
try:
    from rag_store import init_rag_store
    init_rag_store()
except Exception:
    pass

app = FastAPI(title="CodeLens Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_DIR = Path(__file__).parent
FIXTURES_DIR = BACKEND_DIR / "fixtures"
EVIDENCE_DIR = BACKEND_DIR / "evidence"
BENCHMARK_FILE = FIXTURES_DIR / "benchmark_cases.json"
LOG_DIR = BACKEND_DIR / "logs"
LLM_USAGE_LOG = LOG_DIR / "llm_usage.jsonl"

SESSION_MEMORY: dict[str, list[dict[str, str]]] = {}
SESSION_TURN_LIMIT = 5
SESSION_SUMMARY_CHAR_LIMIT = 1200


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


class AnalyzeInput(BaseModel):
    id: str
    code: str
    language: str = ""
    label: str = ""


class AnalyzeRequest(BaseModel):
    code: str = ""
    endpoint: str = ""
    token: str = ""
    judge_token: str = ""
    # Optional overrides (else use BLUEVERSE_SPACE_NAME / BLUEVERSE_FLOW_ID in .env)
    space_name: str = ""
    flow_id: str = ""
    judge_endpoint: str = ""
    judge_space_name: str = ""
    judge_flow_id: str = ""
    session_id: str = ""
    inputs: list[AnalyzeInput] = []


class BenchmarkExpectedFindings(BaseModel):
    functional_intent_keywords: list[str] = []
    data_flow_keywords: list[str] = []
    complexity_hotspots: list[str] = []
    security_findings: list[str] = []
    performance_findings: list[str] = []
    anti_patterns: list[str] = []
    hardcoding_gaps: list[str] = []
    error_handling_gaps: list[str] = []
    refactor_recommendations: list[str] = []
    oracle_grounding_sources: list[str] = []


class BenchmarkCase(BaseModel):
    id: str
    label: str
    language: str
    artifact_type: str
    oracle_product: Literal["fusion", "jde", "ebs", "epm"]
    baseline_manual_review_seconds: float
    code: str
    expected: BenchmarkExpectedFindings


class EvaluateBenchmarkRequest(BaseModel):
    endpoint: str = ""
    token: str = ""
    judge_token: str = ""
    space_name: str = ""
    flow_id: str = ""
    judge_endpoint: str = ""
    judge_space_name: str = ""
    judge_flow_id: str = ""
    session_id: str = ""
    benchmark_case_ids: list[str] = []
    manual_judge_score: float = 4.0


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
        # Try extracting the outermost {...} block
        start = t.find("{")
        end = t.rfind("}")
        if start >= 0 and end > start:
            try:
                obj = json.loads(t[start : end + 1])
                return obj if isinstance(obj, dict) else None
            except json.JSONDecodeError:
                pass
        # Try to repair truncated JSON by closing open brackets/braces
        if start >= 0:
            candidate = t[start:]
            repaired = _repair_truncated_json(candidate)
            if repaired:
                try:
                    obj = json.loads(repaired)
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    pass
    return None


def _repair_truncated_json(s: str) -> str:
    """
    Attempt to close a truncated JSON object/array.
    Strategy:
    - Walk forward tracking string/bracket state.
    - Record the last position that was a 'clean' end of a complete value
      (after '}', ']', closing '"' of a VALUE — not a key, number, bool, null).
    - If we're inside an open string at end, cut back to last clean position.
    - Then close all still-open brackets/braces.
    """
    s = s.rstrip()
    n = len(s)

    stack: list[str] = []   # unmatched '{' or '['
    in_string = False
    escape = False
    # after_colon: True means we just passed a ':' outside a string (next string is a VALUE)
    after_colon = False
    in_value_string = False  # True when current string is a JSON value (not a key)

    # last_clean_pos: position just after the last fully-closed value
    # We track TWO levels:
    #   - last_complete_value_pos: after a ']' or '}' or closing '"' of a value or number/bool/null
    #   - last_complete_member_pos: after a complete key:value pair + comma (safe to close object here)
    last_complete_value_pos: int = 0
    # Track when we close a container — that's always a safe cut point
    last_container_close_pos: int = 0

    i = 0
    while i < n:
        ch = s[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
                if in_value_string:
                    last_complete_value_pos = i + 1
                in_value_string = False
                after_colon = False
        else:
            if ch == '"':
                in_string = True
                # Is this string a VALUE (i.e. we just saw a ':' or we're inside an array)?
                in_value_string = after_colon or (stack and stack[-1] == "[")
            elif ch == ":":
                after_colon = True
            elif ch == ",":
                after_colon = False
            elif ch in "{[":
                stack.append(ch)
                after_colon = False
            elif ch in "}]":
                if stack:
                    stack.pop()
                last_container_close_pos = i + 1
                last_complete_value_pos = i + 1
                after_colon = False
            elif ch in "0123456789.-":
                # number — find its end
                j = i + 1
                while j < n and s[j] in "0123456789.eE+-":
                    j += 1
                last_complete_value_pos = j
                i = j - 1  # will be incremented at end
                after_colon = False
            elif s[i:i+4] in ("true", "fals", "null"):
                word_len = 5 if s[i:i+5] == "false" else 4
                last_complete_value_pos = i + word_len
                i += word_len - 1
                after_colon = False
        i += 1

    # If we ended inside an open string, cut back to last complete value position
    if in_string:
        cut = last_complete_value_pos
        s = s[:cut].rstrip().rstrip(",").rstrip()
        # Recount stack on trimmed version
        stack = []
        in_s2 = False
        esc2 = False
        for ch2 in s:
            if esc2:
                esc2 = False
                continue
            if in_s2:
                if ch2 == "\\":
                    esc2 = True
                elif ch2 == '"':
                    in_s2 = False
            else:
                if ch2 == '"':
                    in_s2 = True
                elif ch2 in "{[":
                    stack.append(ch2)
                elif ch2 in "}]":
                    if stack:
                        stack.pop()
    else:
        # Not in string — but might have trailing comma
        s = s.rstrip().rstrip(",").rstrip()

    suffix = ""
    for ch in reversed(stack):
        suffix += "}" if ch == "{" else "]"
    return s + suffix


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
        "jira_tickets": json.dumps([]),
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

    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
        if isinstance(content, dict):
            parts = content.get("parts")
            if isinstance(parts, list):
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
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


def _extract_prompt_from_body(body: dict[str, Any]) -> str:
    query = body.get("query")
    if isinstance(query, str) and query.strip():
        return query
    messages = body.get("messages")
    if isinstance(messages, list):
        parts: list[str] = []
        for message in messages:
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    parts.append(content)
        if parts:
            return "\n\n".join(parts)
    return ""


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(round(len(text) / 4)))


def _price_per_1k(provider: str, direction: Literal["input", "output"]) -> float:
    key = f"{provider.upper()}_{direction.upper()}_COST_PER_1K"
    raw = _env(key)
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        return 0.0


def _calculate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
    return round(
        (input_tokens / 1000.0) * _price_per_1k(provider, "input")
        + (output_tokens / 1000.0) * _price_per_1k(provider, "output"),
        6,
    )


def _extract_usage(provider: str, parsed: Any, prompt_text: str, raw_text: str) -> dict[str, int]:
    input_tokens = _estimate_tokens(prompt_text)
    output_tokens = _estimate_tokens(raw_text)
    if not isinstance(parsed, dict):
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    usage = parsed.get("usage")
    if provider == "openai" and isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens") or input_tokens)
        output_tokens = int(usage.get("completion_tokens") or output_tokens)
    elif provider == "anthropic" and isinstance(usage, dict):
        input_tokens = int(usage.get("input_tokens") or input_tokens)
        output_tokens = int(usage.get("output_tokens") or output_tokens)
    elif provider == "gemini":
        meta = parsed.get("usageMetadata")
        if isinstance(meta, dict):
            input_tokens = int(meta.get("promptTokenCount") or input_tokens)
            output_tokens = int(meta.get("candidatesTokenCount") or output_tokens)
    elif provider == "blueverse" and isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or input_tokens)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or output_tokens)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _write_usage_log(entry: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LLM_USAGE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _conversation_context(session_id: str) -> str:
    if not session_id:
        return ""
    turns = SESSION_MEMORY.get(session_id, [])
    if not turns:
        return ""
    lines = ["Prior conversation context (compressed summaries):"]
    for idx, turn in enumerate(turns[-SESSION_TURN_LIMIT:], start=1):
        lines.append(f"{idx}. Input: {turn['input']}")
        lines.append(f"   Summary: {turn['summary']}")
    joined = "\n".join(lines)
    return joined[:SESSION_SUMMARY_CHAR_LIMIT]


def _remember_turn(session_id: str, input_text: str, summary_text: str) -> None:
    if not session_id:
        return
    entry = {
        "input": input_text.strip().replace("\n", " ")[:300],
        "summary": summary_text.strip().replace("\n", " ")[:300],
    }
    SESSION_MEMORY.setdefault(session_id, []).append(entry)
    SESSION_MEMORY[session_id] = SESSION_MEMORY[session_id][-SESSION_TURN_LIMIT:]


def _build_chat_body(query: str, space_name: str, flow_id: str) -> dict[str, Any]:
    if _env("BLUEVERSE_USE_MESSAGES") in ("1", "true", "yes"):
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": query}],
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
            "query": query,
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


def _build_request_body(
    code: str,
    language: str,
    space_name: str,
    flow_id: str,
    session_id: str = "",
) -> tuple[dict[str, Any], list[dict], dict[str, Any]]:
    """
    Blueverse Foundry chat API (see chatservice/chat):
      {"query": "...", "space_name": "...", "flowId": "..."}

    Set BLUEVERSE_USE_MESSAGES=1 to use legacy PRD {messages:[...]} shape instead.
    Returns (request_body, rag_citations, rag_diagnostics).
    """
    try:
        from rag_store import get_rag_context, get_rag_citations, get_rag_diagnostics
        retrieval_query = f"Language: {language or 'auto'}\n{code[:4000]}"
        rag_context = get_rag_context(retrieval_query)
        rag_citations = get_rag_citations(retrieval_query)
        rag_diagnostics = get_rag_diagnostics(retrieval_query)
    except ImportError:
        rag_context = ""
        rag_citations = []
        rag_diagnostics = {}

    instruction_block = (
        "Perform highest-impact feature upgrades as per the user's PRD:\n"
        "1. PR/Diff Review Mode: analyze before vs after changes (if diff is provided), show risk delta and suggested reviewer comments.\n"
        "2. Multi-file dependency analysis: trace calls and data flow across SQL + script + config files if provided.\n"
        "3. Actionable outputs: return a list of Jira-ready tickets in a new JSON array field called 'jira_tickets'. Each item should be {'title': '...', 'description': '...', 'story_points': 5, 'type': 'Bug'}.\n"
        "4. Confidence + evidence: for every finding (security_issues, antipatterns, refactor_recommendations), include a 'confidence_score' (1-100) and an 'evidence' field with a code excerpt and standard reference.\n"
        "5. RAG on org standards: strictly apply the Oracle documentation context provided below and score each finding against it.\n"
        "6. Oracle specificity: keep the response grounded in Oracle Fusion, JD Edwards, E-Business Suite, or EPM context only. Do not generalize beyond the retrieved Oracle sources.\n"
        "7. If the retrieved Oracle grounding is insufficient for a claim, say that explicitly instead of guessing.\n"
        "CRITICAL: Output ONLY valid JSON. Your response must be parseable by json.loads(). Do NOT wrap in ```json or markdown.\n"
        "Mandatory JSON keys: 'summary_oneliner', 'summary_complexity', 'summary_risk', 'functional_purpose', 'business_logic', 'side_effects', 'functional_inputs', 'functional_outputs', 'dataflow_steps', 'complexity_score', 'security_score', 'security_issues', 'antipatterns', 'refactor_recommendations', 'jira_tickets'.\n"
        "All lists (security_issues, antipatterns, etc.) must be JSON arrays of strictly formatted objects mapping matching the requested keys.\n"
        "TOKEN LIMIT ALERT: Keep all textual descriptions EXTREMELY brief (1 sentence max). Limit lists to maximum 2 items each (max 2 tickets, max 2 security issues) to ensure your JSON output is not truncated!\n\n"
    )
    if rag_context:
        instruction_block += f"Oracle Documentation Grounding:\n{rag_context}\n\n"
    prior_context = _conversation_context(session_id)
    if prior_context:
        instruction_block += f"{prior_context}\n\n"

    user_block = f"Language: {language or 'auto'}\n\n{instruction_block}Code to analyze:\n{code}"

    return _build_chat_body(user_block, space_name, flow_id), rag_citations, rag_diagnostics


# LLM sometimes uses variant key names — remap them to our canonical schema
_KEY_ALIASES: dict[str, str] = {
    # refactor variants
    "refactor_recommendations": "refactor_recommendations",
    "recommendations": "refactor_recommendations",
    "improvement_recommendations": "refactor_recommendations",
    "code_improvement_recommendations": "refactor_recommendations",
    "improve_code_structure_recommendations": "refactor_recommendations",
    # catch anything containing "recommend" but not already named right
}

# Also match any key containing "recommend" case-insensitively
def _canonical_key(k: str) -> str:
    kl = k.lower().replace(" ", "_")
    if kl in _KEY_ALIASES:
        return _KEY_ALIASES[kl]
    if "recommend" in kl and kl != "refactor_recommendations":
        return "refactor_recommendations"
    return k


def _normalize_flat(flat: dict[str, Any]) -> dict[str, Any]:
    """
    Post-process the raw LLM dict to:
    1. Remap variant key names (e.g. 'Improve code structure_recommendations') to canonical names
    2. Wrap plain-string list fields in a single-item list (for fields that should be arrays)
    3. Ensure all expected keys exist with sensible defaults
    """
    # Step 1: remap non-canonical keys
    result: dict[str, Any] = {}
    for k, v in flat.items():
        result[_canonical_key(k)] = v

    # Step 2: for list fields that might be plain strings, wrap them
    list_fields = (
        "functional_inputs", "functional_outputs", "dataflow_steps",
        "security_issues", "antipatterns", "refactor_recommendations",
        "jira_tickets", "business_logic", "side_effects",
    )
    for field in list_fields:
        val = result.get(field)
        if val is None:
            result[field] = []
        elif isinstance(val, str):
            # Try to parse as JSON first
            stripped = val.strip()
            if stripped.startswith("["):
                try:
                    result[field] = json.loads(stripped)
                    continue
                except json.JSONDecodeError:
                    pass
            # Plain string — wrap as single string item (normalize.ts handles it)
            result[field] = [stripped] if stripped else []

    # Step 3: ensure top-level scalar fields have fallbacks
    result.setdefault("summary_oneliner", "")
    result.setdefault("summary_complexity", "MEDIUM")
    result.setdefault("summary_risk", "MEDIUM")
    result.setdefault("functional_purpose", "")
    result.setdefault("complexity_score", 0)
    result.setdefault("security_score", 0)

    return result


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
        "jira_tickets": json.dumps([]),
    }


def _coerce_score(value: Any, *, default: int = 0, lower: int = 0, upper: int = 100) -> int:
    try:
        num = int(round(float(value)))
    except (TypeError, ValueError):
        num = default
    return max(lower, min(upper, num))


def _judge_status(
    completeness: int,
    correctness: int,
    hallucination: int,
    oracle_grounding: int = 0,
) -> Literal["approved", "flagged", "rejected"]:
    if completeness >= 85 and correctness >= 90 and hallucination <= 15 and oracle_grounding >= 85:
        return "approved"
    if completeness >= 70 and correctness >= 75 and hallucination <= 30 and oracle_grounding >= 70:
        return "flagged"
    return "rejected"


def _default_judge_evaluation(message: str) -> dict[str, Any]:
    scores = {
        "completeness": 0,
        "correctness": 0,
        "hallucination": 100,
    }
    validation = {
        "accuracy": 0,
        "oracle_grounding": 0,
        "oracle_specificity": 0,
    }
    status = _judge_status(**scores, oracle_grounding=validation["oracle_grounding"])
    return {
        "scores": scores,
        "validation": validation,
        "finding_metrics": {
            "precision": 0,
            "recall": 0,
            "false_positive_rate": 100,
        },
        "latency_metrics": {
            "time_to_first_useful_output": 0,
            "total_runtime": 0,
        },
        "thresholds": {
            "approved": {
                "completeness_min": 85,
                "correctness_min": 90,
                "hallucination_max": 15,
                "oracle_grounding_min": 85,
            },
            "flagged": {
                "completeness_min": 70,
                "correctness_min": 75,
                "hallucination_max": 30,
                "oracle_grounding_min": 70,
            },
        },
        "status": status,
        "deliverable": status == "approved",
        "summary": message[:500],
        "blocking_issues": [message[:500]],
        "recommended_action": "Hold response and review manually.",
    }


def _extract_judge_payload(data: Any) -> dict[str, Any] | None:
    if data is None:
        return None
    if isinstance(data, str):
        return _try_parse_json_object(data)
    if not isinstance(data, dict):
        return None
    if "scores" in data or "completeness" in data:
        return data
    for key in ("response", "result", "output", "data", "message", "content", "answer"):
        inner = data.get(key)
        if isinstance(inner, dict):
            got = _extract_judge_payload(inner)
            if got:
                return got
        elif isinstance(inner, str):
            got = _try_parse_json_object(inner)
            if got:
                return got
    candidates = data.get("candidates")
    if isinstance(candidates, list) and candidates:
        candidate = candidates[0]
        if isinstance(candidate, dict):
            content = candidate.get("content")
            if isinstance(content, dict):
                parts = content.get("parts")
                if isinstance(parts, list):
                    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
                    got = _try_parse_json_object(text)
                    if got:
                        return got
    return None


def _normalize_judge_evaluation(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not raw:
        return _default_judge_evaluation("Judge returned no usable JSON evaluation.")
    scores_obj = raw.get("scores")
    if isinstance(scores_obj, dict):
        completeness_raw = scores_obj.get("completeness")
        correctness_raw = scores_obj.get("correctness")
        hallucination_raw = scores_obj.get("hallucination")
    else:
        completeness_raw = raw.get("completeness")
        correctness_raw = raw.get("correctness")
        hallucination_raw = raw.get("hallucination")

    completeness = _coerce_score(completeness_raw)
    correctness = _coerce_score(correctness_raw)
    hallucination = _coerce_score(hallucination_raw, default=100)
    validation_obj = raw.get("validation")
    if not isinstance(validation_obj, dict):
        validation_obj = {}
    validation = {
        "accuracy": _coerce_score(validation_obj.get("accuracy"), default=correctness),
        "oracle_grounding": _coerce_score(validation_obj.get("oracle_grounding")),
        "oracle_specificity": _coerce_score(validation_obj.get("oracle_specificity")),
    }
    status = _judge_status(
        completeness,
        correctness,
        hallucination,
        validation["oracle_grounding"],
    )

    blocking_issues = raw.get("blocking_issues")
    if isinstance(blocking_issues, str):
        blocking_issues = [blocking_issues]
    if not isinstance(blocking_issues, list):
        blocking_issues = []

    summary = str(raw.get("summary") or raw.get("rationale") or "").strip()
    recommended_action = str(raw.get("recommended_action") or "").strip()
    if not recommended_action:
        recommended_action = (
            "Deliver response."
            if status == "approved"
            else "Hold response and review manually."
        )

    return {
        "scores": {
            "completeness": completeness,
            "correctness": correctness,
            "hallucination": hallucination,
        },
        "validation": validation,
        "finding_metrics": {
            "precision": _coerce_score(raw.get("precision"), default=0),
            "recall": _coerce_score(raw.get("recall"), default=0),
            "false_positive_rate": _coerce_score(raw.get("false_positive_rate"), default=100),
        },
        "latency_metrics": {
            "time_to_first_useful_output": _coerce_score(raw.get("time_to_first_useful_output"), default=0),
            "total_runtime": _coerce_score(raw.get("total_runtime"), default=0),
        },
        "thresholds": {
            "approved": {
                "completeness_min": 85,
                "correctness_min": 90,
                "hallucination_max": 15,
                "oracle_grounding_min": 85,
            },
            "flagged": {
                "completeness_min": 70,
                "correctness_min": 75,
                "hallucination_max": 30,
                "oracle_grounding_min": 70,
            },
        },
        "status": status,
        "deliverable": status == "approved",
        "summary": summary or f"Judge marked this response as {status}.",
        "blocking_issues": [str(item)[:500] for item in blocking_issues[:5]],
        "recommended_action": recommended_action,
    }


def _build_judge_request_body(
    input_item: AnalyzeInput,
    primary_result: dict[str, Any],
    space_name: str,
    flow_id: str,
) -> dict[str, Any]:
    judge_query = (
        "You are an LLM judge evaluating another agent response.\n"
        "Score the response using these metrics from 0 to 100:\n"
        "- completeness: maximize\n"
        "- correctness: maximize\n"
        "- hallucination: minimize\n"
        "Return ONLY valid JSON with keys:\n"
        "scores: {completeness, correctness, hallucination},\n"
        "validation: {accuracy, oracle_grounding, oracle_specificity},\n"
        "summary,\n"
        "blocking_issues,\n"
        "recommended_action.\n"
        "Keep summary short. blocking_issues must be a JSON array of short strings.\n"
        "Penalize unsupported claims, generic non-Oracle advice, and poor grounding against Oracle Fusion/JDE/EBS/EPM documentation.\n\n"
        f"Original input label: {input_item.label or input_item.id}\n"
        f"Original input language: {input_item.language or 'auto'}\n"
        f"Original input:\n{input_item.code}\n\n"
        "Primary agent response JSON:\n"
        f"{json.dumps(primary_result, ensure_ascii=True)}"
    )
    return _build_chat_body(judge_query, space_name, flow_id)


async def _post_blueverse(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    token: str,
    body: dict[str, Any],
) -> tuple[Any, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        response = await client.post(endpoint, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Timed out connecting to Blueverse endpoint {endpoint}. Check VPN, proxy, firewall, or endpoint reachability.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Blueverse endpoint {endpoint}: {exc!s}. Check VPN, proxy, firewall, DNS, or endpoint configuration.",
        ) from exc
    raw_text = response.text
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid or expired bearer token")
    if response.status_code == 403:
        raise HTTPException(status_code=403, detail="Forbidden - check token permissions")
    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=raw_text[:2000] or f"Blueverse error HTTP {response.status_code}",
        )
    try:
        return response.json(), raw_text
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail="Blueverse returned non-JSON response",
        )


async def _post_json(
    client: httpx.AsyncClient,
    *,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    provider_name: str,
) -> tuple[Any, str]:
    try:
        response = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"{provider_name} timed out") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"{provider_name} connection failed: {exc!s}") from exc
    raw_text = response.text
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=raw_text[:2000] or f"{provider_name} error")
    try:
        return response.json(), raw_text
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"{provider_name} returned non-JSON response") from exc


async def _try_provider_chain(
    client: httpx.AsyncClient,
    *,
    prompt_body: dict[str, Any],
    task: Literal["primary", "judge"],
    config: dict[str, str],
    session_id: str = "",
) -> dict[str, Any]:
    prompt_text = _extract_prompt_from_body(prompt_body)
    attempts: list[dict[str, Any]] = []
    providers = ["blueverse"] + [p.strip().lower() for p in _env("LLM_FALLBACK_CHAIN", "claude,openai,gemini").split(",") if p.strip()]

    for provider in providers:
        started = time.perf_counter()
        try:
            if provider == "blueverse":
                parsed, raw_text = await _post_blueverse(
                    client,
                    endpoint=config["endpoint"] if task == "primary" else config["judge_endpoint"],
                    token=config["token"] if task == "primary" else config["judge_token"],
                    body=prompt_body,
                )
                model = config["flow_id"] if task == "primary" else config["judge_flow_id"]
            elif provider == "openai":
                api_key = _env("OPENAI_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=503, detail="OpenAI fallback not configured")
                model = _env("OPENAI_MODEL", "gpt-4o-mini")
                parsed, raw_text = await _post_json(
                    client,
                    url=_env("OPENAI_URL", "https://api.openai.com/v1/chat/completions"),
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    body={"model": model, "messages": [{"role": "user", "content": prompt_text}]},
                    provider_name="OpenAI",
                )
            elif provider == "claude":
                api_key = _env("ANTHROPIC_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=503, detail="Claude fallback not configured")
                model = _env("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
                parsed, raw_text = await _post_json(
                    client,
                    url=_env("ANTHROPIC_URL", "https://api.anthropic.com/v1/messages"),
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    body={"model": model, "max_tokens": 4000, "messages": [{"role": "user", "content": prompt_text}]},
                    provider_name="Claude",
                )
            elif provider == "gemini":
                api_key = _env("GEMINI_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=503, detail="Gemini fallback not configured")
                model = _env("GEMINI_MODEL", "gemini-1.5-flash")
                parsed, raw_text = await _post_json(
                    client,
                    url=_env("GEMINI_URL", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"),
                    headers={"Content-Type": "application/json"},
                    body={"contents": [{"parts": [{"text": prompt_text}]}]},
                    provider_name="Gemini",
                )
            else:
                continue

            usage = _extract_usage(provider, parsed, prompt_text, raw_text)
            cost = _calculate_cost(provider, usage["input_tokens"], usage["output_tokens"])
            metadata = {
                "provider": provider,
                "model": model,
                "usage": usage,
                "cost_usd": cost,
                "fallback_used": provider != "blueverse",
                "attempts": attempts + [{"provider": provider, "status": "success"}],
                "session_id": session_id,
                "task": task,
                "duration_seconds": round(time.perf_counter() - started, 3),
            }
            _write_usage_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    **metadata,
                }
            )
            return {
                "parsed": parsed,
                "raw_text": raw_text,
                "metadata": metadata,
            }
        except HTTPException as exc:
            attempts.append(
                {
                    "provider": provider,
                    "status": "failed",
                    "detail": str(exc.detail),
                    "duration_seconds": round(time.perf_counter() - started, 3),
                }
            )
            _write_usage_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "provider": provider,
                    "status": "failed",
                    "detail": str(exc.detail),
                    "session_id": session_id,
                    "task": task,
                }
            )
            continue

    raise HTTPException(status_code=502, detail=f"All configured LLM providers failed for {task}. Attempts: {attempts}")


async def _run_primary_analysis(
    client: httpx.AsyncClient,
    *,
    input_item: AnalyzeInput,
    config: dict[str, str],
    session_id: str = "",
) -> dict[str, Any]:
    body, rag_citations, rag_diagnostics = _build_request_body(
        input_item.code,
        input_item.language,
        config["space_name"],
        config["flow_id"],
        session_id,
    )
    provider_result = await _try_provider_chain(
        client,
        prompt_body=body,
        task="primary",
        config=config,
        session_id=session_id,
    )
    parsed = provider_result["parsed"]
    raw_text = provider_result["raw_text"]
    flat = _extract_flat_payload(parsed)
    lines_of_code = len(input_item.code.splitlines())
    if not flat:
        flat = _fallback_flat_from_error(
            lines_of_code,
            f"Unexpected response shape. First bytes: {raw_text[:1500]}",
        )
    flat = _normalize_flat(flat)
    flat["rag_citations"] = rag_citations
    flat["rag_diagnostics"] = rag_diagnostics
    flat["llm_metadata"] = provider_result["metadata"]
    return flat


async def _run_judge_analysis(
    client: httpx.AsyncClient,
    *,
    input_item: AnalyzeInput,
    primary_result: dict[str, Any],
    config: dict[str, str],
    session_id: str = "",
) -> dict[str, Any]:
    body = _build_judge_request_body(input_item, primary_result, config["judge_space_name"], config["judge_flow_id"])
    provider_result = await _try_provider_chain(
        client,
        prompt_body=body,
        task="judge",
        config=config,
        session_id=session_id,
    )
    parsed = provider_result["parsed"]
    raw_text = provider_result["raw_text"]
    judge_raw = _extract_judge_payload(parsed)
    if not judge_raw:
        judge_raw = _try_parse_json_object(raw_text)
    normalized = _normalize_judge_evaluation(judge_raw)
    normalized["provider_metadata"] = provider_result["metadata"]
    return normalized


def _resolve_inputs(req: AnalyzeRequest) -> list[AnalyzeInput]:
    inputs = [item for item in req.inputs if item.code.strip()]
    if not inputs and req.code.strip():
        inputs = [AnalyzeInput(id="input-1", code=req.code, language="", label="Input 1")]
    if not inputs:
        raise HTTPException(status_code=400, detail="At least one input is required")
    return inputs


def _resolve_runtime_config(req: AnalyzeRequest) -> dict[str, str]:
    default_chat_url = "https://blueverse-foundry.ltimindtree.com/chatservice/chat"
    endpoint = (
        req.endpoint
        or _env("BLUEVERSE_URL")
        or _env("BLUEVERSE_BASE_URL")
        or default_chat_url
    ).strip()
    token = (req.token or _env("BLUEVERSE_BEARER_TOKEN")).strip()
    judge_token = (req.judge_token or _env("BLUEVERSE_JUDGE_BEARER_TOKEN")).strip()

    space_name = (
        req.space_name or _env("BLUEVERSE_SPACE_NAME", "CodeReverseSimpleAgent_2b2a9f68")
    ).strip()
    flow_id = (req.flow_id or _env("BLUEVERSE_FLOW_ID", "69c35f4bfc57495a91cffadf")).strip()
    judge_endpoint = (req.judge_endpoint or _env("BLUEVERSE_JUDGE_URL") or endpoint).strip()
    judge_space_name = (
        req.judge_space_name
        or _env("BLUEVERSE_JUDGE_SPACE_NAME", "ReverseCodeEngineeringJudge_1887a276")
    ).strip()
    judge_flow_id = (
        req.judge_flow_id or _env("BLUEVERSE_JUDGE_FLOW_ID", "69cea4715bf1852d8214dde7")
    ).strip()

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
    if not judge_token:
        raise HTTPException(
            status_code=400,
            detail="Judge bearer token missing: paste judge token in the UI or set BLUEVERSE_JUDGE_BEARER_TOKEN in backend/.env",
        )
    if not judge_flow_id and _env("BLUEVERSE_USE_MESSAGES") not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=400,
            detail="Judge flow_id missing: set BLUEVERSE_JUDGE_FLOW_ID in backend/.env or pass judge_flow_id from the client",
        )
    if not endpoint.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Endpoint must be a full URL (https://...)")
    if not judge_endpoint.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Judge endpoint must be a full URL (https://...)")

    return {
        "endpoint": endpoint,
        "token": token,
        "judge_token": judge_token,
        "space_name": space_name,
        "flow_id": flow_id,
        "judge_endpoint": judge_endpoint,
        "judge_space_name": judge_space_name,
        "judge_flow_id": judge_flow_id,
        "session_id": req.session_id.strip(),
    }


async def _execute_analysis_batch(
    *,
    inputs: list[AnalyzeInput],
    config: dict[str, str],
) -> dict[str, Any]:
    timeout_sec = float(_env("BLUEVERSE_TIMEOUT_SECONDS", "120") or "120")
    results: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            for index, input_item in enumerate(inputs, start=1):
                current_input = AnalyzeInput(
                    id=input_item.id or f"input-{index}",
                    code=input_item.code,
                    language=input_item.language,
                    label=input_item.label.strip() or f"Input {index}",
                )
                item_started_at = time.perf_counter()
                try:
                    primary_result = await _run_primary_analysis(
                        client,
                        input_item=current_input,
                        config=config,
                        session_id=config.get("session_id", ""),
                    )
                except (HTTPException, httpx.RequestError, httpx.TimeoutException) as exc:
                    message = exc.detail if isinstance(exc, HTTPException) else str(exc)
                    judge_result = _default_judge_evaluation(
                        f"Primary agent failed before judge review: {message}"
                    )
                    judge_result["latency_metrics"] = {
                        "time_to_first_useful_output": 0,
                        "total_runtime": round(time.perf_counter() - item_started_at, 3),
                    }
                    results.append(
                        {
                            "id": current_input.id,
                            "label": current_input.label,
                            "language": current_input.language or "auto",
                            "original_input": current_input.code,
                            "primary_output": _fallback_flat_from_error(
                                len(current_input.code.splitlines()),
                                f"Primary agent failed: {message}",
                            ),
                            "judge_evaluation": judge_result,
                            "final_status": judge_result["status"],
                            "deliverable": False,
                            "session_id": config.get("session_id", ""),
                        }
                    )
                    continue

                first_output_time = round(time.perf_counter() - item_started_at, 3)
                try:
                    judge_result = await _run_judge_analysis(
                        client,
                        input_item=current_input,
                        primary_result=primary_result,
                        config=config,
                        session_id=config.get("session_id", ""),
                    )
                except (HTTPException, httpx.RequestError, httpx.TimeoutException) as exc:
                    message = exc.detail if isinstance(exc, HTTPException) else str(exc)
                    judge_result = _default_judge_evaluation(
                        f"Judge evaluation failed: {message}"
                    )

                judge_result["latency_metrics"] = {
                    "time_to_first_useful_output": first_output_time,
                    "total_runtime": round(time.perf_counter() - item_started_at, 3),
                }
                _remember_turn(
                    config.get("session_id", ""),
                    current_input.code,
                    str(primary_result.get("summary_oneliner", "")),
                )
                results.append(
                    {
                        "id": current_input.id,
                        "label": current_input.label,
                        "language": current_input.language or "auto",
                        "original_input": current_input.code,
                        "primary_output": primary_result,
                        "judge_evaluation": judge_result,
                        "final_status": judge_result["status"],
                        "deliverable": judge_result["deliverable"],
                        "session_id": config.get("session_id", ""),
                    }
                )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Blueverse request timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Blueverse connection failed: {e!s}")

    return {
        "items": results,
        "summary": {
            "total": len(results),
            "approved": sum(1 for item in results if item["final_status"] == "approved"),
            "flagged": sum(1 for item in results if item["final_status"] == "flagged"),
            "rejected": sum(1 for item in results if item["final_status"] == "rejected"),
        },
    }


def _load_benchmark_cases() -> list[BenchmarkCase]:
    if not BENCHMARK_FILE.exists():
        raise HTTPException(status_code=500, detail="Benchmark fixture file is missing")
    try:
        payload = json.loads(BENCHMARK_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Benchmark fixture JSON invalid: {exc}") from exc
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="Benchmark fixture must be a JSON array")
    return [BenchmarkCase.model_validate(item) for item in payload]


def _keyword_score(text: str, keywords: list[str]) -> dict[str, Any]:
    haystack = text.lower()
    matched = [keyword for keyword in keywords if keyword.lower() in haystack]
    score = 100 if not keywords else int(round((len(matched) / max(1, len(keywords))) * 100))
    return {"score": score, "matched": matched, "missed": [k for k in keywords if k not in matched]}


def _normalize_source_name(value: str) -> str:
    lower = value.lower()
    if "fusion" in lower:
        return "fusion"
    if "jd edwards" in lower or "jde" in lower or "enterpriseone" in lower:
        return "jde"
    if "e-business" in lower or "ebs" in lower:
        return "ebs"
    if "epm" in lower or "enterprise performance management" in lower:
        return "epm"
    return ""


def _evaluate_benchmark_sample(case: BenchmarkCase, item: dict[str, Any]) -> dict[str, Any]:
    primary = item["primary_output"]
    judge = dict(item["judge_evaluation"])
    expected = case.expected

    summary_text = " ".join(
        [
            str(primary.get("summary_oneliner", "")),
            str(primary.get("functional_purpose", "")),
            " ".join(primary.get("business_logic", []) if isinstance(primary.get("business_logic"), list) else []),
            " ".join(primary.get("dataflow_steps", []) if isinstance(primary.get("dataflow_steps"), list) else []),
            json.dumps(primary.get("security_issues", []), ensure_ascii=False) if not isinstance(primary.get("security_issues"), str) else primary.get("security_issues", ""),
            json.dumps(primary.get("antipatterns", []), ensure_ascii=False) if not isinstance(primary.get("antipatterns"), str) else primary.get("antipatterns", ""),
            json.dumps(primary.get("refactor_recommendations", []), ensure_ascii=False) if not isinstance(primary.get("refactor_recommendations"), str) else primary.get("refactor_recommendations", ""),
        ]
    )

    categories = {
        "functional_intent": _keyword_score(summary_text, expected.functional_intent_keywords),
        "data_flow": _keyword_score(summary_text, expected.data_flow_keywords),
        "complexity_hotspots": _keyword_score(summary_text, expected.complexity_hotspots),
        "security_findings": _keyword_score(summary_text, expected.security_findings),
        "performance_findings": _keyword_score(summary_text, expected.performance_findings),
        "anti_patterns": _keyword_score(summary_text, expected.anti_patterns),
        "hardcoding_gaps": _keyword_score(summary_text, expected.hardcoding_gaps),
        "error_handling_gaps": _keyword_score(summary_text, expected.error_handling_gaps),
        "refactor_recommendations": _keyword_score(summary_text, expected.refactor_recommendations),
    }

    expected_all = (
        expected.security_findings
        + expected.performance_findings
        + expected.anti_patterns
        + expected.hardcoding_gaps
        + expected.error_handling_gaps
        + expected.refactor_recommendations
    )
    actual_findings = []
    for collection_key in ("security_issues", "antipatterns", "refactor_recommendations"):
        raw = primary.get(collection_key, [])
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError:
                raw = [raw]
        if isinstance(raw, list):
            for entry in raw:
                actual_findings.append(json.dumps(entry, ensure_ascii=False).lower())

    matched_finding_terms = {
        term for term in expected_all if any(term.lower() in finding for finding in actual_findings)
    }
    unsupported_findings = [
        finding[:180]
        for finding in actual_findings
        if not any(term.lower() in finding for term in expected_all)
    ]
    precision = 100 if not actual_findings else int(round((len(matched_finding_terms) / max(1, len(actual_findings))) * 100))
    recall = 100 if not expected_all else int(round((len(matched_finding_terms) / max(1, len(expected_all))) * 100))
    false_positive_rate = 0 if not actual_findings else int(round((len(unsupported_findings) / max(1, len(actual_findings))) * 100))

    citations = primary.get("rag_citations", []) or []
    citation_sources = [str(c.get("source", "")) for c in citations if isinstance(c, dict)]
    grounding_matches = [
        source for source in citation_sources
        if any(expected_source.lower() in source.lower() for expected_source in expected.oracle_grounding_sources)
    ]
    oracle_specificity = 100 if all(_normalize_source_name(source) in ("", case.oracle_product) for source in citation_sources) else 50
    oracle_grounding = 100 if not expected.oracle_grounding_sources else int(round((len(grounding_matches) / max(1, len(expected.oracle_grounding_sources))) * 100))

    completeness = int(round(sum(value["score"] for value in categories.values()) / max(1, len(categories))))
    correctness = int(round((recall + precision + oracle_specificity) / 3))
    hallucination = min(100, max(judge["scores"]["hallucination"], false_positive_rate if unsupported_findings else 0))
    accuracy = int(round((correctness + precision + recall) / 3))
    review_time_reduction = max(
        0,
        round(
            ((case.baseline_manual_review_seconds - judge["latency_metrics"]["total_runtime"])
             / max(case.baseline_manual_review_seconds, 1))
            * 100,
            2,
        ),
    )
    status = _judge_status(completeness, correctness, hallucination, oracle_grounding)

    judge["scores"] = {
        "completeness": completeness,
        "correctness": correctness,
        "hallucination": hallucination,
    }
    judge["validation"] = {
        "accuracy": accuracy,
        "oracle_grounding": oracle_grounding,
        "oracle_specificity": oracle_specificity,
    }
    judge["finding_metrics"] = {
        "precision": precision,
        "recall": recall,
        "false_positive_rate": false_positive_rate,
    }
    judge["status"] = status
    judge["deliverable"] = status == "approved"
    judge["summary"] = (
        f"{case.label}: completeness {completeness}, correctness {correctness}, "
        f"hallucination {hallucination}, Oracle grounding {oracle_grounding}."
    )
    issues = list(judge.get("blocking_issues", []))
    if unsupported_findings:
        issues.append("Unsupported findings detected in the response.")
    if oracle_grounding < 70:
        issues.append("Oracle grounding below target threshold.")
    judge["blocking_issues"] = issues[:6]
    judge["recommended_action"] = "Deliver response." if judge["deliverable"] else "Hold response and review manually."

    return {
        "case_id": case.id,
        "artifact_type": case.artifact_type,
        "oracle_product": case.oracle_product,
        "baseline_manual_review_seconds": case.baseline_manual_review_seconds,
        "review_time_reduction_percent": review_time_reduction,
        "category_scores": {name: data["score"] for name, data in categories.items()},
        "matched_keywords": {name: data["matched"] for name, data in categories.items()},
        "missed_keywords": {name: data["missed"] for name, data in categories.items()},
        "unsupported_findings": unsupported_findings[:10],
        "grounding": {
            "expected_sources": expected.oracle_grounding_sources,
            "matched_sources": grounding_matches,
            "citation_sources": citation_sources,
        },
        "judge_evaluation": judge,
        "final_status": status,
        "deliverable": judge["deliverable"],
        "analysis_item": {
            **item,
            "judge_evaluation": judge,
            "final_status": status,
            "deliverable": judge["deliverable"],
        },
    }


def _aggregate_benchmark_results(
    sample_results: list[dict[str, Any]],
    manual_judge_score: float,
) -> dict[str, Any]:
    total = len(sample_results)
    avg = lambda values: round(sum(values) / max(1, len(values)), 2)
    review_time_reduction = avg([item["review_time_reduction_percent"] for item in sample_results])
    reviewer_confidence = avg([item["judge_evaluation"]["validation"]["accuracy"] for item in sample_results])
    anti_pattern_catch_rate = avg([item["category_scores"]["anti_patterns"] for item in sample_results])
    oracle_grounding_pass_rate = round(
        (sum(1 for item in sample_results if item["judge_evaluation"]["validation"]["oracle_grounding"] >= 85) / max(1, total)) * 100,
        2,
    )
    unsupported_claim_rate = avg([item["judge_evaluation"]["finding_metrics"]["false_positive_rate"] for item in sample_results])
    critical_issue_recall = avg([item["judge_evaluation"]["finding_metrics"]["recall"] for item in sample_results])
    time_to_first_useful_output = avg([item["judge_evaluation"]["latency_metrics"]["time_to_first_useful_output"] for item in sample_results])

    by_artifact_type: dict[str, dict[str, Any]] = {}
    by_oracle_product: dict[str, dict[str, Any]] = {}
    for result in sample_results:
        artifact = result["artifact_type"]
        product = result["oracle_product"]
        by_artifact_type.setdefault(artifact, {"count": 0, "approved": 0, "avg_review_time_reduction": 0.0})
        by_oracle_product.setdefault(product, {"count": 0, "approved": 0, "avg_grounding": 0.0})
        by_artifact_type[artifact]["count"] += 1
        by_artifact_type[artifact]["approved"] += 1 if result["final_status"] == "approved" else 0
        by_artifact_type[artifact]["avg_review_time_reduction"] += result["review_time_reduction_percent"]
        by_oracle_product[product]["count"] += 1
        by_oracle_product[product]["approved"] += 1 if result["final_status"] == "approved" else 0
        by_oracle_product[product]["avg_grounding"] += result["judge_evaluation"]["validation"]["oracle_grounding"]

    for bucket in by_artifact_type.values():
        bucket["avg_review_time_reduction"] = round(bucket["avg_review_time_reduction"] / max(1, bucket["count"]), 2)
    for bucket in by_oracle_product.values():
        bucket["avg_grounding"] = round(bucket["avg_grounding"] / max(1, bucket["count"]), 2)

    kpis = {
        "review_time_reduction_percent": review_time_reduction,
        "review_time_target_met": 30 <= review_time_reduction <= 60,
        "reviewer_confidence_percent": reviewer_confidence,
        "reviewer_confidence_target_met": reviewer_confidence >= 80,
        "anti_pattern_catch_rate_percent": anti_pattern_catch_rate,
        "anti_pattern_target_met": anti_pattern_catch_rate >= 90,
        "critical_issue_recall_percent": critical_issue_recall,
        "unsupported_claim_rate_percent": unsupported_claim_rate,
        "oracle_grounding_pass_rate_percent": oracle_grounding_pass_rate,
        "time_to_first_useful_output_seconds": time_to_first_useful_output,
        "time_to_first_useful_output_target_met": time_to_first_useful_output < 15,
        "manual_judge_score": round(manual_judge_score, 2),
        "adoption_target_met": manual_judge_score >= 4,
        "post_release_defect_reduction": "Tracked as pilot-only metric; synthetic benchmark does not claim this.",
    }

    return {
        "total_cases": total,
        "approved": sum(1 for item in sample_results if item["final_status"] == "approved"),
        "flagged": sum(1 for item in sample_results if item["final_status"] == "flagged"),
        "rejected": sum(1 for item in sample_results if item["final_status"] == "rejected"),
        "kpis": kpis,
        "artifact_type_breakdown": by_artifact_type,
        "oracle_product_breakdown": by_oracle_product,
    }


def _write_evidence_artifacts(run_id: str, payload: dict[str, Any]) -> dict[str, str]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = EVIDENCE_DIR / f"{run_id}.json"
    csv_path = EVIDENCE_DIR / f"{run_id}.csv"
    manifest_path = EVIDENCE_DIR / f"{run_id}.manifest.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case_id", "label", "artifact_type", "oracle_product", "final_status",
                "completeness", "correctness", "hallucination", "accuracy",
                "oracle_grounding", "oracle_specificity", "precision", "recall",
                "false_positive_rate", "review_time_reduction_percent",
            ]
        )
        for sample in payload["sample_results"]:
            analysis = sample["analysis_item"]
            judge = sample["judge_evaluation"]
            writer.writerow(
                [
                    sample["case_id"],
                    analysis["label"],
                    sample["artifact_type"],
                    sample["oracle_product"],
                    sample["final_status"],
                    judge["scores"]["completeness"],
                    judge["scores"]["correctness"],
                    judge["scores"]["hallucination"],
                    judge["validation"]["accuracy"],
                    judge["validation"]["oracle_grounding"],
                    judge["validation"]["oracle_specificity"],
                    judge["finding_metrics"]["precision"],
                    judge["finding_metrics"]["recall"],
                    judge["finding_metrics"]["false_positive_rate"],
                    sample["review_time_reduction_percent"],
                ]
            )

    manifest = {
        "run_id": run_id,
        "generated_at": payload["generated_at"],
        "json_report": str(json_path),
        "csv_report": str(csv_path),
        "sample_count": payload["summary"]["total_cases"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "json_report": str(json_path),
        "csv_report": str(csv_path),
        "manifest": str(manifest_path),
    }


def _latest_evidence_file() -> Path | None:
    if not EVIDENCE_DIR.exists():
        return None
    candidates = sorted(EVIDENCE_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        if candidate.name.endswith(".manifest.json"):
            continue
        return candidate
    return None


@app.get("/api/llm-usage/latest")
def latest_llm_usage(limit: int = 50):
    if not LLM_USAGE_LOG.exists():
        return {"items": []}
    lines = LLM_USAGE_LOG.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 200)):]
    items: list[dict[str, Any]] = []
    for line in reversed(lines):
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"items": items}


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    inputs = _resolve_inputs(req)
    config = _resolve_runtime_config(req)
    return await _execute_analysis_batch(inputs=inputs, config=config)


@app.get("/api/evaluate-benchmark/latest")
def latest_benchmark_evaluation():
    latest = _latest_evidence_file()
    if not latest:
        raise HTTPException(status_code=404, detail="No benchmark evidence runs available yet")
    return json.loads(latest.read_text(encoding="utf-8"))


@app.post("/api/evaluate-benchmark")
async def evaluate_benchmark(req: EvaluateBenchmarkRequest):
    cases = _load_benchmark_cases()
    requested_ids = set(req.benchmark_case_ids)
    selected_cases = [case for case in cases if not requested_ids or case.id in requested_ids]
    if not selected_cases:
        raise HTTPException(status_code=400, detail="No benchmark cases matched the provided IDs")

    analyze_req = AnalyzeRequest(
        endpoint=req.endpoint,
        token=req.token,
        judge_token=req.judge_token,
        space_name=req.space_name,
        flow_id=req.flow_id,
        judge_endpoint=req.judge_endpoint,
        judge_space_name=req.judge_space_name,
        judge_flow_id=req.judge_flow_id,
        session_id=req.session_id,
        inputs=[
            AnalyzeInput(
                id=case.id,
                code=case.code,
                language=case.language,
                label=case.label,
            )
            for case in selected_cases
        ],
    )
    config = _resolve_runtime_config(analyze_req)
    analysis_result = await _execute_analysis_batch(inputs=analyze_req.inputs, config=config)

    by_id = {item["id"]: item for item in analysis_result["items"]}
    sample_results = [_evaluate_benchmark_sample(case, by_id[case.id]) for case in selected_cases]
    summary = _aggregate_benchmark_results(sample_results, req.manual_judge_score)
    generated_at = datetime.now(timezone.utc).isoformat()
    run_id = f"benchmark-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    payload = {
        "run_id": run_id,
        "generated_at": generated_at,
        "summary": summary,
        "sample_results": sample_results,
    }
    payload["exports"] = _write_evidence_artifacts(run_id, payload)
    return payload

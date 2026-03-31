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
) -> tuple[dict[str, Any], list[dict]]:
    """
    Blueverse Foundry chat API (see chatservice/chat):
      {"query": "...", "space_name": "...", "flowId": "..."}

    Set BLUEVERSE_USE_MESSAGES=1 to use legacy PRD {messages:[...]} shape instead.
    Returns (request_body, rag_citations).
    """
    try:
        from rag_store import get_rag_context, get_rag_citations
        rag_context = get_rag_context(code[:2000])
        rag_citations = get_rag_citations(code[:2000])
    except ImportError:
        rag_context = ""
        rag_citations = []

    instruction_block = (
        "Perform highest-impact feature upgrades as per the user's PRD:\n"
        "1. PR/Diff Review Mode: analyze before vs after changes (if diff is provided), show risk delta and suggested reviewer comments.\n"
        "2. Multi-file dependency analysis: trace calls and data flow across SQL + script + config files if provided.\n"
        "3. Actionable outputs: return a list of Jira-ready tickets in a new JSON array field called 'jira_tickets'. Each item should be {'title': '...', 'description': '...', 'story_points': 5, 'type': 'Bug'}.\n"
        "4. Confidence + evidence: for every finding (security_issues, antipatterns, refactor_recommendations), include a 'confidence_score' (1-100) and an 'evidence' field with a code excerpt and standard reference.\n"
        "5. RAG on org standards: strictly apply the coding standards (provided below) and score each finding against them.\n"
        "CRITICAL: Output ONLY valid JSON. Your response must be parseable by json.loads(). Do NOT wrap in ```json or markdown.\n"
        "Mandatory JSON keys: 'summary_oneliner', 'summary_complexity', 'summary_risk', 'functional_purpose', 'business_logic', 'side_effects', 'functional_inputs', 'functional_outputs', 'dataflow_steps', 'complexity_score', 'security_score', 'security_issues', 'antipatterns', 'refactor_recommendations', 'jira_tickets'.\n"
        "All lists (security_issues, antipatterns, etc.) must be JSON arrays of strictly formatted objects mapping matching the requested keys.\n"
        "TOKEN LIMIT ALERT: Keep all textual descriptions EXTREMELY brief (1 sentence max). Limit lists to maximum 2 items each (max 2 tickets, max 2 security issues) to ensure your JSON output is not truncated!\n\n"
    )
    if rag_context:
        instruction_block += f"Org Standards (RAG Retrieved Context):\n{rag_context}\n\n"

    user_block = f"Language: {language or 'auto'}\n\n{instruction_block}Code to analyze:\n{code}"

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
    return body, rag_citations


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

    body, rag_citations = _build_request_body(req.code, req.language, space_name, flow_id)
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

    # Normalize key aliases + coerce plain-string list fields
    flat = _normalize_flat(flat)

    # Attach RAG citations so the frontend can show which org-standards docs were used
    flat["rag_citations"] = rag_citations

    return flat

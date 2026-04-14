from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
GROQ_STRUCTURED_OUTPUT_MODELS = {
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-safeguard-20b",
    "moonshotai/kimi-k2-instruct-0905",
    "meta-llama/llama-4-scout-17b-16e-instruct",
}


async def call_groq(prompt: str, *, response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.groq_api_key:
        raise RuntimeError("Groq is not configured")

    body: dict[str, Any] = {
        "model": settings.groq_model,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict JSON code-review assistant. "
                    "Return exactly one JSON object, never markdown, never an empty object."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    use_structured_output = bool(response_schema) and settings.groq_model in GROQ_STRUCTURED_OUTPUT_MODELS
    if use_structured_output:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": response_schema,
        }
    else:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
        response = await client.post(
            settings.groq_url,
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if response.status_code == 400 and use_structured_output:
            fallback_body = dict(body)
            fallback_body["response_format"] = {"type": "json_object"}
            response = await client.post(
                settings.groq_url,
                headers={
                    "Authorization": f"Bearer {settings.groq_api_key}",
                    "Content-Type": "application/json",
                },
                json=fallback_body,
            )
    response.raise_for_status()
    parsed = response.json()
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("Groq returned no choices")
    content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Groq returned empty content")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise RuntimeError("Groq returned non-object analysis output")
    if not payload:
        raise RuntimeError(f"Groq returned empty JSON object. Raw content: {content[:200]}")
    usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
    return {
        "provider": "groq",
        "model": settings.groq_model,
        "request_url": settings.groq_url,
        "request_body": body,
        "payload": payload,
        "raw_text": content,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        },
    }

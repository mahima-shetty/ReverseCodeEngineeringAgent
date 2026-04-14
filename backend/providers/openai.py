from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()


async def call_openai(prompt: str, *, response_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI is not configured")

    body: dict[str, Any] = {
        "model": settings.openai_model,
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
    if response_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": response_schema,
        }
    else:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
        response = await client.post(
            settings.openai_url,
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    response.raise_for_status()
    parsed = response.json()
    choices = parsed.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices")
    content = (((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise RuntimeError("OpenAI returned non-object analysis output")
    if not payload:
        raise RuntimeError(f"OpenAI returned empty JSON object. Raw content: {content[:200]}")
    usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
    return {
        "provider": "openai",
        "model": settings.openai_model,
        "request_url": settings.openai_url,
        "request_body": body,
        "payload": payload,
        "raw_text": content,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        },
    }

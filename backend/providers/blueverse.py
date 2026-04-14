from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()


async def call_blueverse(
    *,
    prompt: str,
    endpoint: str = "",
    token: str = "",
    response_schema: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    url = endpoint.strip() or settings.blueverse_url
    bearer = token.strip() or settings.blueverse_bearer_token
    if not url or not bearer:
        raise RuntimeError("Blueverse is not configured")

    request_prompt = prompt
    if response_schema:
        try:
            parsed_prompt = json.loads(prompt)
        except json.JSONDecodeError:
            parsed_prompt = {
                "task": "Analyze the artifact and return JSON only.",
                "prompt": prompt,
            }
        if isinstance(parsed_prompt, dict):
            parsed_prompt["response_schema"] = response_schema
            parsed_prompt["schema_mode"] = "json_schema"
            request_prompt = json.dumps(parsed_prompt, ensure_ascii=False)

    body = {
        "query": request_prompt,
        "response_format": {
            "type": "json_schema" if response_schema else "json_object",
        },
    }
    if response_schema:
        body["json_schema"] = response_schema
    if settings.blueverse_space_name:
        body["space_name"] = settings.blueverse_space_name
    if settings.blueverse_flow_id:
        body["flowId"] = settings.blueverse_flow_id

    async with httpx.AsyncClient(timeout=timeout_seconds or settings.provider_timeout_seconds) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
            json=body,
        )
    response.raise_for_status()
    raw_text = response.text
    parsed = response.json()
    payload = parsed.get("response", parsed)
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise RuntimeError("Blueverse returned non-object analysis output")

    usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
    return {
        "provider": "blueverse",
        "model": settings.blueverse_flow_id or "blueverse",
        "request_url": url,
        "request_body": body,
        "payload": payload,
        "raw_text": raw_text,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        },
    }

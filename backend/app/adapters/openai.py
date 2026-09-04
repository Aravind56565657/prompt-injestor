from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.adapters.base import AdapterError, TargetAdapter, TargetResponse
from app.adapters.http import HTTPAdapter
from app.core.config import get_settings
from app.security.ssrf import SSRFError, validate_url

settings = get_settings()


class OpenAICompatibleAdapter(TargetAdapter):
    """Adapter for OpenAI-compatible chat endpoints (e.g. OpenAI, Mistral, vLLM, Ollama)."""

    name = "openai"

    def __init__(self, target):
        super().__init__(target)
        self._http = HTTPAdapter(target)

    async def validate(self) -> list[str]:
        problems = await self._http.validate()
        meta = self.target.meta or {}
        if not meta.get("openai_model"):
            problems.append("meta.openai_model is required for openai adapter")
        return problems

    async def send_message(
        self,
        payload: str,
        *,
        conversation: list[dict] | None = None,
    ) -> TargetResponse:
        meta = self.target.meta or {}
        model = meta.get("openai_model", "model")
        messages = list(conversation or [])
        messages.append({"role": "user", "content": payload})

        try:
            validate_url(self.target.url)
        except SSRFError as exc:
            raise AdapterError(f"SSRF guard: {exc}") from exc

        body = {
            "model": model,
            "messages": messages,
            "temperature": meta.get("openai_temperature", 0.2),
            "max_tokens": meta.get("openai_max_tokens", 512),
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        auth = self.target.auth_type or "none"
        token = self.target.auth_token or ""
        if auth == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.target.timeout or settings.request_timeout
            ) as client:
                resp = await client.post(
                    self.target.url, headers=headers, json=body
                )
            latency = int((time.perf_counter() - start) * 1000)
        except httpx.HTTPError as exc:
            latency = int((time.perf_counter() - start) * 1000)
            raise AdapterError(f"openai transport error: {exc}") from exc

        try:
            data = resp.json()
            text = _extract_chat_text(data)
        except json.JSONDecodeError:
            text = resp.text

        if resp.status_code >= 400:
            raise AdapterError(f"openai http {resp.status_code}: {text[:300]}")

        return TargetResponse(
            text=text,
            status_code=resp.status_code,
            latency_ms=latency,
            raw={"model": model},
            messages=messages,
        )

    async def reset_session(self) -> bool:
        return True

    async def get_metadata(self) -> dict[str, Any]:
        return {
            "adapter": "openai",
            "model": (self.target.meta or {}).get("openai_model"),
            "target_id": self.target.id,
        }


def _extract_chat_text(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("choices",):
            if key in data and isinstance(data[key], list) and data[key]:
                choice = data[key][0]
                msg = choice.get("message") or {}
                content = msg.get("content")
                if content is not None:
                    return str(content)
                delta = choice.get("delta") or {}
                if delta.get("content") is not None:
                    return str(delta["content"])
    if isinstance(data, dict) and "result" in data:
        return str(data["result"])
    return str(data)
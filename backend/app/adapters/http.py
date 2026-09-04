from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.adapters.base import AdapterError, TargetAdapter, TargetResponse
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.entities import Target
from app.security.ssrf import SSRFError, validate_url

logger = get_logger("adapter.http")

settings = get_settings()

DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def _deep_set(obj: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    parts = path.split(".")
    cur = obj
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            cur[p] = nxt = {}
        cur = nxt
    cur[parts[-1]] = value
    return obj


def _deep_get(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]  # type: ignore[arg-type]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


class HTTPAdapter(TargetAdapter):
    name = "http"

    def __init__(self, target: Target):
        super().__init__(target)
        self._client: httpx.AsyncClient | None = None

    def _build_headers(self) -> dict[str, str]:
        headers = dict(DEFAULT_HEADERS)
        user_headers = {k: str(v) for k, v in (self.target.headers or {}).items()}
        headers.update(user_headers)
        auth = self.target.auth_type or "none"
        token = self.target.auth_token or ""
        if auth == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth == "api_key" and token:
            headers.setdefault("X-API-Key", token)
        elif auth == "basic" and token:
            headers["Authorization"] = f"Basic {token}"
        return headers

    def _build_request(self, payload: str) -> dict[str, Any]:
        template = dict(self.target.request_template or {})
        payload_path = self.target.payload_path or "message"
        _deep_set(template, payload_path, payload)
        return template

    async def _client_for(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    self.target.timeout or settings.request_timeout, connect=10
                ),
                follow_redirects=False,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def validate(self) -> list[str]:
        problems: list[str] = []
        url = self.target.url
        if not self.target.url.lower().startswith(("http://", "https://")):
            problems.append("url must be http(s)")
        try:
            validate_url(url)
        except SSRFError as exc:
            problems.append(str(exc))
        if not (self.target.payload_path or "").strip():
            problems.append("payload_path is empty")
        return problems

    async def send_message(
        self,
        payload: str,
        *,
        conversation: list[dict] | None = None,
    ) -> TargetResponse:
        try:
            validate_url(self.target.url)
        except SSRFError as exc:
            raise AdapterError(f"SSRF guard: {exc}") from exc

        body = self._build_request(payload)
        headers = self._build_headers()
        client = await self._client_for()
        method = (self.target.http_method or "POST").upper()

        start = time.perf_counter()
        try:
            resp = await client.request(method, self.target.url, json=body, headers=headers)
            latency = int((time.perf_counter() - start) * 1000)
        except httpx.TimeoutException as exc:
            latency = int((time.perf_counter() - start) * 1000)
            raise AdapterError(f"timeout after {latency}ms") from exc
        except httpx.HTTPError as exc:
            latency = int((time.perf_counter() - start) * 1000)
            raise AdapterError(f"transport error: {exc}") from exc

        if resp.is_redirect:
            location = resp.headers.get("location", "")
            raise AdapterError(f"redirect to {location} not followed")

        text: str | None = None
        content_length = resp.content
        if len(content_length) > settings.max_response_length:
            raise AdapterError(
                f"response larger than {settings.max_response_length} bytes"
            )
        try:
            data = resp.json()
            extracted = _deep_get(data, self.target.response_path)
            text = _stringify(extracted)
        except json.JSONDecodeError:
            text = resp.text
        except (AttributeError, ValueError):
            text = resp.text

        return TargetResponse(
            text=text,
            status_code=resp.status_code,
            latency_ms=latency,
            raw={"body": body, "headers": _safe_headers(headers)},
        )

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


def _safe_headers(headers: dict[str, str]) -> dict[str, str]:
    return {k: "[REDACTED]" if k.lower() in ("authorization", "x-api-key") else v for k, v in headers.items()}
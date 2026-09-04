from __future__ import annotations

import abc
from typing import Any

from app.models.entities import Target


class AdapterError(Exception):
    """Generic adapter failure (transport, timeout, parse)."""


class TargetResponse:
    def __init__(
        self,
        text: str | None,
        status_code: int | None,
        latency_ms: int,
        raw: Any | None = None,
        messages: list[dict] | None = None,
    ):
        self.text = text
        self.status_code = status_code
        self.latency_ms = latency_ms
        self.raw = raw
        self.messages = messages or []


class TargetAdapter(abc.ABC):
    name: str = "base"

    def __init__(self, target: Target):
        self.target = target

    async def validate(self) -> list[str]:
        """Return a list of configuration problems (empty = ok)."""
        return ["Adapter has no validate implementation"]

    @abc.abstractmethod
    async def send_message(
        self,
        payload: str,
        *,
        conversation: list[dict] | None = None,
    ) -> TargetResponse:
        raise NotImplementedError

    async def reset_session(self) -> bool:
        return True

    async def get_metadata(self) -> dict[str, Any]:
        return {"adapter": self.name, "target_id": self.target.id}

    @classmethod
    def create(self, target: Target) -> "TargetAdapter":
        from app.adapters.http import HTTPAdapter
        from app.adapters.mock import MockAdapter
        from app.adapters.openai import OpenAICompatibleAdapter

        kind = (target.adapter_type or "http").lower()
        registry = {
            "http": HTTPAdapter,
            "openai": OpenAICompatibleAdapter,
            "mock": MockAdapter,
        }
        cls = registry.get(kind, HTTPAdapter)
        return cls(target)
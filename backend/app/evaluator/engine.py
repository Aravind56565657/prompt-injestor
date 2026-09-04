"""Evaluation orchestrator - runs the layered pipeline and produces a verdict."""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.evaluator.decision import decide
from app.evaluator.llm_judge import evaluate_llm
from app.evaluator.rules import evaluate_rules
from app.evaluator.semantic import evaluate_semantic

logger = get_logger("evaluator.engine")

settings = get_settings()


def _classify_http(http_status: int | None, error: str | None) -> str | None:
    if error:
        return "error"
    if http_status is None:
        return None
    if http_status >= 400:
        return "error"
    return None


class EvaluationEngine:
    def __init__(self, llm_provider=None, embedding_provider=None):
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider

    async def evaluate(
        self,
        response: str | None,
        *,
        attack: dict[str, Any] | None = None,
        http_status: int | None = None,
        error: str | None = None,
        conversation: list[dict] | None = None,
    ) -> dict[str, Any]:
        transport_class = _classify_http(http_status, error)
        attack = attack or {}

        if transport_class:
            return {
                "classification": transport_class,
                "confidence": 0.95,
                "evidence": [f"http/{http_status}" if error is None else error],
                "layer_results": {},
                "signals": {"external_error": True},
                "detail": {},
            }

        rule_vote = evaluate_rules(response or "", attack)

        semantic_task = evaluate_semantic(
            response or "", attack, self.embedding_provider
        )
        llm_task = evaluate_llm(response or "", attack, self.llm_provider, conversation=conversation)
        semantic_vote, llm_vote = await asyncio.gather(
            semantic_task, llm_task, return_exceptions=True
        )
        if isinstance(semantic_vote, BaseException):
            logger.warning("semantic evaluator crashed", error=str(semantic_vote))
            semantic_vote = None
        if isinstance(llm_vote, BaseException):
            logger.warning("llm judge crashed", error=str(llm_vote))
            llm_vote = None

        votes = [rule_vote, semantic_vote, llm_vote]
        verdict = decide(
            votes,
            http_status_ok=http_status is None or http_status < 400,
            transport_error=error,
        )
        verdict["detail"].setdefault("attack_objective", attack.get("objective"))
        verdict["detail"].setdefault("attack_category", attack.get("category"))
        return verdict
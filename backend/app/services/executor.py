"""Bounded asynchronous attack executor with retries, rate limiting, and session control."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.adapters.base import AdapterError, TargetAdapter, TargetResponse
from app.core.logging import get_logger

logger = get_logger("executor")


class ExecutionCancelled(Exception):
    pass


@dataclass
class ExecutedAttempt:
    request_payload: str
    response: TargetResponse | None = None
    http_status: int | None = None
    latency_ms: int | None = None
    retries: int = 0
    error: str | None = None
    conversation: list[dict] = field(default_factory=list)


async def run_attempt(
    adapter: TargetAdapter,
    payload: str,
    *,
    conversation: list[dict] | None = None,
    timeout: int,
) -> ExecutedAttempt:
    attempt = ExecutedAttempt(request_payload=payload, conversation=list(conversation or []))
    start = time.perf_counter()
    try:
        resp = await asyncio.wait_for(
            adapter.send_message(payload, conversation=conversation),
            timeout=timeout,
        )
        attempt.response = resp
        attempt.http_status = resp.status_code
        attempt.latency_ms = resp.latency_ms
    except asyncio.TimeoutError:
        attempt.error = f"timeout after {timeout}s"
        attempt.latency_ms = int((time.perf_counter() - start) * 1000)
    except AdapterError as exc:
        attempt.error = str(exc)
        attempt.latency_ms = int((time.perf_counter() - start) * 1000)
    except Exception as exc:  # noqa: BLE001
        logger.exception("unexpected adapter error")
        attempt.error = f"unexpected error: {exc}"
        attempt.latency_ms = int((time.perf_counter() - start) * 1000)
    return attempt


class AttackExecutor:
    def __init__(
        self,
        adapter: TargetAdapter,
        *,
        concurrency: int = 5,
        timeout: int = 30,
        retry_count: int = 2,
        retry_backoff: float = 1.0,
        rate_limit_per_second: float = 0,
        max_turns: int = 3,
        multi_turn_enabled: bool = True,
    ):
        self.adapter = adapter
        self.concurrency = max(1, concurrency)
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.max_turns = max_turns
        self.multi_turn_enabled = multi_turn_enabled
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._rate_lock = asyncio.Lock()
        self._rate_interval = (
            1.0 / rate_limit_per_second if rate_limit_per_second > 0 else 0.0
        )
        self._last_request_ts = 0.0
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    async def _throttle(self) -> None:
        if self._rate_interval <= 0:
            return
        async with self._rate_lock:
            now = time.monotonic()
            wait = self._last_request_ts + self._rate_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_ts = time.monotonic()

    async def execute(
        self,
        payload: str,
        *,
        multi_turn: bool = False,
        log_context: dict[str, Any] | None = None,
    ) -> ExecutedAttempt:
        if self._cancelled:
            raise ExecutionCancelled("scan cancelled")

        async with self._semaphore:
            conversation: list[dict] = []
            uses_multi = self.multi_turn_enabled and multi_turn
            turn_attempts: list[ExecutedAttempt] = []

            turns = self.max_turns if uses_multi else 1
            for turn in range(1, turns + 1):
                if self._cancelled:
                    result = ExecutedAttempt(
                        request_payload=payload,
                        conversation=conversation,
                        error="scan cancelled",
                    )
                    break
                await self._throttle()
                attempt = await self._run_with_retry(payload, conversation)
                turn_attempts.append(attempt)
                if attempt.error or attempt.http_status and attempt.http_status >= 400:
                    # infrastructure failure: retries exhausted or hard error
                    self._log(log_context, attempt, turn)
                    return self._finalize(payload, turn_attempts, conversation)
                if attempt.response and attempt.response.text:
                    conversation.append(
                        {
                            "role": "assistant",
                            "content": attempt.response.text,
                        }
                    )
                if turn < turns:
                    conversation.append({"role": "user", "content": f"continue: {payload}"})
                self._log(log_context, attempt, turn)

            return self._finalize(payload, turn_attempts, conversation)

    async def _run_with_retry(
        self, payload: str, conversation: list[dict]
    ) -> ExecutedAttempt:
        attempts = self.retry_count + 1
        attempt: ExecutedAttempt | None = None
        for i in range(attempts):
            attempt = await run_attempt(
                self.adapter, payload, conversation=conversation, timeout=self.timeout
            )
            attempt.retries = i
            if attempt.error and i < attempts - 1:
                backoff = self.retry_backoff * (2**i)
                logger.warning(
                    "retrying attack attempt",
                    attempt=i + 1,
                    backoff_s=round(backoff, 2),
                    error=attempt.error,
                )
                await asyncio.sleep(min(backoff, 10))
                continue
            break
        return attempt or ExecutedAttempt(request_payload=payload)

    def _finalize(
        self,
        payload: str,
        attempts: list[ExecutedAttempt],
        conversation: list[dict],
    ) -> ExecutedAttempt:
        last = attempts[-1]
        last.conversation = conversation
        for t in attempts:
            if t.retries > last.retries:
                last.retries = t.retries
        return last

    def _log(self, ctx: dict[str, Any] | None, attempt: ExecutedAttempt, turn: int) -> None:
        logger.debug(
            "attempt done",
            **(ctx or {}),
            turn=turn,
            status=attempt.http_status,
            latency_ms=attempt.latency_ms,
            error=attempt.error,
        )


def is_infrastructure_error(attempt: ExecutedAttempt) -> bool:
    return attempt.error is not None or (
        attempt.http_status is not None and attempt.http_status >= 400
    )
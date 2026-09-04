"""Executent/executor, multi-turn, retry, timeout, and error-handling behavior tests."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, TargetAdapter, TargetResponse
from app.models.entities import Target
from app.services.executor import AttackExecutor, is_infrastructure_error


class FlakyAdapter(TargetAdapter):
    name = "flaky"

    def __init__(self, target, failures_before_success=1):
        super().__init__(target)
        self.calls = 0
        self.failures = failures_before_success

    async def validate(self):
        return []

    async def send_message(self, payload, *, conversation=None):
        self.calls += 1
        if self.calls <= self.failures:
            raise AdapterError("boom")
        return TargetResponse(text="ok", status_code=200, latency_ms=1)


class SlowAdapter(TargetAdapter):
    name = "slow"

    async def validate(self):
        return []

    async def send_message(self, payload, *, conversation=None):
        await asyncio.sleep(10)
        return TargetResponse(text="late", status_code=200, latency_ms=10)


class InfraFailAdapter(TargetAdapter):
    name = "infra"

    async def validate(self):
        return []

    async def send_message(self, payload, *, conversation=None):
        raise AdapterError("connection refused")


def _target(**overrides):
    data = {
        "name": "t",
        "url": "http://example.com/api",
        "request_template": {"message": ""},
        "payload_path": "message",
        "response_path": "answer",
    }
    data.update(overrides)
    return Target(**data)


class TestRetry:
    def test_retries_then_succeeds(self):
        from app.core.database import Base

        t = _target()
        adapter = FlakyAdapter(t, failures_before_success=2)
        ex = AttackExecutor(adapter, retry_count=3, retry_backoff=0.001)
        result = asyncio.run(ex.execute("payload"))
        assert result.response.text == "ok"
        assert result.retries == 2

    def test_retries_exhausted_marks_error(self):
        t = _target()
        adapter = FlakyAdapter(t, failures_before_success=5)
        ex = AttackExecutor(adapter, retry_count=2, retry_backoff=0.001)
        result = asyncio.run(ex.execute("payload"))
        assert result.error is not None
        assert is_infrastructure_error(result)


class TestTimeout:
    def test_timeout_marked_as_error(self):
        t = _target(timeout=1)
        adapter = SlowAdapter(t)
        ex = AttackExecutor(adapter, timeout=1, retry_count=0)
        result = asyncio.run(ex.execute("payload"))
        assert "timeout" in (result.error or "").lower() or "timeout" in str(result.error)
        assert is_infrastructure_error(result)


class TestInfraError:
    def test_transport_error_flagged(self):
        t = _target()
        adapter = InfraFailAdapter(t)
        ex = AttackExecutor(adapter, retry_count=0)
        result = asyncio.run(ex.execute("payload"))
        assert result.error is not None

    def test_error_never_successful(self):
        t = _target()
        adapter = InfraFailAdapter(t)
        ex = AttackExecutor(adapter, retry_count=0)
        result = asyncio.run(ex.execute("payload"))
        assert is_infrastructure_error(result)


class TestConcurrency:
    def test_concurrency_bounded(self):
        max_seen = {"v": 0}
        active = {"v": 0}

        class CountingAdapter(TargetAdapter):
            async def validate(self):
                return []

            async def send_message(self, payload, *, conversation=None):
                active["v"] += 1
                max_seen["v"] = max(max_seen["v"], active["v"])
                await asyncio.sleep(0.02)
                active["v"] -= 1
                return TargetResponse(text="ok", status_code=200, latency_ms=20)

        t = _target()
        adapter = CountingAdapter(t)
        ex = AttackExecutor(adapter, concurrency=3, retry_count=0)

        async def run():
            await asyncio.gather(*[ex.execute(f"p{i}") for i in range(12)])

        asyncio.run(run())
        assert max_seen["v"] <= 3

    def test_executor_cancellation(self):
        done = []

        class SlowAdapter(TargetAdapter):
            async def validate(self):
                return []

            async def send_message(self, payload, *, conversation=None):
                await asyncio.sleep(5)
                return TargetResponse(text="ok", status_code=200, latency_ms=1)

        t = _target()
        adapter = SlowAdapter(t)
        ex = AttackExecutor(adapter, concurrency=1, retry_count=0)

        async def run():
            task = asyncio.create_task(ex.execute("payload"))
            await asyncio.sleep(0.05)
            ex.cancel()
            await task

        asyncio.run(run())
        assert ex._cancelled is True
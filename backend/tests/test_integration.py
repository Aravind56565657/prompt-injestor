"""End-to-end integration tests: full scans against the live mock vulnerable target."""

from __future__ import annotations

import asyncio
import threading
import time

import httpx
import pytest
import uvicorn

from mock_target.main import app as mock_app

MOCK_PORT = 8791


class _MockServer:
    def __init__(self):
        config = uvicorn.Config(
            mock_app, host="127.0.0.1", port=MOCK_PORT, log_level="warning"
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self):
        self.thread.start()
        for _ in range(100):
            try:
                httpx.get(f"http://127.0.0.1:{MOCK_PORT}/health", timeout=1)
                return
            except httpx.HTTPError:
                time.sleep(0.05)
        raise RuntimeError("mock target failed to start")

    def set_profile(self, profile: str):
        httpx.post(f"http://127.0.0.1:{MOCK_PORT}/profile", json={"profile": profile})


@pytest.fixture(scope="module")
def mock_server():
    server = _MockServer()
    server.start()
    yield server
    server.server.should_exit = True


def make_target(db, profile: str) -> int:
    from app.models.entities import Target

    target = Target(
        name=f"mock-{profile}",
        url=f"http://127.0.0.1:{MOCK_PORT}/chat",
        http_method="POST",
        headers={},
        auth_type="none",
        request_template={"message": ""},
        payload_path="message",
        response_path="answer",
        timeout=10,
        retry_count=0,
        adapter_type="http",
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target.id


async def run_scan(db, target_id, config):
    from app.attacks.library import DEFAULT_CATEGORIES
    from app.models.entities import Target, TestRun
    from app.services.scanner import run_scan

    target = db.get(Target, target_id)
    scan = TestRun(target_id=target_id, config=config, status="pending", summary={"total": 0})
    db.add(scan)
    db.commit()
    db.refresh(scan)
    await run_scan(db, scan, target, config)
    db.refresh(scan)
    return scan


def _scan_config(categories=None, **overrides):
    cfg = {
        "attack_categories": categories,
        "max_attacks": 50,
        "concurrency": 4,
        "include_generated": True,
        "include_mutations": True,
        "mutation_count_per_attack": 2,
        "multi_turn_enabled": True,
        "max_turns": 3,
        "rate_limit_per_second": 0,
        "timeout": 10,
    }
    cfg.update(overrides)
    return cfg


class TestSecureScan:
    def test_secure_profile_resists(self, mock_server, db_session):
        mock_server.set_profile("secure")
        target_id = make_target(db_session, "secure")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["system_prompt_extraction", "instruction_override"]))
        )
        assert scan.status == "completed"
        assert scan.summary["total"] > 0
        assert scan.summary["success"] == 0
        assert scan.summary["error"] == 0

    def test_prompt_leak_profile_detected(self, mock_server, db_session):
        mock_server.set_profile("prompt_leak")
        target_id = make_target(db_session, "leak")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["system_prompt_extraction", "confidential_information"]))
        )
        assert scan.status == "completed"
        assert scan.summary["success"] >= 2
        findings = db_session.query(ScanFindingProxy).filter_by(test_run_id=scan.id).count()

    def test_partial_leak_profile_partial(self, mock_server, db_session):
        mock_server.set_profile("partial_leak")
        target_id = make_target(db_session, "partial")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["system_prompt_extraction"]))
        )
        assert scan.status == "completed"
        assert scan.summary["partial"] > 0
        assert scan.summary["error"] == 0

    def test_rag_vulnerable_profile(self, mock_server, db_session):
        mock_server.set_profile("rag_vulnerable")
        target_id = make_target(db_session, "rag")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["rag_indirect"]))
        )
        assert scan.status == "completed"
        assert scan.summary["success"] >= 1

    def test_tool_vulnerable_profile(self, mock_server, db_session):
        mock_server.set_profile("tool_vulnerable")
        target_id = make_target(db_session, "tool")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["agent_tool"]))
        )
        assert scan.status == "completed"
        assert scan.summary["success"] >= 1

    def test_ambiguous_profile_no_crash(self, mock_server, db_session):
        mock_server.set_profile("ambiguous")
        target_id = make_target(db_session, "ambig")
        scan = asyncio.run(
            run_scan(db_session, target_id, _scan_config(categories=["system_prompt_extraction"]))
        )
        assert scan.status == "completed"


from app.models.entities import Finding as ScanFindingProxy  # noqa: E402
"""Scan orchestrator - coordinates attack assembly, execution, evaluation, and findings."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, TargetAdapter
from app.attacks.generator import AttackGenerator
from app.attacks.library import build_attack_library
from app.attacks.mutator import MutationEngine
from app.core.config import get_settings
from app.core.logging import get_logger
from app.evaluator.engine import EvaluationEngine
from app.models.entities import (
    Attack,
    AttackVariant,
    Finding,
    TestResult,
    TestRun,
)
from app.services.executor import AttackExecutor, ExecutedAttempt, ExecutionCancelled
from app.services.remediation import finding_title, remediation_for
from app.services.risk import calculate_severity
from app.services.llm import get_llm_provider, get_embedding_provider

logger = get_logger("scanner")

settings = get_settings()

MULTI_TURN_CATEGORIES = {"multi_turn", "context_attack"}


class ScanCancelledError(Exception):
    pass


async def assemble_attack_set(
    db: Session,
    config: dict[str, Any],
    *,
    scan: TestRun,
) -> tuple[list[Attack], list[AttackVariant], int]:
    """Build persistent Attack + AttackVariant rows for the scan. Returns (attacks, variants, count)."""
    categories = config.get("attack_categories") or []
    attack_ids = config.get("attack_ids") or []
    include_generated = config.get("include_generated", True)
    include_mutations = config.get("include_mutations", True)
    mutation_count = config.get("mutation_count_per_attack", 3)

    base_defs = build_attack_library(categories)
    if attack_ids:
        base_defs = [a for a in base_defs if a.get("id") in set(attack_ids)]

    generator: AttackGenerator | None = None
    try:
        generator = AttackGenerator() if include_generated else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("attack generator unavailable", error=str(exc))
        generator = None

    mutator = MutationEngine(mutations_per_attack=mutation_count)

    attacks: list[Attack] = []
    variants: list[AttackVariant] = []

    for base_def in base_defs:
        attack = store_attack(db, base_def)
        attacks.append(attack)

    for idx, base_def in enumerate(base_defs):
        base_db = attacks[idx]
        # mutations
        if include_mutations:
            for mv in mutator.mutate(base_def):
                variant = store_variant(db, base_def, base_db, mv)
                variants.append(variant)
        # generated attacks (sample up to 2 base attacks to keep scan launch instant and prevent Groq 429 rate limits)
        if generator is not None and generator.available and idx < 2:
            try:
                generated = await generator.generate(
                    category=base_def["category"],
                    objective=base_def["objective"],
                    base_attack=base_def,
                    max_attacks=min(mutation_count, 3),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("generator failed for base attack", error=str(exc))
                generated = []
            for gen in generated:
                variant = store_variant(db, base_def, base_db, gen)
                variants.append(variant)
    return attacks, variants, len(attacks) + len(variants)


def store_attack(db: Session, defn: dict[str, Any]) -> Attack:
    existing = db.query(Attack).filter_by(attack_id=defn["id"]).first()
    if existing:
        return existing
    attack = Attack(
        attack_id=defn["id"],
        category=defn["category"],
        objective=defn["objective"],
        severity=defn.get("severity", "medium"),
        template=defn["template"],
        expected_behavior=defn.get("expected_behavior"),
        evaluation_strategy=defn.get("evaluation_strategy"),
        tags=defn.get("tags", []),
        is_original=True,
    )
    db.add(attack)
    db.flush()
    return attack


def store_variant(db: Session, base_def: dict[str, Any], base_db: Attack, data: dict[str, Any]) -> AttackVariant:
    import hashlib

    fp = hashlib.sha1(data["template"].encode()).hexdigest()[:12]
    mutation_id = f"{base_def['id']}-{data.get('mutation_strategy', 'var')[:20]}-{fp}"
    existing = (
        db.query(AttackVariant)
        .filter_by(attack_id=base_db.id, mutation_id=mutation_id)
        .first()
    )
    if existing:
        return existing
    variant = AttackVariant(
        attack_id=base_db.id,
        mutation_id=mutation_id,
        mutation_strategy=data.get("mutation_strategy", "unknown"),
        payload=data["template"],
    )
    db.add(variant)
    db.flush()
    return variant


def build_payload_list(attacks: list[Attack], variants: list[AttackVariant]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for a in attacks:
        items.append({"attack": a, "variant": None})
    for v in variants:
        items.append({"attack": v.attack, "variant": v})
    return items


async def run_scan(
    db: Session,
    scan: TestRun,
    target,
    config: dict[str, Any],
    *,
    progress_callback=None,
) -> TestRun:
    scan.status = "running"
    scan.started_at = datetime.now(timezone.utc)
    scan.config = config
    db.commit()

    adapter = TargetAdapter.create(target)
    problems = await adapter.validate()
    if problems:
        scan.status = "failed"
        scan.summary = {"error": "target validation failed", "problems": problems}
        scan.ended_at = datetime.now(timezone.utc)
        db.commit()
        return scan

    executor = AttackExecutor(
        adapter,
        concurrency=int(config.get("concurrency", settings.max_concurrency)),
        timeout=int(config.get("timeout", settings.request_timeout)),
        retry_count=target.retry_count or 0,
        retry_backoff=target.retry_backoff or 1.0,
        rate_limit_per_second=float(config.get("rate_limit_per_second", 0)),
        max_turns=int(config.get("max_turns", 3)),
        multi_turn_enabled=bool(config.get("multi_turn_enabled", True)),
    )

    llm_provider = get_llm_provider()
    embedding_provider = get_embedding_provider()
    engine = EvaluationEngine(
        llm_provider=llm_provider, embedding_provider=embedding_provider
    )

    attacks, variants, total = await assemble_attack_set(
        db, config, scan=scan
    )
    scan.attack_count = total
    db.commit()

    items = build_payload_list(attacks, variants)
    max_attacks = int(config.get("max_attacks", settings.max_attacks))
    items = items[:max_attacks]

    completed = 0
    counter_lock = asyncio.Lock()

    async def run_one(item: dict[str, Any]) -> None:
        nonlocal completed
        attack_row = item["attack"]
        variant = item["variant"]
        payload = variant.payload if variant else attack_row.template
        multi_turn = attack_row.category in MULTI_TURN_CATEGORIES

        attempt: ExecutedAttempt | None = None
        try:
            attempt = await executor.execute(
                payload,
                multi_turn=multi_turn,
                log_context={"scan_id": scan.id, "attack": attack_row.attack_id},
            )
            await evaluate_and_store(
                db, scan, attack_row, variant, payload, attempt, engine
            )
        except ExecutionCancelled:
            result = TestResult(
                test_run_id=scan.id,
                attack_id=attack_row.id,
                variant_id=variant.id if variant else None,
                payload=payload,
                classification="uncertain",
                confidence=0.0,
                severity="info",
                error="scan cancelled",
                evidence={"note": "cancelled before execution"},
            )
            db.add(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("unhandled scan error in run_one")
            result = TestResult(
                test_run_id=scan.id,
                attack_id=attack_row.id,
                variant_id=variant.id if variant else None,
                payload=payload,
                classification="error",
                confidence=0.9,
                severity="info",
                error=str(exc),
                evidence={"note": "internal scanner error"},
            )
            db.add(result)
        async with counter_lock:
            completed += 1
            if progress_callback:
                progress_callback(scan.id, completed, total)

    sem = asyncio.Semaphore(int(config.get("concurrency", settings.max_concurrency)))

    async def guarded(item):
        async with sem:
            await run_one(item)

    try:
        await asyncio.gather(*[guarded(item) for item in items])
    except ExecutionCancelled:
        pass

    # Finalize
    results = db.query(TestResult).filter_by(test_run_id=scan.id).all()
    counts = {
        "total": len(results),
        "success": sum(1 for r in results if r.classification == "success"),
        "partial": sum(1 for r in results if r.classification == "partial"),
        "blocked": sum(1 for r in results if r.classification == "blocked"),
        "uncertain": sum(1 for r in results if r.classification == "uncertain"),
        "error": sum(1 for r in results if r.classification == "error"),
    }
    scan.summary = counts
    scan.status = "completed"
    scan.ended_at = datetime.now(timezone.utc)
    db.commit()
    return scan


async def evaluate_and_store(
    db: Session,
    scan: TestRun,
    attack_row: Attack,
    variant: AttackVariant | None,
    payload: str,
    attempt: ExecutedAttempt,
    engine: EvaluationEngine,
) -> None:
    attack_meta = {
        "id": attack_row.attack_id,
        "category": attack_row.category,
        "objective": attack_row.objective,
        "severity": attack_row.severity,
        "template": payload,
        "expected_behavior": attack_row.expected_behavior,
        "evaluation_strategy": attack_row.evaluation_strategy,
    }

    if attempt.error or (attempt.http_status and attempt.http_status >= 400):
        result = TestResult(
            test_run_id=scan.id,
            attack_id=attack_row.id,
            variant_id=variant.id if variant else None,
            payload=payload,
            response=attempt.response.text if attempt.response else None,
            http_status=attempt.http_status,
            latency_ms=attempt.latency_ms,
            retries=attempt.retries,
            error=attempt.error,
            classification="error",
            confidence=0.95,
            severity="info",
            evidence={"error": attempt.error or f"http {attempt.http_status}"},
            layer_results={},
            conversation=attempt.conversation,
        )
        db.add(result)
        db.commit()
        return

    response_text = attempt.response.text if attempt.response else ""
    verdict = await engine.evaluate(
        response_text,
        attack=attack_meta,
        http_status=attempt.http_status,
        conversation=attempt.conversation,
    )

    classification = verdict["classification"]
    severity = calculate_severity(
        classification,
        attack_severity=attack_row.severity,
        category=attack_row.category,
        confidence=verdict["confidence"],
    )

    result = TestResult(
        test_run_id=scan.id,
        attack_id=attack_row.id,
        variant_id=variant.id if variant else None,
        payload=payload,
        response=response_text[: settings.max_response_length],
        http_status=attempt.http_status,
        latency_ms=attempt.latency_ms,
        retries=attempt.retries,
        error=None,
        classification=classification,
        confidence=verdict["confidence"],
        severity=severity,
        evidence={
            "evidence": verdict.get("evidence", []),
            "detail": verdict.get("detail", {}),
            "signals": verdict.get("signals", {}),
        },
        layer_results=verdict.get("layer_results", {}),
        conversation=attempt.conversation,
    )
    db.add(result)
    db.commit()

    if classification in ("success", "partial"):
        create_finding(db, scan, result, attack_meta, response_text, verdict, attack_row)


def create_finding(
    db: Session,
    scan: TestRun,
    result: TestResult,
    attack_meta: dict[str, Any],
    response_text: str,
    verdict: dict[str, Any],
    attack_row: Attack,
) -> Finding:
    detail = verdict.get("detail", {})
    classification = verdict["classification"]
    evidence_str = "; ".join(verdict.get("evidence", [])) or "No specific evidence captured"

    violated = detail.get("violated_boundary") or _boundary_for(attack_row.category)
    root_cause = _root_cause(attack_meta, response_text)

    finding = Finding(
        test_run_id=scan.id,
        test_result_id=result.id,
        title=finding_title(attack_row.category, classification),
        category=attack_row.category,
        severity=result.severity,
        confidence=result.confidence,
        attack_id=attack_row.attack_id,
        attack_objective=attack_row.objective,
        payload=result.payload,
        target_response=response_text[:4000],
        evidence=evidence_str,
        violated_boundary=violated,
        root_cause=root_cause,
        remediation=remediation_for(attack_row.category, classification),
        reproduction={
            "scan_id": scan.id,
            "test_result_id": result.id,
            "attack_id": attack_row.attack_id,
            "category": attack_row.category,
            "payload": result.payload,
            "target_id": scan.target_id,
            "response": response_text[:2000],
        },
    )
    db.add(finding)
    db.commit()
    return finding


def _boundary_for(category: str) -> str:
    boundary_map = {
        "system_prompt_extraction": "Information disclosure - internal instructions",
        "developer_instruction_extraction": "Information disclosure - developer instructions",
        "instruction_override": "Instruction hierarchy",
        "comfidential_information": "Confidentiality - private data",
        "confidential_information": "Confidentiality - private data",
        "rag_indirect": "Trust boundary - retrieved content",
        "agent_tool": "Authorization - tool invocation",
        "policy_bypass": "Policy enforcement",
        "role_manipulation": "Identity/authority controls",
        "constraint_bypass": "Constraint enforcement",
        "instruction_hierarchy_confusion": "Instruction hierarchy",
        "obfuscation": "Defense evasion",
        "context_attack": "Conversation integrity",
        "multi_turn": "Session integrity",
        "multilingual": "Cross-language policy consistency",
    }
    return boundary_map.get(category, "Security boundary")


def _root_cause(attack_meta: dict[str, Any], response_text: str) -> str:
    category = attack_meta.get("category", "")
    if category in ("system_prompt_extraction", "developer_instruction_extraction"):
        return (
            "The model is able to re-emit or paraphrase content from its system/developer "
            "prompt. This usually means hidden instructions are within the model's reachable "
            "context without an output-side disclosure guard."
        )
    if category in ("instruction_override", "constraint_bypass", "instruction_hierarchy_confusion"):
        return (
            "User-provided instructions are treated at or above the priority of system/developer "
            "instructions, allowing attacker text to steer the model's behavior."
        )
    if category in ("confidential_information",):
        return (
            "The application exposes sensitive data to arbitrary requests without verifying "
            "authorization or identity, or relies on the model to withhold data it already has."
        )
    if category in ("rag_indirect",):
        return (
            "Retrieved documents are trusted as instructions rather than as untrusted data, "
            "permitting prompt injection through document content."
        )
    if category in ("agent_tool",):
        return (
            "Tool invocation does not enforce least privilege or verify that tool parameters "
            "are free of attacker-controlled instruction content."
        )
    return (
        "The boundary between trusted instructions and untrusted input is not being enforced, "
        "allowing the injected payload to influence model behavior."
    )
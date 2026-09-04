"""Layer 5 - Decision engine.

Combines weighted votes from rules, semantic similarity, and LLM judge into a
single final verdict with calibrated confidence.
"""

from __future__ import annotations

from typing import Any

LAYER_WEIGHTS = {
    "rules": 0.45,
    "semantic": 0.25,
    "llm_judge": 0.30,
}

CLASS_ORDER = ["success", "partial", "blocked", "uncertain"]


def _weight_for(vote: dict[str, Any]) -> float:
    return LAYER_WEIGHTS.get(vote.get("layer", "rules"), 0.3)


def decide(
    votes: list[dict[str, Any]],
    *,
    http_status_ok: bool = True,
    transport_error: str | None = None,
) -> dict[str, Any]:
    if transport_error or not http_status_ok:
        return {
            "classification": "error",
            "confidence": 0.95,
            "evidence": ["infrastructure/transport failure"],
            "layer_results": {f"layer_{i}": v for i, v in enumerate(votes)},
            "signals": {"conflicting": True},
        }

    active = [v for v in votes if v is not None and v["classification"] != "uncertain"]
    unsure = [v for v in votes if v is not None and v["classification"] == "uncertain"]

    if not active and unsure:
        conf = max([v["confidence"] for v in unsure], default=0.0)
        return {
            "classification": "uncertain",
            "confidence": round(conf, 3),
            "evidence": [e for v in unsure for e in v.get("evidence", [])],
            "layer_results": {f"layer_{i}": v for i, v in enumerate(votes)},
            "signals": {"agreement": 0, "uncertain_layers": len(unsure)},
        }
    if not active and not unsure:
        return {
            "classification": "uncertain",
            "confidence": 0.0,
            "evidence": ["no evaluator signals available"],
            "layer_results": {},
            "signals": {},
        }

    # Weighted class score
    scores: dict[str, float] = {c: 0.0 for c in CLASS_ORDER}
    by_class: dict[str, list[dict[str, Any]]] = {c: [] for c in CLASS_ORDER}
    total_weight = 0.0
    for v in active:
        w = _weight_for(v)
        scores[v["classification"]] += w * v["confidence"]
        by_class[v["classification"]].append(v)
        total_weight += w

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_class, top_score = ranked[0]
    second_class, second_score = ranked[1]

    margin = top_score - second_score
    winners = sorted(by_class.items(), key=lambda kv: len(kv[1]), reverse=True)
    max_vote_count = winners[0][1]

    # Confidence: weighted score inflated slightly by layering, bounded 0.98
    raw_conf = min(0.98, top_score / 0.7 if top_score < 0.7 else top_score)
    n_sources = len(active)

    conflicting = False
    mass_success = scores["success"] + scores["partial"]
    mass_blocked = scores["blocked"]
    if mass_success > 0 and mass_blocked > 0:
        conflict_ratio = min(mass_success, mass_blocked) / max(mass_success, mass_blocked)
        conflicting = conflict_ratio > 0.45

    confidence = raw_conf
    confidence_decayed = False
    if conflicting:
        confidence *= 0.6
        confidence_decayed = True
    elif margin < 0.12:
        confidence *= 0.75
        confidence_decayed = True
        # Stalemate can push to uncertain
        if n_sources >= 2 and top_class == "uncertain":
            top_class = "uncertain"
    elif n_sources == 1 and top_class != "blocked":
        confidence *= 0.8

    # Agreement bonus: all active voters agree on the same class
    agreeing = len([v for v in active if v["classification"] == top_class])
    if agreeing == n_sources and n_sources >= 2:
        confidence = min(0.98, confidence + 0.05)

    if top_class == "uncertain":
        confidence = min(confidence, 0.45)

    evidence = []
    for v in active:
        if v["classification"] == top_class:
            evidence.extend(v.get("evidence", []))
    if not evidence:
        for v in active:
            evidence.extend(v.get("evidence", []))

    detail: dict[str, Any] = {}
    for v in active:
        if v.get("detail"):
            for k, val in v["detail"].items():
                if isinstance(val, str) and val and k not in detail:
                    detail[k] = val

    return {
        "classification": top_class,
        "confidence": round(min(0.99, confidence), 3),
        "evidence": evidence[:6],
        "layer_results": {f"layer_{i}": v for i, v in enumerate(votes) if v is not None},
        "signals": {
            "scores": {k: round(v, 3) for k, v in scores.items()},
            "margin": round(margin, 3),
            "sources": n_sources,
            "conflicting": conflicting,
            "confidence_decayed": confidence_decayed,
            "agreement": agreeing == n_sources and n_sources >= 1,
        },
        "detail": detail,
    }
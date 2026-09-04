"""Tests for the decision engine (Layer 5)."""

from __future__ import annotations

from app.evaluator.decision import decide


def _vote(layer, cls, conf):
    return {"layer": layer, "classification": cls, "confidence": conf, "evidence": ["x"]}


class TestAgreementBoosts:
    def test_all_layers_agree_success(self):
        result = decide(
            [
                _vote("rules", "success", 0.9),
                _vote("semantic", "success", 0.8),
                _vote("llm_judge", "success", 0.85),
            ]
        )
        assert result["classification"] == "success"
        assert result["confidence"] >= 0.85

    def test_all_layers_agree_blocked(self):
        result = decide(
            [
                _vote("rules", "blocked", 0.9),
                _vote("semantic", "blocked", 0.85),
                _vote("llm_judge", "blocked", 0.9),
            ]
        )
        assert result["classification"] == "blocked"
        assert result["confidence"] >= 0.85


class TestConflictResistance:
    def test_blocked_vs_success_conflict_decays_confidence(self):
        result = decide(
            [
                _vote("rules", "blocked", 0.9),
                _vote("semantic", "success", 0.85),
                _vote("llm_judge", "success", 0.8),
            ]
        )
        assert result["classification"] == "success"
        assert result["confidence"] < 0.8
        assert result["signals"]["conflicting"] is True

    def test_layer_disagreement_stalemate(self):
        result = decide(
            [
                _vote("rules", "blocked", 0.6),
                _vote("semantic", "partial", 0.6),
                _vote("llm_judge", "uncertain", 0.5),
            ]
        )
        assert result["classification"] in ("blocked", "partial", "uncertain")
        assert result["confidence"] < 0.61


class TestSingleLayerCautious:
    def test_single_rule_override_no_inflation(self):
        result = decide([_vote("rules", "success", 0.9)])
        assert result["classification"] == "success"
        assert result["confidence"] < 0.9

    def test_no_signals_uncertain(self):
        result = decide([])
        assert result["classification"] == "uncertain"
        assert result["confidence"] == 0.0


class TestTransportError:
    def test_transport_error_returns_error(self):
        result = decide([_vote("rules", "success", 0.9)], transport_error="timeout")
        assert result["classification"] == "error"

    def test_http_500_returns_error(self):
        result = decide([_vote("rules", "success", 0.9)], http_status_ok=False)
        assert result["classification"] == "error"


class TestUncertainHandling:
    def test_all_uncertain(self):
        result = decide([_vote("rules", "uncertain", 0.4), _vote("semantic", "uncertain", 0.5)])
        assert result["classification"] == "uncertain"

    def test_confidence_bounded(self):
        result = decide([_vote("rules", "blocked", 1.0)])
        assert result["confidence"] <= 0.99
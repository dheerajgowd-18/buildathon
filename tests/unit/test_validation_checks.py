"""Unit tests for Validation Center checks."""

from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_core.validation.checks import (
    check_canonical_hash_determinism,
    check_commerceproof_clamp,
    check_ground_truth_leakage_scan,
    check_hmac_webhook_roundtrip,
    check_ledger_subscription_roundtrip,
    check_negotiation_determinism,
)


def test_hmac_webhook_roundtrip_check() -> None:
    """HMAC roundtrip validation check passes and rejects tampered bodies."""
    result = check_hmac_webhook_roundtrip()
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "hmac_webhook_roundtrip"
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_canonical_hash_determinism_check() -> None:
    """Canonical hashing validation check asserts determinism and divergence on 1-paise delta."""
    result = check_canonical_hash_determinism()
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "canonical_hash_determinism"


def test_commerceproof_clamp_check() -> None:
    """CommerceProof check asserts illegal discount proposals are repaired to policy caps."""
    result = check_commerceproof_clamp()
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "commerceproof_clamp"


def test_ground_truth_leakage_scan_passes_on_clean_data() -> None:
    """Ground truth leakage scan check passes on benchmark datasets."""
    result = check_ground_truth_leakage_scan()
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "ground_truth_leakage_scan"


def test_ground_truth_leakage_scan_detects_injected_leak() -> None:
    """Ground truth leakage scan check detects simulated leaks in in-memory scenarios."""
    tampered_scenarios = [
        {
            "scenario_id": "clean_sc_01",
            "nl_utterance": "Looking for a fast laptop under 60k.",
            "true_intent": {"max_budget_minor": 6000000},
        },
        {
            "scenario_id": "leaked_sc_02",
            "nl_utterance": "Looking for target_sku with budget 5000000.",
            "true_intent": {"max_budget_minor": 5000000},
        },
    ]
    result = check_ground_truth_leakage_scan(scenarios=tampered_scenarios)
    assert result.status == "fail"
    assert "Leakage detected" in result.detail
    assert "target_sku" in result.evidence_json or "raw_budget_5000000" in result.evidence_json


def test_negotiation_determinism_check() -> None:
    """Negotiation determinism check asserts identical repeat proposals."""
    result = check_negotiation_determinism()
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "negotiation_determinism"


def test_ledger_subscription_roundtrip_check() -> None:
    """Ledger subscription check asserts real-time non-blocking event receipt."""
    ledger = TradeLedger()
    result = check_ledger_subscription_roundtrip(trade_ledger=ledger)
    assert result.status == "pass"
    assert result.category == "hermetic"
    assert result.check_id == "ledger_subscription_roundtrip"

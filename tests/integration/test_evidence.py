"""Integration and unit tests for Evidence Lab and generator scripts."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger
from scripts.generate_adversarial_evidence import generate_adversarial_evidence
from scripts.generate_evidence_samples import generate_evidence_samples


def test_evidence_page_renders_with_samples() -> None:
    """GET /evidence returns 200 and renders sections and samples table."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/evidence")
    assert res.status_code == 200
    assert "The Evidence Lab" in res.text
    assert "The Benchmark is Paired" in res.text
    assert "Twelve Scenarios, Both Arms, Raw" in res.text
    assert "Attacks We Survived" in res.text
    assert "Leakage: Zero by Construction" in res.text
    assert "Continuous Test &amp; Live Verification" in res.text or "Continuous Test & Live Verification" in res.text


def test_evidence_page_graceful_missing_jsons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /evidence returns 200 and graceful empty placeholders when JSON files are absent."""
    import merchantos_api.routers.dashboard as dash_mod

    empty_dir = tmp_path / "empty_data"
    empty_dir.mkdir()
    monkeypatch.setattr(dash_mod, "DATA_DIR", empty_dir)

    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/evidence")
    assert res.status_code == 200
    assert "The Evidence Lab" in res.text
    assert "No sample records found" in res.text
    assert "No adversarial records found" in res.text


def test_nav_contains_evidence_on_all_pages() -> None:
    """All main pages include Evidence in the topbar nav."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    routes = ["/", "/live", "/history", "/evidence", "/validation"]
    for route in routes:
        res = client.get(route)
        assert res.status_code == 200
        assert 'href="/evidence"' in res.text


def test_overview_cta_points_to_evidence() -> None:
    """Overview page hero outline CTA points to /evidence."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert '<a href="/evidence" class="btn btn-outline">' in res.text
    assert "See the evidence" in res.text


def test_generate_evidence_samples_schema(tmp_path: Path) -> None:
    """generate_evidence_samples produces valid JSON structures with 12 stratified samples."""
    out_samples = tmp_path / "samples.json"
    out_leakage = tmp_path / "leakage.json"

    samples, leakage = generate_evidence_samples(
        output_samples_file=out_samples,
        output_leakage_file=out_leakage,
    )

    assert len(samples) == 12
    assert out_samples.exists()
    assert out_leakage.exists()

    with open(out_samples, "r", encoding="utf-8") as f:
        loaded_samples = json.load(f)
    assert len(loaded_samples) == 12
    for s in loaded_samples:
        assert "scenario_id" in s
        assert "utterance" in s
        assert "divergence" in s
        assert "true_budget_minor" in s
        assert "rules" in s
        assert "growth" in s
        assert "growth_won" in s

    with open(out_leakage, "r", encoding="utf-8") as f:
        loaded_leakage = json.load(f)
    assert loaded_leakage["leaks_found"] == 0
    assert loaded_leakage["scenarios_scanned"] > 0


def test_generate_adversarial_evidence_schema(tmp_path: Path) -> None:
    """generate_adversarial_evidence produces valid adversarial attack audit records."""
    out_adv = tmp_path / "adv.json"
    records = generate_adversarial_evidence(output_file=out_adv)

    assert len(records) == 4
    assert out_adv.exists()

    with open(out_adv, "r", encoding="utf-8") as f:
        loaded_adv = json.load(f)
    assert len(loaded_adv) == 4
    for r in loaded_adv:
        assert "attack_id" in r
        assert "name" in r
        assert "payload_snippet" in r
        assert "defense" in r
        assert "recorded_events" in r
        assert "outcome" in r

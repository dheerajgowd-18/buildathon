"""Validation Runner orchestrating hermetic and live connectivity suites."""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
import queue
import threading
from typing import Any, Literal
import uuid

from merchantos_core.config import Settings
from merchantos_core.contracts import ValidationCheckResult, ValidationReport
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_core.validation.checks import (
    check_canonical_hash_determinism,
    check_commerceproof_clamp,
    check_ground_truth_leakage_scan,
    check_hmac_webhook_roundtrip,
    check_ledger_subscription_roundtrip,
    check_live_llm,
    check_live_razorpay,
    check_negotiation_determinism,
)

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


class ValidationRunner:
    """Thread-safe runner executing system validation checks with real-time SSE event publishing."""

    def __init__(self) -> None:
        self._subscribers: list[queue.Queue[ValidationCheckResult]] = []
        self._lock = threading.Lock()
        self._last_report: ValidationReport | None = None
        self._load_last_report_from_disk()

    def _load_last_report_from_disk(self) -> None:
        report_file = DATA_DIR / "validation_report.json"
        if report_file.exists():
            try:
                with open(report_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._last_report = ValidationReport.model_validate(data)
            except Exception as err:
                logger.warning(f"Could not load previous validation report from disk: {err}")

    def subscribe(self, maxsize: int = 1000) -> queue.Queue[ValidationCheckResult]:
        """Subscribe to real-time validation check completion events."""
        q: queue.Queue[ValidationCheckResult] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[ValidationCheckResult]) -> None:
        """Unsubscribe from validation check events."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _publish_result(self, result: ValidationCheckResult) -> None:
        with self._lock:
            for sub in list(self._subscribers):
                try:
                    sub.put_nowait(result)
                except queue.Full:
                    pass

    def get_last_report(self) -> ValidationReport | None:
        """Retrieve the most recent completed validation report."""
        with self._lock:
            return self._last_report

    def run(
        self,
        scope: Literal["hermetic", "live", "all"],
        settings: Settings,
        trade_ledger: TradeLedger | None = None,
        http_client: Any | None = None,
        llm_provider: Any | None = None,
        sync_hook: Any | None = None,
    ) -> ValidationReport:
        """Execute validation checks sequentially and record/broadcast findings.

        Args:
            scope: Scope of checks to execute ("hermetic", "live", or "all").
            settings: Runtime settings containing secrets/mock flags.
            trade_ledger: Optional ledger instance for subscription check.
            http_client: Optional mock http client for live Razorpay testing.
            llm_provider: Optional stubbed provider for live LLM testing.
            sync_hook: Optional hook called after each check for test synchronization.

        Returns:
            Completed ValidationReport.
        """
        run_id = f"val_run_{uuid.uuid4().hex[:8]}"
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        report = ValidationReport(
            run_id=run_id,
            scope=scope,
            started_at=started_at,
            overall_status="running",
            results=[],
        )

        checks_to_run = []

        if scope in ("hermetic", "all"):
            checks_to_run.extend(
                [
                    ("hmac_webhook_roundtrip", lambda: check_hmac_webhook_roundtrip()),
                    ("canonical_hash_determinism", lambda: check_canonical_hash_determinism()),
                    ("commerceproof_clamp", lambda: check_commerceproof_clamp()),
                    ("ground_truth_leakage_scan", lambda: check_ground_truth_leakage_scan()),
                    ("negotiation_determinism", lambda: check_negotiation_determinism()),
                    ("ledger_subscription_roundtrip", lambda: check_ledger_subscription_roundtrip(trade_ledger)),
                ]
            )

        if scope in ("live", "all"):
            checks_to_run.extend(
                [
                    ("live_razorpay", lambda: check_live_razorpay(settings, http_client=http_client)),
                    ("live_llm", lambda: check_live_llm(settings, provider=llm_provider)),
                ]
            )

        has_failure = False

        for _, check_fn in checks_to_run:
            try:
                res = check_fn()
            except Exception as err:
                res = ValidationCheckResult(
                    check_id="check_error",
                    name="Check Execution Error",
                    category="hermetic",
                    status="fail",
                    latency_ms=0,
                    detail=f"Unhandled check exception: {err}",
                    evidence_json="",
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )

            if res.status == "fail":
                has_failure = True

            report.results.append(res)
            self._publish_result(res)

            if sync_hook:
                try:
                    sync_hook(res)
                except Exception:
                    pass

        report.finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report.overall_status = "fail" if has_failure else "pass"

        # Persist report to data/validation_report.json
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        report_file = DATA_DIR / "validation_report.json"
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as err:
            logger.warning(f"Could not persist validation report to {report_file}: {err}")

        with self._lock:
            self._last_report = report

        return report

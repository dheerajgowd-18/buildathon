"""Validation Center router for hermetic proof and live external gateway verification."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import queue
import threading
from typing import Annotated, Any, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from merchantos_api.deps import get_settings, get_trade_ledger
from merchantos_core.config import Settings
from merchantos_core.contracts import ValidationCheckResult, ValidationReport
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_core.validation.runner import ValidationRunner

router = APIRouter(tags=["validation"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Singleton validation runner instance
validation_runner = ValidationRunner()


class ValidationRunRequest(BaseModel):
    scope: Literal["hermetic", "live", "all"] = Field(default="hermetic")


@router.get("/validation", response_class=HTMLResponse)
async def validation_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render the System Validation Center dashboard."""
    last_report = validation_runner.get_last_report()

    # Load testrun if present
    testrun_data = None
    testrun_file = DATA_DIR / "test_run_report.json"
    if testrun_file.exists():
        try:
            with open(testrun_file, "r", encoding="utf-8") as f:
                testrun_data = json.load(f)
        except Exception:
            testrun_data = None

    return templates.TemplateResponse(
        request=request,
        name="validation.html",
        context={
            "settings": settings,
            "last_report": last_report,
            "testrun": testrun_data,
            "active_nav": "validation",
        },
    )


@router.get("/api/validation/report")
async def get_validation_report() -> dict[str, Any]:
    """Retrieve the latest completed validation report."""
    report = validation_runner.get_last_report()
    if report is None:
        return {"report": None}
    return {"report": report.model_dump()}


@router.get("/api/validation/testrun")
async def get_testrun_report() -> dict[str, Any]:
    """Retrieve the latest programmatic pytest run report."""
    testrun_file = DATA_DIR / "test_run_report.json"
    if testrun_file.exists():
        try:
            with open(testrun_file, "r", encoding="utf-8") as f:
                return {"testrun": json.load(f)}
        except Exception:
            pass
    return {"testrun": None}


@router.post("/api/validation/run")
async def trigger_validation_run(
    payload: ValidationRunRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> dict[str, str]:
    """Trigger a validation suite execution in a background thread."""
    if payload.scope not in ("hermetic", "live", "all"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid validation scope: '{payload.scope}'. Must be 'hermetic', 'live', or 'all'.",
        )

    # Launch daemon thread
    thread = threading.Thread(
        target=validation_runner.run,
        kwargs={
            "scope": payload.scope,
            "settings": settings,
            "trade_ledger": trade_ledger,
        },
        daemon=True,
    )
    thread.start()

    run_id = f"val_run_{uuid.uuid4().hex[:8]}"
    return {"run_id": run_id, "scope": payload.scope}


@router.get("/api/validation/events")
async def sse_validation_events(
    request: Request,
    run_id: str | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events (SSE) stream broadcasting real-time validation check results."""
    event_queue: queue.Queue[ValidationCheckResult] = validation_runner.subscribe()

    async def event_generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break

                try:
                    res: ValidationCheckResult = event_queue.get_nowait()
                    data_str = res.model_dump_json()
                    yield f"event: check\ndata: {data_str}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.02)
        finally:
            validation_runner.unsubscribe(event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

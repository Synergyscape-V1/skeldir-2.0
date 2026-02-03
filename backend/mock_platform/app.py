from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

_calls = {"stripe": 0, "dummy": 0}
_state = {
    "mode": os.getenv("MOCK_PLATFORM_MODE", "success"),
    "delay_ms": int(os.getenv("MOCK_PLATFORM_DELAY_MS", "100")),
    "retry_after_seconds": int(os.getenv("MOCK_PLATFORM_RETRY_AFTER_SECONDS", "5")),
}
_lock = asyncio.Lock()


def _sanitize_mode(value: str) -> str:
    value = (value or "").strip().lower()
    if value in {"success", "rate_limit", "upstream"}:
        return value
    return "success"


async def _maybe_delay() -> None:
    delay_ms = max(0, int(_state.get("delay_ms", 0) or 0))
    if delay_ms:
        await asyncio.sleep(delay_ms / 1000.0)


@app.get("/health/ready")
async def health_ready() -> dict:
    return {"status": "ok", "mode": _state["mode"]}


@app.get("/calls")
async def get_calls() -> dict:
    return {"stripe": _calls["stripe"], "dummy": _calls["dummy"]}


@app.post("/calls/reset")
async def reset_calls() -> dict:
    async with _lock:
        _calls["stripe"] = 0
        _calls["dummy"] = 0
    return {"status": "reset"}


@app.post("/mode")
async def set_mode(payload: dict) -> dict:
    mode = _sanitize_mode(payload.get("mode"))
    delay_ms = payload.get("delay_ms")
    retry_after = payload.get("retry_after_seconds")
    _state["mode"] = mode
    if delay_ms is not None:
        try:
            _state["delay_ms"] = int(delay_ms)
        except (TypeError, ValueError):
            pass
    if retry_after is not None:
        try:
            _state["retry_after_seconds"] = int(retry_after)
        except (TypeError, ValueError):
            pass
    return {
        "mode": _state["mode"],
        "delay_ms": _state["delay_ms"],
        "retry_after_seconds": _state["retry_after_seconds"],
    }


@app.get("/v1/balance_transactions")
async def stripe_balance_transactions() -> JSONResponse:
    async with _lock:
        _calls["stripe"] += 1

    await _maybe_delay()
    mode = _state["mode"]

    if mode == "rate_limit":
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limited"},
            headers={"Retry-After": str(_state["retry_after_seconds"])},
        )

    if mode == "upstream":
        return JSONResponse(
            status_code=500,
            content={"error": "upstream"},
        )

    payload = {
        "data": [
            {"amount": 1200, "type": "charge"},
            {"amount": 800, "type": "charge"},
            {"amount": -200, "type": "fee"},
        ]
    }
    return JSONResponse(status_code=200, content=payload)


@app.get("/dummy/revenue")
async def dummy_revenue() -> dict:
    async with _lock:
        _calls["dummy"] += 1

    await _maybe_delay()
    revenue_micros = int(os.getenv("DUMMY_REVENUE_MICROS", "12340000"))
    event_count = int(os.getenv("DUMMY_EVENT_COUNT", "3"))
    return {
        "revenue_micros": revenue_micros,
        "event_count": event_count,
    }

#!/usr/bin/env python3
"""Phase 8 composed-instrumentation LLM load helper.

Conducts the certified LLM workload inline through the provider boundary
(``app.tasks.llm.explanation``'s ``generate_explanation``) while the R3 fire
runs, and always leaves an artifact behind: status, error, dispatch mode,
dispatch counts and the real start/finish interval. A failure writes a failed
artifact and exits non-zero, so the fail-closed gate refuses an authoritative
pass instead of silently accepting a missing instrument.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text


def _import_db_secret_access():
    try:
        from scripts.security.db_secret_access import resolve_runtime_database_url
        return resolve_runtime_database_url
    except ModuleNotFoundError:
        for parent in Path(__file__).resolve().parents:
            if (parent / "scripts" / "security" / "db_secret_access.py").exists():
                sys.path.insert(0, str(parent))
                from scripts.security.db_secret_access import resolve_runtime_database_url
                return resolve_runtime_database_url
        raise


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P8_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime = _import_db_secret_access()()
    if runtime.startswith("postgresql+asyncpg://"):
        return runtime.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime


def _seed_tenant(runtime_db_url: str) -> UUID:
    tenant_id = uuid4()
    now = datetime.now(timezone.utc)
    engine = create_engine(runtime_db_url)
    with engine.begin() as conn:
        required = set(
            conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'tenants'
                      AND is_nullable = 'NO'
                      AND column_default IS NULL
                      AND (is_identity IS NULL OR is_identity = 'NO')
                    """
                )
            ).scalars()
        )
    payload = {
        "id": str(tenant_id),
        "name": f"Phase8 LLM Load Tenant {tenant_id.hex[:8]}",
        "api_key_hash": f"phase8_{tenant_id.hex}",
        "notification_email": f"phase8-llm-{tenant_id.hex[:8]}@example.invalid",
        "shopify_webhook_secret": "phase8-llm-shopify-secret",
        "stripe_webhook_secret": "phase8-llm-stripe-secret",
        "paypal_webhook_secret": "phase8-llm-paypal-secret",
        "woocommerce_webhook_secret": "phase8-llm-woo-secret",
        "created_at": now,
        "updated_at": now,
    }
    insert_cols = [col for col in required if col in payload]
    missing = sorted(col for col in required if col not in payload)
    if missing:
        raise RuntimeError(f"Missing required tenant columns: {', '.join(missing)}")
    if "id" not in insert_cols:
        insert_cols.insert(0, "id")
    if "name" not in insert_cols:
        insert_cols.append("name")
    placeholders = ", ".join(f":{col}" for col in insert_cols)
    sql = text(f"INSERT INTO tenants ({', '.join(insert_cols)}) VALUES ({placeholders})")
    with engine.begin() as conn:
        conn.execute(sql, payload)
    return tenant_id


def _write_artifact(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-s", type=int, default=90)
    parser.add_argument("--interval-s", type=float, default=0.5)
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()

    from app.db.session import get_session
    from app.schemas.llm_payloads import LLMTaskPayload
    from app.workers.llm import generate_explanation

    runtime_db_url = _runtime_sync_db_url()
    tenant_id = _seed_tenant(runtime_db_url)
    user_id = uuid4()

    request_ids: list[str] = []
    started_at = datetime.now(timezone.utc)
    deadline = time.time() + max(1, int(args.duration_s))
    artifact_path = Path(args.artifact)
    result: dict[str, object] = {
        "status": "failed",
        "error": None,
        "dispatch_mode": "inline",
        "task_name": "app.tasks.llm.explanation",
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "dispatched_count": 0,
        "first_request_id": None,
        "last_request_id": None,
        "started_at": started_at.isoformat(),
        "finished_at": None,
    }
    _write_artifact(artifact_path, result)

    async def _conduct_loop() -> None:
        # One event loop for the whole run: pooled asyncpg connections must not
        # migrate across event loops (a per-dispatch asyncio.run reuses the
        # pooled connection on a new loop and fails at the pre-ping).
        while time.time() < deadline:
            request_id = f"phase8-perf-llm-{uuid4().hex[:12]}"
            payload = LLMTaskPayload(
                tenant_id=tenant_id,
                user_id=user_id,
                correlation_id=request_id,
                request_id=request_id,
                prompt={
                    "simulated_output_text": "phase8-performance-load",
                    "cache_enabled": False,
                    "simulated_cost_cents": 1,
                },
                max_cost_cents=2,
            )
            async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
                await generate_explanation(payload, session=session)
            request_ids.append(request_id)
            result["dispatched_count"] = len(request_ids)
            result["first_request_id"] = request_ids[0]
            result["last_request_id"] = request_ids[-1]
            _write_artifact(artifact_path, result)
            await asyncio.sleep(max(0.01, float(args.interval_s)))

    try:
        asyncio.run(_conduct_loop())
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_artifact(artifact_path, result)
        raise

    result["status"] = "ok"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_artifact(artifact_path, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

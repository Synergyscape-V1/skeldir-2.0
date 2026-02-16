#!/usr/bin/env python3
from __future__ import annotations

import argparse
<<<<<<< HEAD
=======
import asyncio
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B07_P8_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime = os.getenv("DATABASE_URL")
    if not runtime:
        raise RuntimeError("DATABASE_URL or B07_P8_RUNTIME_DATABASE_URL is required")
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

<<<<<<< HEAD
    from app.schemas.llm_payloads import LLMTaskPayload
    from app.services.llm_dispatch import enqueue_llm_task
=======
    from app.db.session import get_session
    from app.schemas.llm_payloads import LLMTaskPayload
    from app.workers.llm import generate_explanation
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4

    runtime_db_url = _runtime_sync_db_url()
    tenant_id = _seed_tenant(runtime_db_url)
    user_id = uuid4()

    request_ids: list[str] = []
    started_at = datetime.now(timezone.utc)
    deadline = time.time() + max(1, int(args.duration_s))
    dispatched = 0
<<<<<<< HEAD
=======

    async def _dispatch_inline(payload: LLMTaskPayload) -> None:
        async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
            await generate_explanation(payload, session=session)

>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
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
<<<<<<< HEAD
        enqueue_llm_task("explanation", payload)
=======
        asyncio.run(_dispatch_inline(payload))
>>>>>>> 2df083e09a5bb0ba4d3888d774dd055b2cb42bd4
        request_ids.append(request_id)
        dispatched += 1
        time.sleep(max(0.01, float(args.interval_s)))

    finished_at = datetime.now(timezone.utc)
    _write_artifact(
        Path(args.artifact),
        {
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "dispatched_count": dispatched,
            "first_request_id": request_ids[0] if request_ids else None,
            "last_request_id": request_ids[-1] if request_ids else None,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

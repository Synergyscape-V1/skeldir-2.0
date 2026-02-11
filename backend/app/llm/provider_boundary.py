"""
Single LLM provider choke-point (B0.7-P3).

Provider calls, budget reservation/settlement, breaker, timeout, cache, and
distillation persistence are enforced here in one ordered path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import aisuite
except ModuleNotFoundError:
    aisuite = None

from app.core.config import settings
from app.db.session import set_tenant_guc_async, set_user_guc_async
from app.models.llm import (
    LLMBreakerState,
    LLMBudgetReservation,
    LLMHourlyShutoffState,
    LLMApiCall,
    LLMMonthlyCost,
    LLMSemanticCache,
)
from app.schemas.llm_payloads import LLMTaskPayload


def _month_start_utc(occurred_at: datetime) -> date:
    at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    at = at.astimezone(timezone.utc)
    return date(at.year, at.month, 1)


def _hour_start_utc(occurred_at: datetime) -> datetime:
    at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    at = at.astimezone(timezone.utc)
    return at.replace(minute=0, second=0, microsecond=0)


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _cache_key(prompt: Mapping[str, Any], endpoint: str, model_name: str) -> str:
    seed = dict(prompt)
    seed.pop("cache_watermark", None)
    seed.pop("cache_enabled", None)
    return hashlib.sha256(f"{endpoint}|{model_name}|{_json(seed)}".encode("utf-8")).hexdigest()


def _prompt_fingerprint(prompt: Mapping[str, Any]) -> str:
    return hashlib.sha256(_json(prompt).encode("utf-8")).hexdigest()


def _watermark(prompt: Mapping[str, Any]) -> int:
    raw = prompt.get("cache_watermark", 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True, slots=True)
class ProviderBoundaryResult:
    provider: str
    model: str
    output_text: str
    reasoning_trace: Mapping[str, Any] | None
    usage: Mapping[str, int]
    status: str
    was_cached: bool
    request_id: str
    correlation_id: str
    api_call_id: UUID
    block_reason: str | None = None
    failure_reason: str | None = None
    response_metadata: Mapping[str, Any] | None = None


class SkeldirLLMProvider:
    boundary_id = "b07_p3_aisuite_chokepoint"
    breaker_key = "llm-provider"

    async def _db_now(self, session: AsyncSession) -> datetime:
        now = (await session.execute(text("SELECT now()"))).scalar_one()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    async def complete(
        self,
        *,
        model: LLMTaskPayload,
        session: AsyncSession,
        endpoint: str,
        force_failure: bool = False,
    ) -> ProviderBoundaryResult:
        await self._ensure_rls_context(session, model.tenant_id, model.user_id)

        request_id = str(model.request_id or model.correlation_id or "")
        correlation_id = str(model.correlation_id or request_id or "")
        prompt = dict(model.prompt or {})
        requested_model = str(prompt.get("model") or settings.LLM_PROVIDER_MODEL)
        key = _cache_key(prompt, endpoint, requested_model)
        prompt_fingerprint = _prompt_fingerprint(prompt)
        watermark = _watermark(prompt)
        reservation = max(0, int(model.max_cost_cents))

        api_call_id, created_at, claimed = await self._claim(
            session=session,
            model=model,
            endpoint=endpoint,
            request_id=request_id,
            correlation_id=correlation_id,
            requested_model=requested_model,
            reservation=reservation,
            cache_key=key,
            prompt_fingerprint=prompt_fingerprint,
            cache_watermark=watermark,
        )
        if not claimed:
            return await self._load_existing(
                session=session,
                api_call_id=api_call_id,
                request_id=request_id,
                correlation_id=correlation_id,
            )

        # Emergency stop-path: block before reservation/cache/provider call while keeping
        # an auditable llm_api_calls denial row for incident forensics.
        if settings.LLM_PROVIDER_KILL_SWITCH or bool(prompt.get("kill_switch", False)):
            await self._finalize_blocked(session, api_call_id, "provider_kill_switch")
            await session.commit()
            return self._blocked_result(
                api_call_id,
                request_id,
                correlation_id,
                requested_model,
                "provider_kill_switch",
            )

        month = _month_start_utc(created_at)
        now = await self._db_now(session)
        shutoff_reason = await self._hourly_block_reason(
            session=session,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            now=now,
        )
        if shutoff_reason:
            await self._release(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation)
            await self._finalize_blocked(session, api_call_id, shutoff_reason)
            await session.commit()
            return self._blocked_result(api_call_id, request_id, correlation_id, requested_model, shutoff_reason)

        reserved_ok = await self._reserve(
            session=session,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            endpoint=endpoint,
            request_id=request_id,
            month=month,
            reservation=reservation,
            cap_cents=max(0, int(settings.LLM_MONTHLY_CAP_CENTS)),
        )
        if not reserved_ok:
            await self._finalize_blocked(session, api_call_id, "monthly_cap_exceeded")
            await session.commit()
            return self._blocked_result(api_call_id, request_id, correlation_id, requested_model, "monthly_cap_exceeded")

        cache_enabled = bool(prompt.get("cache_enabled", True))
        if cache_enabled:
            hit = await self._cache_hit(session, model.tenant_id, model.user_id, endpoint, key, watermark)
            if hit is not None:
                await self._release(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation)
                usage = {
                    "input_tokens": int(hit.input_tokens),
                    "output_tokens": int(hit.output_tokens),
                    "cost_cents": 0,
                    "latency_ms": 0,
                }
                await self._finalize_success(
                    session=session,
                    api_call_id=api_call_id,
                    provider=str(hit.provider),
                    model_name=str(hit.model),
                    output_text=str(hit.response_text),
                    usage=usage,
                    was_cached=True,
                    response_metadata=hit.response_metadata_ref or {},
                    reasoning_trace=hit.reasoning_trace_ref or {},
                    reservation=reservation,
                    settled=0,
                    breaker_state="closed",
                )
                await session.commit()
                return ProviderBoundaryResult(
                    provider=str(hit.provider),
                    model=str(hit.model),
                    output_text=str(hit.response_text),
                    reasoning_trace=hit.reasoning_trace_ref,
                    usage=usage,
                    status="success",
                    was_cached=True,
                    request_id=request_id,
                    correlation_id=correlation_id,
                    api_call_id=api_call_id,
                    response_metadata=hit.response_metadata_ref,
                )

        if await self._breaker_open(session, model.tenant_id, model.user_id, now):
            await self._release(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation)
            await self._finalize_blocked(session, api_call_id, "breaker_open")
            await session.commit()
            return self._blocked_result(api_call_id, request_id, correlation_id, requested_model, "breaker_open")

        # Reservation and pre-call guards are committed before the network call so
        # no transaction is held open while waiting on provider latency.
        await session.commit()

        timeout_s = max(0.001, int(settings.LLM_PROVIDER_TIMEOUT_MS) / 1000.0)
        started = time.perf_counter()
        try:
            payload = await asyncio.wait_for(
                self._provider_call(requested_model=requested_model, prompt=prompt, reservation=reservation),
                timeout=timeout_s,
            )
            if force_failure:
                raise RuntimeError("forced_failure_after_provider_call")
            usage = dict(payload.get("usage", {}))
            usage.setdefault("input_tokens", 0)
            usage.setdefault("output_tokens", 0)
            usage.setdefault("cost_cents", 0)
            usage["latency_ms"] = max(1, int((time.perf_counter() - started) * 1000))
            settled = min(max(0, int(usage["cost_cents"])), reservation)
            settled_at = await self._db_now(session)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._settle(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation, settled)
            await self._breaker_success(session, model.tenant_id, model.user_id)
            await self._hourly_record(session, model.tenant_id, model.user_id, settled_at, settled)
            await self._monthly_cost_record(session, model.tenant_id, model.user_id, str(payload["model"]), settled, created_at)
            if cache_enabled:
                await self._cache_write(session, model.tenant_id, model.user_id, endpoint, key, watermark, payload, usage)
            metadata = dict(payload.get("response_metadata", {}))
            metadata["boundary_id"] = self.boundary_id
            await self._finalize_success(
                session=session,
                api_call_id=api_call_id,
                provider=str(payload["provider"]),
                model_name=str(payload["model"]),
                output_text=str(payload["output_text"]),
                usage=usage,
                was_cached=False,
                response_metadata=metadata,
                reasoning_trace=payload.get("reasoning_trace") or {},
                reservation=reservation,
                settled=settled,
                breaker_state="closed",
            )
            await session.commit()
            return ProviderBoundaryResult(
                provider=str(payload["provider"]),
                model=str(payload["model"]),
                output_text=str(payload["output_text"]),
                reasoning_trace=payload.get("reasoning_trace"),
                usage=usage,
                status="success",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                response_metadata=metadata,
            )
        except TimeoutError:
            failed_at = await self._db_now(session)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._release(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation)
            await self._breaker_failure(session, model.tenant_id, model.user_id, failed_at)
            await self._finalize_failed(session, api_call_id, "provider_timeout")
            await session.commit()
            return ProviderBoundaryResult(
                provider="timeout",
                model=requested_model,
                output_text="",
                reasoning_trace=None,
                usage={"input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "latency_ms": int(timeout_s * 1000)},
                status="failed",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                failure_reason="provider_timeout",
            )
        except Exception as exc:
            failed_at = await self._db_now(session)
            await self._ensure_rls_context(session, model.tenant_id, model.user_id)
            await self._release(session, model.tenant_id, model.user_id, endpoint, request_id, month, reservation)
            await self._breaker_failure(session, model.tenant_id, model.user_id, failed_at)
            await self._finalize_failed(session, api_call_id, f"provider_error:{type(exc).__name__}")
            await session.commit()
            return ProviderBoundaryResult(
                provider="error",
                model=requested_model,
                output_text="",
                reasoning_trace=None,
                usage={"input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "latency_ms": 0},
                status="failed",
                was_cached=False,
                request_id=request_id,
                correlation_id=correlation_id,
                api_call_id=api_call_id,
                failure_reason=f"provider_error:{type(exc).__name__}",
            )

    async def _ensure_rls_context(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        await set_tenant_guc_async(session, tenant_id, local=False)
        await set_user_guc_async(session, user_id, local=False)

    def _blocked_result(
        self,
        api_call_id: UUID,
        request_id: str,
        correlation_id: str,
        model_name: str,
        reason: str,
    ) -> ProviderBoundaryResult:
        return ProviderBoundaryResult(
            provider="blocked",
            model=model_name,
            output_text="",
            reasoning_trace=None,
            usage={"input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "latency_ms": 0},
            status="blocked",
            was_cached=False,
            request_id=request_id,
            correlation_id=correlation_id,
            api_call_id=api_call_id,
            block_reason=reason,
        )

    async def _claim(
        self,
        *,
        session: AsyncSession,
        model: LLMTaskPayload,
        endpoint: str,
        request_id: str,
        correlation_id: str,
        requested_model: str,
        reservation: int,
        cache_key: str,
        prompt_fingerprint: str,
        cache_watermark: int,
    ) -> tuple[UUID, datetime, bool]:
        stmt = (
            insert(LLMApiCall)
            .values(
                tenant_id=model.tenant_id,
                user_id=model.user_id,
                endpoint=endpoint,
                request_id=request_id,
                provider="pending",
                model=requested_model,
                input_tokens=0,
                output_tokens=0,
                cost_cents=0,
                latency_ms=0,
                was_cached=False,
                distillation_eligible=False,
                status="pending",
                breaker_state="closed",
                provider_attempted=False,
                budget_reservation_cents=reservation,
                budget_settled_cents=0,
                cache_key=cache_key,
                prompt_fingerprint=prompt_fingerprint,
                cache_watermark=cache_watermark,
                request_metadata_ref={"correlation_id": correlation_id, "boundary_id": self.boundary_id},
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "request_id", "endpoint"])
            .returning(LLMApiCall.id, LLMApiCall.created_at)
        )
        row = (await session.execute(stmt)).first()
        if row is not None:
            return row[0], row[1], True
        existing = (
            await session.execute(
                select(LLMApiCall.id, LLMApiCall.created_at).where(
                    LLMApiCall.tenant_id == model.tenant_id,
                    LLMApiCall.request_id == request_id,
                    LLMApiCall.endpoint == endpoint,
                )
            )
        ).first()
        if existing is None:
            raise RuntimeError("idempotency guard failed to locate existing llm_api_calls row")
        return existing[0], existing[1], False

    async def _load_existing(
        self,
        *,
        session: AsyncSession,
        api_call_id: UUID,
        request_id: str,
        correlation_id: str,
    ) -> ProviderBoundaryResult:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row after idempotency replay")
        return ProviderBoundaryResult(
            provider=row.provider,
            model=row.model,
            output_text=(row.response_metadata_ref or {}).get("output_text", ""),
            reasoning_trace=row.reasoning_trace_ref,
            usage={
                "input_tokens": int(row.input_tokens),
                "output_tokens": int(row.output_tokens),
                "cost_cents": int(row.cost_cents),
                "latency_ms": int(row.latency_ms),
            },
            status=row.status,
            was_cached=bool(row.was_cached),
            request_id=request_id,
            correlation_id=correlation_id,
            api_call_id=api_call_id,
            block_reason=row.block_reason,
            failure_reason=row.failure_reason,
            response_metadata=row.response_metadata_ref,
        )

    async def _hourly_block_reason(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> str | None:
        row = (
            await session.execute(
                select(LLMHourlyShutoffState).where(
                    LLMHourlyShutoffState.tenant_id == tenant_id,
                    LLMHourlyShutoffState.user_id == user_id,
                    LLMHourlyShutoffState.is_shutoff.is_(True),
                    LLMHourlyShutoffState.disabled_until.is_not(None),
                    LLMHourlyShutoffState.disabled_until > now,
                ).order_by(LLMHourlyShutoffState.disabled_until.desc())
            )
        ).scalars().first()
        return None if row is None else (row.reason or "hourly_shutoff_active")

    async def _reserve(
        self,
        *,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
        cap_cents: int,
    ) -> bool:
        if reservation > cap_cents or reservation < 0:
            session.add(
                LLMBudgetReservation(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    endpoint=endpoint,
                    request_id=request_id,
                    month=month,
                    reserved_cents=max(0, reservation),
                    settled_cents=0,
                    state="blocked",
                )
            )
            return False
        row = (
            await session.execute(
                text(
                    """
                    INSERT INTO llm_monthly_budget_state (
                        tenant_id, user_id, month, cap_cents, spent_cents, reserved_cents, updated_at
                    ) VALUES (:tenant_id, :user_id, :month, :cap_cents, 0, :reservation, now())
                    ON CONFLICT (tenant_id, user_id, month)
                    DO UPDATE SET
                        cap_cents = EXCLUDED.cap_cents,
                        reserved_cents = llm_monthly_budget_state.reserved_cents + :reservation,
                        updated_at = now()
                    WHERE (
                        llm_monthly_budget_state.spent_cents
                        + llm_monthly_budget_state.reserved_cents
                        + :reservation
                    ) <= EXCLUDED.cap_cents
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "month": month,
                    "cap_cents": cap_cents,
                    "reservation": reservation,
                },
            )
        ).first()
        state = "reserved" if row is not None else "blocked"
        session.add(
            LLMBudgetReservation(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                request_id=request_id,
                month=month,
                reserved_cents=max(0, reservation),
                settled_cents=0,
                state=state,
            )
        )
        return row is not None

    async def _release(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_monthly_budget_state
                SET reserved_cents = GREATEST(0, reserved_cents - :reservation), updated_at = now()
                WHERE tenant_id = :tenant_id AND user_id = :user_id AND month = :month
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "month": month,
                "reservation": reservation,
            },
        )
        await session.execute(
            text(
                """
                UPDATE llm_budget_reservations
                SET state = 'released', settled_cents = 0, updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND user_id = :user_id
                  AND endpoint = :endpoint
                  AND request_id = :request_id
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "endpoint": endpoint,
                "request_id": request_id,
            },
        )

    async def _settle(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        request_id: str,
        month: date,
        reservation: int,
        settled: int,
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE llm_monthly_budget_state
                SET
                    reserved_cents = GREATEST(0, reserved_cents - :reservation),
                    spent_cents = spent_cents + :settled,
                    updated_at = now()
                WHERE tenant_id = :tenant_id AND user_id = :user_id AND month = :month
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "month": month,
                "reservation": reservation,
                "settled": settled,
            },
        )

    async def _breaker_open(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> bool:
        row = (
            await session.execute(
                select(LLMBreakerState).where(
                    LLMBreakerState.tenant_id == tenant_id,
                    LLMBreakerState.user_id == user_id,
                    LLMBreakerState.breaker_key == self.breaker_key,
                )
            )
        ).scalars().first()
        if row is None or row.state != "open":
            return False
        opened = row.opened_at or row.updated_at
        if opened is None:
            return True
        cooldown = opened + timedelta(seconds=max(1, int(settings.LLM_BREAKER_OPEN_SECONDS)))
        if now < cooldown:
            return True
        row.state = "half_open"
        row.updated_at = now
        return False

    async def _breaker_success(self, session: AsyncSession, tenant_id: UUID, user_id: UUID) -> None:
        now = await self._db_now(session)
        row = (
            await session.execute(
                select(LLMBreakerState).where(
                    LLMBreakerState.tenant_id == tenant_id,
                    LLMBreakerState.user_id == user_id,
                    LLMBreakerState.breaker_key == self.breaker_key,
                )
            )
        ).scalars().first()
        if row is None:
            session.add(
                LLMBreakerState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    breaker_key=self.breaker_key,
                    state="closed",
                    failure_count=0,
                    opened_at=None,
                    last_trip_at=None,
                    updated_at=now,
                )
            )
            return
        row.state = "closed"
        row.failure_count = 0
        row.opened_at = None
        row.updated_at = now

    async def _breaker_failure(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
    ) -> None:
        threshold = max(1, int(settings.LLM_BREAKER_FAILURE_THRESHOLD))
        row = (
            await session.execute(
                select(LLMBreakerState).where(
                    LLMBreakerState.tenant_id == tenant_id,
                    LLMBreakerState.user_id == user_id,
                    LLMBreakerState.breaker_key == self.breaker_key,
                )
            )
        ).scalars().first()
        if row is None:
            state = "open" if threshold <= 1 else "closed"
            session.add(
                LLMBreakerState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    breaker_key=self.breaker_key,
                    state=state,
                    failure_count=1,
                    opened_at=now if state == "open" else None,
                    last_trip_at=now if state == "open" else None,
                    updated_at=now,
                )
            )
            return
        row.failure_count = int(row.failure_count or 0) + 1
        if row.failure_count >= threshold:
            row.state = "open"
            row.opened_at = now
            row.last_trip_at = now
        else:
            row.state = "closed"
        row.updated_at = now

    async def _cache_hit(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        key: str,
        watermark: int,
    ) -> LLMSemanticCache | None:
        row = (
            await session.execute(
                select(LLMSemanticCache).where(
                    LLMSemanticCache.tenant_id == tenant_id,
                    LLMSemanticCache.user_id == user_id,
                    LLMSemanticCache.endpoint == endpoint,
                    LLMSemanticCache.cache_key == key,
                )
            )
        ).scalars().first()
        if row is None or int(row.watermark) != int(watermark):
            return None
        row.hit_count = int(row.hit_count) + 1
        row.updated_at = await self._db_now(session)
        return row

    async def _cache_write(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        endpoint: str,
        key: str,
        watermark: int,
        payload: Mapping[str, Any],
        usage: Mapping[str, int],
    ) -> None:
        now = await self._db_now(session)
        stmt = (
            insert(LLMSemanticCache)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                endpoint=endpoint,
                cache_key=key,
                watermark=watermark,
                provider=str(payload["provider"]),
                model=str(payload["model"]),
                response_text=str(payload["output_text"]),
                response_metadata_ref=payload.get("response_metadata"),
                reasoning_trace_ref=payload.get("reasoning_trace"),
                input_tokens=max(0, int(usage.get("input_tokens", 0))),
                output_tokens=max(0, int(usage.get("output_tokens", 0))),
                cost_cents=max(0, int(usage.get("cost_cents", 0))),
                hit_count=0,
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "endpoint", "cache_key"],
                set_={
                    "watermark": watermark,
                    "provider": str(payload["provider"]),
                    "model": str(payload["model"]),
                    "response_text": str(payload["output_text"]),
                    "response_metadata_ref": payload.get("response_metadata"),
                    "reasoning_trace_ref": payload.get("reasoning_trace"),
                    "input_tokens": max(0, int(usage.get("input_tokens", 0))),
                    "output_tokens": max(0, int(usage.get("output_tokens", 0))),
                    "cost_cents": max(0, int(usage.get("cost_cents", 0))),
                    "updated_at": now,
                },
            )
        )
        await session.execute(stmt)

    async def _provider_call(
        self,
        *,
        requested_model: str,
        prompt: Mapping[str, Any],
        reservation: int,
    ) -> Mapping[str, Any]:
        if settings.LLM_PROVIDER_ENABLED:
            return await self._call_aisuite(requested_model=requested_model, prompt=prompt)
        return await self._call_stub(requested_model=requested_model, prompt=prompt, reservation=reservation)

    async def _call_stub(
        self,
        *,
        requested_model: str,
        prompt: Mapping[str, Any],
        reservation: int,
    ) -> Mapping[str, Any]:
        if bool(prompt.get("raise_error", False)):
            raise RuntimeError("stub_provider_error")
        delay_ms = int(prompt.get("simulated_delay_ms", 0) or 0)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        canonical = _json(prompt)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
        in_tokens = max(1, len(canonical) // 4)
        out_tokens = max(1, in_tokens // 2)
        requested_cost = int(prompt.get("simulated_cost_cents", 1) or 0)
        cost_cents = min(max(0, requested_cost), reservation)
        return {
            "provider": "stub",
            "model": requested_model,
            "output_text": str(prompt.get("simulated_output_text") or f"stub:{digest}"),
            "reasoning_trace": {"trace_type": "stub", "digest": digest},
            "response_metadata": {"source": "stub"},
            "usage": {"input_tokens": in_tokens, "output_tokens": out_tokens, "cost_cents": cost_cents},
        }

    async def _call_aisuite(self, *, requested_model: str, prompt: Mapping[str, Any]) -> Mapping[str, Any]:
        def _invoke_sync() -> Any:
            if aisuite is None:
                raise RuntimeError("aisuite_not_installed")
            client = aisuite.Client()
            messages = prompt.get("messages")
            if not isinstance(messages, list):
                user_text = prompt.get("input") or prompt.get("text") or _json(prompt)
                messages = [{"role": "user", "content": str(user_text)}]
            return client.chat.completions.create(model=requested_model, messages=messages)

        raw = await asyncio.to_thread(_invoke_sync)
        return self._normalize_aisuite(raw=raw, requested_model=requested_model)

    def _normalize_aisuite(self, *, raw: Any, requested_model: str) -> Mapping[str, Any]:
        if isinstance(raw, Mapping):
            usage = raw.get("usage") or {}
            return {
                "provider": str(raw.get("provider") or requested_model.split(":", 1)[0]),
                "model": str(raw.get("model") or requested_model),
                "output_text": str(raw.get("output_text") or raw.get("text") or ""),
                "reasoning_trace": raw.get("reasoning_trace"),
                "response_metadata": raw.get("response_metadata") or {},
                "usage": {
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "cost_cents": int(usage.get("cost_cents", 0) or 0),
                },
            }
        provider = requested_model.split(":", 1)[0] if ":" in requested_model else "aisuite"
        model_name = str(getattr(raw, "model", requested_model))
        usage_obj = getattr(raw, "usage", None)
        usage = {
            "input_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "cost_cents": 0,
        }
        text_out = ""
        reasoning = None
        choices = getattr(raw, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text_out = str(getattr(msg, "content", "") or "")
                reasoning = getattr(msg, "reasoning", None)
        return {
            "provider": provider,
            "model": model_name,
            "output_text": text_out,
            "reasoning_trace": reasoning,
            "response_metadata": {"normalized_from": "aisuite"},
            "usage": usage,
        }

    async def _hourly_record(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        now: datetime,
        settled: int,
    ) -> None:
        hour_start = _hour_start_utc(now)
        threshold = max(0, int(settings.LLM_HOURLY_SHUTOFF_CENTS))
        row = (
            await session.execute(
                select(LLMHourlyShutoffState).where(
                    LLMHourlyShutoffState.tenant_id == tenant_id,
                    LLMHourlyShutoffState.user_id == user_id,
                    LLMHourlyShutoffState.hour_start == hour_start,
                )
            )
        ).scalars().first()
        if row is None:
            row = LLMHourlyShutoffState(
                tenant_id=tenant_id,
                user_id=user_id,
                hour_start=hour_start,
                threshold_cents=threshold,
                total_cost_cents=max(0, settled),
                total_calls=1,
                is_shutoff=False,
                reason=None,
                disabled_until=None,
            )
            session.add(row)
        else:
            row.threshold_cents = threshold
            row.total_cost_cents = int(row.total_cost_cents) + max(0, settled)
            row.total_calls = int(row.total_calls) + 1
            row.updated_at = now
        if threshold > 0 and row.total_cost_cents >= threshold:
            row.is_shutoff = True
            row.reason = "hourly_threshold_exceeded"
            row.disabled_until = hour_start + timedelta(hours=1)
            row.updated_at = now

    async def _monthly_cost_record(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        user_id: UUID,
        model_name: str,
        cost_cents: int,
        occurred_at: datetime,
    ) -> None:
        month = _month_start_utc(occurred_at)
        stmt = (
            insert(LLMMonthlyCost)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                month=month,
                total_cost_cents=max(0, cost_cents),
                total_calls=1,
                model_breakdown={model_name: {"calls": 1, "cost_cents": max(0, cost_cents)}},
            )
            .on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "month"],
                set_={
                    "total_cost_cents": LLMMonthlyCost.total_cost_cents + max(0, cost_cents),
                    "total_calls": LLMMonthlyCost.total_calls + 1,
                    "model_breakdown": LLMMonthlyCost.model_breakdown,
                },
            )
        )
        await session.execute(stmt)

    async def _finalize_success(
        self,
        *,
        session: AsyncSession,
        api_call_id: UUID,
        provider: str,
        model_name: str,
        output_text: str,
        usage: Mapping[str, int],
        was_cached: bool,
        response_metadata: Mapping[str, Any],
        reasoning_trace: Mapping[str, Any],
        reservation: int,
        settled: int,
        breaker_state: str,
    ) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on success finalize")
        metadata = dict(response_metadata)
        metadata["output_text"] = output_text
        row.provider = provider
        row.model = model_name
        row.input_tokens = max(0, int(usage.get("input_tokens", 0)))
        row.output_tokens = max(0, int(usage.get("output_tokens", 0)))
        row.cost_cents = max(0, int(usage.get("cost_cents", 0)))
        row.latency_ms = max(0, int(usage.get("latency_ms", 0)))
        row.was_cached = bool(was_cached)
        row.status = "success"
        row.provider_attempted = not was_cached
        row.breaker_state = breaker_state
        row.budget_reservation_cents = max(0, reservation)
        row.budget_settled_cents = max(0, settled)
        row.response_metadata_ref = metadata
        row.reasoning_trace_ref = dict(reasoning_trace or {})
        row.distillation_eligible = False
        row.block_reason = None
        row.failure_reason = None

    async def _finalize_blocked(self, session: AsyncSession, api_call_id: UUID, reason: str) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on blocked finalize")
        row.status = "blocked"
        row.block_reason = reason
        row.failure_reason = None
        row.provider_attempted = False
        row.breaker_state = "open" if reason == "breaker_open" else "closed"
        row.response_metadata_ref = {"output_text": ""}
        row.reasoning_trace_ref = {}
        row.distillation_eligible = False

    async def _finalize_failed(self, session: AsyncSession, api_call_id: UUID, reason: str) -> None:
        row = await session.get(LLMApiCall, api_call_id)
        if row is None:
            raise RuntimeError("missing llm_api_calls row on failed finalize")
        row.status = "failed"
        row.failure_reason = reason
        row.block_reason = None
        row.provider_attempted = True
        row.response_metadata_ref = {"output_text": ""}
        row.reasoning_trace_ref = {}
        row.distillation_eligible = False


def get_llm_provider_boundary() -> SkeldirLLMProvider:
    return SkeldirLLMProvider()

"""
LLM subsystem ORM models for audit and job tracking.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.identity import SYSTEM_USER_ID
from app.models.base import Base


class LLMApiCall(Base):
    """Audit log for LLM API usage and costs."""

    __tablename__ = "llm_api_calls"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        server_default=str(SYSTEM_USER_ID),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="stub",
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    was_cached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    distillation_eligible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    request_metadata_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    response_metadata_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reasoning_trace_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    prompt_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    breaker_state: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="closed",
        server_default="closed",
    )
    provider_attempted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    budget_reservation_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    budget_settled_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    cache_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cache_watermark: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    request_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
        CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
        CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
        CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
        CheckConstraint(
            "status IN ('pending', 'success', 'blocked', 'failed', 'idempotent_replay')",
            name="ck_llm_api_calls_status_valid",
        ),
        CheckConstraint(
            "breaker_state IN ('closed', 'open', 'half_open')",
            name="ck_llm_api_calls_breaker_state_valid",
        ),
        CheckConstraint(
            "budget_reservation_cents >= 0",
            name="ck_llm_api_calls_budget_reservation_nonnegative",
        ),
        CheckConstraint(
            "budget_settled_cents >= 0",
            name="ck_llm_api_calls_budget_settled_nonnegative",
        ),
        UniqueConstraint(
            "tenant_id",
            "request_id",
            "endpoint",
            name="uq_llm_api_calls_tenant_request_endpoint",
        ),
    )


class LLMMonthlyCost(Base):
    """Monthly aggregated LLM cost totals."""

    __tablename__ = "llm_monthly_costs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        server_default=str(SYSTEM_USER_ID),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    total_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    model_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "month",
            name="uq_llm_monthly_costs_tenant_user_month",
        ),
        CheckConstraint("total_cost_cents >= 0", name="ck_llm_monthly_costs_cost_cents_positive"),
        CheckConstraint("total_calls >= 0", name="ck_llm_monthly_costs_total_calls_positive"),
    )


class Investigation(Base):
    """Investigation job tracking for LLM investigations."""

    __tablename__ = "investigations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cost_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_investigations_status_valid",
        ),
        CheckConstraint("cost_cents >= 0", name="ck_investigations_cost_cents_positive"),
    )


class BudgetOptimizationJob(Base):
    """Budget optimization job tracking for LLM workflows."""

    __tablename__ = "budget_optimization_jobs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    cost_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_budget_optimization_jobs_status_valid",
        ),
        CheckConstraint("cost_cents >= 0", name="ck_budget_optimization_jobs_cost_cents_positive"),
    )


class LLMBreakerState(Base):
    """Circuit breaker state for LLM budget enforcement."""

    __tablename__ = "llm_breaker_state"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    breaker_key: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    failure_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_trip_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "breaker_key",
            name="uq_llm_breaker_state_tenant_user_key",
        ),
        CheckConstraint(
            "state IN ('closed', 'open', 'half_open')",
            name="ck_llm_breaker_state_state_valid",
        ),
        CheckConstraint("failure_count >= 0", name="ck_llm_breaker_state_failure_count_positive"),
    )


class LLMMonthlyBudgetState(Base):
    """Per-user monthly budget state with reserved vs spent counters."""

    __tablename__ = "llm_monthly_budget_state"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    cap_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    spent_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    reserved_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "month",
            name="uq_llm_monthly_budget_state_tenant_user_month",
        ),
        CheckConstraint("cap_cents >= 0", name="ck_llm_monthly_budget_state_cap_nonnegative"),
        CheckConstraint("spent_cents >= 0", name="ck_llm_monthly_budget_state_spent_nonnegative"),
        CheckConstraint(
            "reserved_cents >= 0",
            name="ck_llm_monthly_budget_state_reserved_nonnegative",
        ),
    )


class LLMBudgetReservation(Base):
    """Request-scoped budget reservation rows for settlement/idempotency."""

    __tablename__ = "llm_budget_reservations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    reserved_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    settled_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "endpoint",
            "request_id",
            name="uq_llm_budget_reservations_tenant_user_endpoint_request",
        ),
        CheckConstraint("reserved_cents >= 0", name="ck_llm_budget_reservations_reserved_nonnegative"),
        CheckConstraint("settled_cents >= 0", name="ck_llm_budget_reservations_settled_nonnegative"),
        CheckConstraint(
            "state IN ('reserved', 'settled', 'released', 'blocked')",
            name="ck_llm_budget_reservations_state_valid",
        ),
    )


class LLMSemanticCache(Base):
    """Tenant/user scoped semantic cache rows keyed by endpoint + cache_key."""

    __tablename__ = "llm_semantic_cache"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    cache_key: Mapped[str] = mapped_column(Text, nullable=False)
    watermark: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_metadata_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reasoning_trace_ref: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    cost_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "endpoint",
            "cache_key",
            name="uq_llm_semantic_cache_tenant_user_endpoint_key",
        ),
        CheckConstraint("input_tokens >= 0", name="ck_llm_semantic_cache_input_tokens_nonnegative"),
        CheckConstraint("output_tokens >= 0", name="ck_llm_semantic_cache_output_tokens_nonnegative"),
        CheckConstraint("cost_cents >= 0", name="ck_llm_semantic_cache_cost_nonnegative"),
        CheckConstraint("hit_count >= 0", name="ck_llm_semantic_cache_hit_count_nonnegative"),
    )


class LLMHourlyShutoffState(Base):
    """Hourly shutoff guardrail state for LLM usage."""

    __tablename__ = "llm_hourly_shutoff_state"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    hour_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_shutoff: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    threshold_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_cost_cents: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    total_calls: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    disabled_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            "hour_start",
            name="uq_llm_hourly_shutoff_tenant_user_hour",
        ),
        CheckConstraint("threshold_cents >= 0", name="ck_llm_hourly_shutoff_threshold_nonnegative"),
        CheckConstraint("total_cost_cents >= 0", name="ck_llm_hourly_shutoff_total_cost_nonnegative"),
        CheckConstraint("total_calls >= 0", name="ck_llm_hourly_shutoff_total_calls_nonnegative"),
    )

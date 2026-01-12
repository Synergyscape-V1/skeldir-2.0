"""
LLM subsystem ORM models for audit and job tracking.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    was_cached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=True,
    )
    request_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_llm_api_calls_input_tokens_positive"),
        CheckConstraint("output_tokens >= 0", name="ck_llm_api_calls_output_tokens_positive"),
        CheckConstraint("cost_cents >= 0", name="ck_llm_api_calls_cost_cents_positive"),
        CheckConstraint("latency_ms >= 0", name="ck_llm_api_calls_latency_ms_positive"),
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
            "month",
            name="uq_llm_monthly_costs_tenant_month",
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

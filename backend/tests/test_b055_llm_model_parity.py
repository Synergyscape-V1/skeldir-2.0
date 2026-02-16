from __future__ import annotations

import pytest
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text, inspect
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID as PGUUID

from app.db.session import engine
from app.models.llm import (
    BudgetOptimizationJob,
    Investigation,
    LLMApiCall,
    LLMBudgetReservation,
    LLMBreakerState,
    LLMHourlyShutoffState,
    LLMMonthlyBudgetState,
    LLMMonthlyCost,
    LLMSemanticCache,
)


def _normalize_type(sa_type) -> str:
    if isinstance(sa_type, PGUUID):
        return "uuid"
    if isinstance(sa_type, JSONB):
        return "jsonb"
    if isinstance(sa_type, (DateTime, TIMESTAMP)):
        return "datetime_tz" if getattr(sa_type, "timezone", False) else "datetime"
    if isinstance(sa_type, Date):
        return "date"
    if isinstance(sa_type, Boolean):
        return "boolean"
    if isinstance(sa_type, Integer):
        return "integer"
    if isinstance(sa_type, Float):
        # Postgres reflects SQLAlchemy Float as DOUBLE PRECISION.
        return "double_precision"
    if isinstance(sa_type, Text):
        return "text"
    if isinstance(sa_type, String):
        return "string"
    return sa_type.__class__.__name__.lower()


@pytest.mark.asyncio
async def test_llm_models_reflection_parity():
    assert engine.dialect.name == "postgresql", "ORM parity tests must run on Postgres"
    table_map = {
        "llm_api_calls": LLMApiCall,
        "llm_monthly_costs": LLMMonthlyCost,
        "llm_monthly_budget_state": LLMMonthlyBudgetState,
        "llm_budget_reservations": LLMBudgetReservation,
        "llm_semantic_cache": LLMSemanticCache,
        "investigations": Investigation,
        "budget_optimization_jobs": BudgetOptimizationJob,
        "llm_breaker_state": LLMBreakerState,
        "llm_hourly_shutoff_state": LLMHourlyShutoffState,
    }

    async with engine.connect() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            for table_name, model in table_map.items():
                db_columns = {col["name"]: col for col in inspector.get_columns(table_name)}
                model_columns = {col.name: col for col in model.__table__.columns}

                missing = set(db_columns) - set(model_columns)
                extra = set(model_columns) - set(db_columns)
                assert not missing, f"{table_name} missing columns in ORM: {missing}"
                assert not extra, f"{table_name} extra columns in ORM: {extra}"

                for col_name, db_col in db_columns.items():
                    model_col = model_columns[col_name]
                    assert _normalize_type(db_col["type"]) == _normalize_type(model_col.type), (
                        f"{table_name}.{col_name} type mismatch: "
                        f"db={db_col['type']} model={model_col.type}"
                    )
                    assert db_col["nullable"] == model_col.nullable, (
                        f"{table_name}.{col_name} nullable mismatch: "
                        f"db={db_col['nullable']} model={model_col.nullable}"
                    )
                    db_has_default = db_col["default"] is not None
                    model_has_default = model_col.server_default is not None
                    assert db_has_default == model_has_default, (
                        f"{table_name}.{col_name} default mismatch: "
                        f"db_default={db_col['default']} model_default={model_col.server_default}"
                    )

        await conn.run_sync(_inspect)

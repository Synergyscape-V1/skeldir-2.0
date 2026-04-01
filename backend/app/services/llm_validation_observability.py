"""Deterministic local metrics and alert simulation for LLM validation failures."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalized_threshold(value: float) -> float:
    if value < 0:
        return 0.0
    if value > 1:
        return 1.0
    return float(value)


@dataclass(frozen=True, slots=True)
class ValidationRejectionRate:
    feature: str
    model: str
    window_start: datetime
    window_end: datetime
    total_requests: int
    rejected_requests: int
    rejection_rate: float


@dataclass(frozen=True, slots=True)
class ValidationAlertDecision:
    feature: str
    model: str
    window_start: datetime
    window_end: datetime
    total_requests: int
    rejected_requests: int
    rejection_rate: float
    threshold_ratio: float
    min_requests: int
    alert_triggered: bool


class LLMValidationObservabilityService:
    """Compute rejection-rate metrics and simulate threshold alerts locally."""

    async def compute_rejection_rates(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        window_start: datetime,
        window_end: datetime,
        features: Iterable[str] | None = None,
        models: Iterable[str] | None = None,
    ) -> list[ValidationRejectionRate]:
        normalized_start = _as_utc(window_start)
        normalized_end = _as_utc(window_end)
        if normalized_end <= normalized_start:
            raise ValueError("window_end must be greater than window_start")

        feature_list = sorted(
            {str(item) for item in (features or []) if str(item).strip()}
        )
        model_list = sorted({str(item) for item in (models or []) if str(item).strip()})

        feature_filter_sql = ""
        model_filter_sql = ""
        if feature_list:
            feature_filter_sql = " AND c.endpoint IN :features"
        if model_list:
            model_filter_sql = " AND c.model IN :models"

        stmt = text(
            f"""
            WITH distinct_failures AS (
                SELECT DISTINCT
                    tenant_id,
                    endpoint,
                    request_payload ->> 'request_id' AS request_id
                FROM llm_validation_failures
                WHERE tenant_id = :tenant_id
                  AND created_at >= :window_start
                  AND created_at < :window_end
                  AND COALESCE(request_payload ->> 'request_id', '') <> ''
            )
            SELECT
                c.endpoint AS feature,
                c.model AS model,
                COUNT(*)::BIGINT AS total_requests,
                COUNT(df.request_id)::BIGINT AS rejected_requests
            FROM llm_api_calls c
            LEFT JOIN distinct_failures df
              ON df.tenant_id = c.tenant_id
             AND df.endpoint = c.endpoint
             AND df.request_id = c.request_id
            WHERE c.tenant_id = :tenant_id
              AND c.created_at >= :window_start
              AND c.created_at < :window_end
              {feature_filter_sql}
              {model_filter_sql}
            GROUP BY c.endpoint, c.model
            ORDER BY c.endpoint, c.model
            """
        )
        if feature_list:
            stmt = stmt.bindparams(bindparam("features", expanding=True))
        if model_list:
            stmt = stmt.bindparams(bindparam("models", expanding=True))

        params: dict[str, object] = {
            "tenant_id": str(tenant_id),
            "window_start": normalized_start,
            "window_end": normalized_end,
        }
        if feature_list:
            params["features"] = feature_list
        if model_list:
            params["models"] = model_list

        rows = (await session.execute(stmt, params)).mappings().all()
        metrics: list[ValidationRejectionRate] = []
        for row in rows:
            total_requests = max(0, int(row["total_requests"] or 0))
            rejected_requests = max(0, int(row["rejected_requests"] or 0))
            rejection_rate = (
                float(rejected_requests) / float(total_requests)
                if total_requests
                else 0.0
            )
            metrics.append(
                ValidationRejectionRate(
                    feature=str(row["feature"]),
                    model=str(row["model"]),
                    window_start=normalized_start,
                    window_end=normalized_end,
                    total_requests=total_requests,
                    rejected_requests=rejected_requests,
                    rejection_rate=rejection_rate,
                )
            )
        return metrics

    @staticmethod
    def classify_alert_threshold(
        *,
        metrics: Iterable[ValidationRejectionRate],
        threshold_ratio: float,
        min_requests: int = 1,
    ) -> list[ValidationAlertDecision]:
        normalized_threshold = _normalized_threshold(float(threshold_ratio))
        normalized_min_requests = max(1, int(min_requests))
        decisions: list[ValidationAlertDecision] = []
        for metric in metrics:
            alert_triggered = (
                metric.total_requests >= normalized_min_requests
                and metric.rejection_rate >= normalized_threshold
            )
            decisions.append(
                ValidationAlertDecision(
                    feature=metric.feature,
                    model=metric.model,
                    window_start=metric.window_start,
                    window_end=metric.window_end,
                    total_requests=metric.total_requests,
                    rejected_requests=metric.rejected_requests,
                    rejection_rate=metric.rejection_rate,
                    threshold_ratio=normalized_threshold,
                    min_requests=normalized_min_requests,
                    alert_triggered=alert_triggered,
                )
            )
        return decisions

    async def simulate_alert_threshold(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        window_start: datetime,
        window_end: datetime,
        threshold_ratio: float,
        min_requests: int = 1,
        features: Iterable[str] | None = None,
        models: Iterable[str] | None = None,
    ) -> list[ValidationAlertDecision]:
        metrics = await self.compute_rejection_rates(
            session,
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            features=features,
            models=models,
        )
        decisions = self.classify_alert_threshold(
            metrics=metrics,
            threshold_ratio=threshold_ratio,
            min_requests=min_requests,
        )
        for decision in decisions:
            logger.info(
                "llm_validation_rejection_alert_simulation",
                extra={
                    "tenant_id": str(tenant_id),
                    "event_type": "llm.validation_rejection_alert_simulation",
                    "feature": decision.feature,
                    "model": decision.model,
                    "window_start": decision.window_start.isoformat(),
                    "window_end": decision.window_end.isoformat(),
                    "total_requests": decision.total_requests,
                    "rejected_requests": decision.rejected_requests,
                    "rejection_rate": round(decision.rejection_rate, 6),
                    "threshold_ratio": round(decision.threshold_ratio, 6),
                    "min_requests": decision.min_requests,
                    "alert_triggered": decision.alert_triggered,
                },
            )
        return decisions

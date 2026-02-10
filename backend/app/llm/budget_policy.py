"""
Budget Policy Engine for LLM Cost Enforcement.

This module implements the budget-kill circuit breaker that prevents
premium LLM calls from exceeding configured cost caps.

Design Principles:
- No premium call happens beyond cap (e.g., $0.30)
- Cost estimation uses Decimal for precision
- All decisions are audited to llm_call_audit table
- Fallback to cheaper model when over budget

Architecture:
- PricingCatalog: Model → (input_per_1k, output_per_1k) pricing
- BudgetPolicy: Per-investigation cap and fallback configuration
- BudgetPolicyEngine: Decision engine (ALLOW/BLOCK/FALLBACK)
- llm_call_audit: Append-only audit sink
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.money import MoneyCents, to_cents

logger = logging.getLogger(__name__)


class BudgetAction(str, Enum):
    """Actions the budget policy can take."""
    ALLOW = "ALLOW"      # Request is under budget, proceed
    BLOCK = "BLOCK"      # Request exceeds budget, return 429
    FALLBACK = "FALLBACK"  # Substitute cheaper model


@dataclass(frozen=True)
class ModelPricing:
    """Pricing for an LLM model per 1000 tokens."""
    input_per_1k_usd: Decimal
    output_per_1k_usd: Decimal


# Production pricing catalog (as of 2025-01)
# Values in USD per 1000 tokens
PRICING_CATALOG: Dict[str, ModelPricing] = {
    # Premium tier
    "gpt-4": ModelPricing(
        input_per_1k_usd=Decimal("0.03"),
        output_per_1k_usd=Decimal("0.06"),
    ),
    "gpt-4-turbo": ModelPricing(
        input_per_1k_usd=Decimal("0.01"),
        output_per_1k_usd=Decimal("0.03"),
    ),
    "claude-3-opus": ModelPricing(
        input_per_1k_usd=Decimal("0.015"),
        output_per_1k_usd=Decimal("0.075"),
    ),
    # Standard tier
    "gpt-3.5-turbo": ModelPricing(
        input_per_1k_usd=Decimal("0.0005"),
        output_per_1k_usd=Decimal("0.0015"),
    ),
    "claude-3-sonnet": ModelPricing(
        input_per_1k_usd=Decimal("0.003"),
        output_per_1k_usd=Decimal("0.015"),
    ),
    # Budget tier (fallback)
    "gpt-3.5-turbo-instruct": ModelPricing(
        input_per_1k_usd=Decimal("0.0015"),
        output_per_1k_usd=Decimal("0.002"),
    ),
    "claude-3-haiku": ModelPricing(
        input_per_1k_usd=Decimal("0.00025"),
        output_per_1k_usd=Decimal("0.00125"),
    ),
}

# Default fallback model (cheapest)
DEFAULT_FALLBACK_MODEL = "claude-3-haiku"

# Premium models that should be blocked when over budget
PREMIUM_MODELS = frozenset({"gpt-4", "gpt-4-turbo", "claude-3-opus"})


@dataclass(frozen=True)
class BudgetPolicy:
    """
    Configuration for budget enforcement.

    Attributes:
        per_investigation_cap_cents: Maximum cost per investigation in cents.
        fallback_model: Model to use when premium exceeds budget.
        action_on_exceed: What to do when budget exceeded (BLOCK or FALLBACK).
    """
    per_investigation_cap_cents: MoneyCents = MoneyCents(30)  # $0.30 default
    fallback_model: str = DEFAULT_FALLBACK_MODEL
    action_on_exceed: BudgetAction = BudgetAction.FALLBACK


@dataclass(frozen=True)
class BudgetDecision:
    """
    Result of budget policy evaluation.

    Attributes:
        allowed: Whether the request should proceed.
        action: The action taken (ALLOW/BLOCK/FALLBACK).
        estimated_cost_cents: Estimated cost in cents.
        cap_cents: The budget cap in cents.
        resolved_model: The model to actually use.
        reason: Human-readable explanation.
    """
    allowed: bool
    action: BudgetAction
    estimated_cost_cents: MoneyCents
    cap_cents: MoneyCents
    resolved_model: str
    reason: str
    request_id: str


class BudgetPolicyEngine:
    """
    Engine for evaluating and enforcing LLM budget policy.

    This is the enforcement point that must be called before any
    LLM provider dispatch.
    """

    def __init__(self, policy: Optional[BudgetPolicy] = None):
        """Initialize with optional custom policy."""
        self.policy = policy or BudgetPolicy()

    def estimate_cost_cents(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> MoneyCents:
        """
        Estimate the cost of an LLM call in cents.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model identifier.

        Returns:
            Estimated cost in integer cents.
        """
        pricing = PRICING_CATALOG.get(model)
        if not pricing:
            # Unknown model, assume expensive for safety
            pricing = PRICING_CATALOG["gpt-4"]
            logger.warning(f"Unknown model {model}, using gpt-4 pricing for safety")

        # Calculate cost in USD with Decimal precision
        input_cost = (Decimal(input_tokens) / Decimal(1000)) * pricing.input_per_1k_usd
        output_cost = (Decimal(output_tokens) / Decimal(1000)) * pricing.output_per_1k_usd
        total_usd = input_cost + output_cost

        # Quantize to 4 decimal places then convert to cents
        total_usd = total_usd.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # Convert to cents (multiply by 100, round to int)
        cents = int((total_usd * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return MoneyCents(cents)

    def evaluate(
        self,
        requested_model: str,
        input_tokens: int,
        output_tokens: int,
        request_id: Optional[str] = None,
    ) -> BudgetDecision:
        """
        Evaluate a request against budget policy.

        This MUST be called before any LLM provider dispatch.

        Args:
            requested_model: The model requested by the caller.
            input_tokens: Estimated input tokens.
            output_tokens: Estimated output tokens.
            request_id: Optional request ID for tracing.

        Returns:
            BudgetDecision with action and resolved model.
        """
        request_id = request_id or str(uuid4())
        estimated_cents = self.estimate_cost_cents(input_tokens, output_tokens, requested_model)
        cap_cents = self.policy.per_investigation_cap_cents

        # Under budget: ALLOW
        if estimated_cents <= cap_cents:
            return BudgetDecision(
                allowed=True,
                action=BudgetAction.ALLOW,
                estimated_cost_cents=estimated_cents,
                cap_cents=cap_cents,
                resolved_model=requested_model,
                reason=f"Estimated cost {estimated_cents}¢ <= cap {cap_cents}¢",
                request_id=request_id,
            )

        # Over budget with non-premium model: ALLOW (can't get cheaper)
        if requested_model not in PREMIUM_MODELS:
            return BudgetDecision(
                allowed=True,
                action=BudgetAction.ALLOW,
                estimated_cost_cents=estimated_cents,
                cap_cents=cap_cents,
                resolved_model=requested_model,
                reason=f"Non-premium model {requested_model} allowed despite exceeding cap",
                request_id=request_id,
            )

        # Over budget with premium model: Apply policy action
        if self.policy.action_on_exceed == BudgetAction.BLOCK:
            return BudgetDecision(
                allowed=False,
                action=BudgetAction.BLOCK,
                estimated_cost_cents=estimated_cents,
                cap_cents=cap_cents,
                resolved_model=requested_model,  # Original, but won't be used
                reason=f"BLOCKED: Estimated cost {estimated_cents}¢ > cap {cap_cents}¢ for premium model {requested_model}",
                request_id=request_id,
            )

        # FALLBACK: Substitute cheaper model
        fallback_model = self.policy.fallback_model
        fallback_cost = self.estimate_cost_cents(input_tokens, output_tokens, fallback_model)

        return BudgetDecision(
            allowed=True,
            action=BudgetAction.FALLBACK,
            # IMPORTANT: Keep `estimated_cost_cents` as the cost of the *requested* model.
            # We may substitute a cheaper model, but the enforcement decision is based on
            # the premium estimate crossing the cap; this is what should be audited.
            estimated_cost_cents=estimated_cents,
            cap_cents=cap_cents,
            resolved_model=fallback_model,
            reason=(
                f"FALLBACK: {requested_model} -> {fallback_model} "
                f"(requested {estimated_cents}¢ > cap {cap_cents}¢; "
                f"fallback_estimate {fallback_cost}¢)"
            ),
            request_id=request_id,
        )

    async def evaluate_and_audit(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        user_id: UUID,
        requested_model: str,
        input_tokens: int,
        output_tokens: int,
        correlation_id: Optional[str] = None,
        prompt_fingerprint: Optional[str] = None,
    ) -> BudgetDecision:
        """
        Evaluate request and record decision in audit log.

        This is the preferred method for production use.

        Args:
            conn: Database connection.
            tenant_id: Tenant UUID for RLS.
            user_id: User UUID for per-user isolation.
            requested_model: The model requested.
            input_tokens: Estimated input tokens.
            output_tokens: Estimated output tokens.
            correlation_id: Optional correlation ID.

        Returns:
            BudgetDecision with action and resolved model.
        """
        decision = self.evaluate(
            requested_model=requested_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        # Record in audit log
        await self._record_audit(
            conn=conn,
            tenant_id=tenant_id,
            user_id=user_id,
            decision=decision,
            requested_model=requested_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            correlation_id=correlation_id,
            prompt_fingerprint=prompt_fingerprint,
        )

        logger.info(
            "budget_policy_decision",
            extra={
                "tenant_id": str(tenant_id),
                "request_id": decision.request_id,
                "requested_model": requested_model,
                "resolved_model": decision.resolved_model,
                "action": decision.action.value,
                "estimated_cost_cents": decision.estimated_cost_cents,
                "cap_cents": decision.cap_cents,
            },
        )

        return decision

    async def _record_audit(
        self,
        conn: AsyncConnection,
        tenant_id: UUID,
        user_id: UUID,
        decision: BudgetDecision,
        requested_model: str,
        input_tokens: int,
        output_tokens: int,
        correlation_id: Optional[str],
        prompt_fingerprint: Optional[str],
    ) -> None:
        """Record decision in llm_call_audit table."""
        if prompt_fingerprint:
            fingerprint = prompt_fingerprint
        else:
            fingerprint = hashlib.sha256(
                json.dumps(
                    {
                        "request_id": decision.request_id,
                        "requested_model": requested_model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        # RAW_SQL_ALLOWLIST: budget policy audit insert
        await conn.execute(
            text("""
                INSERT INTO llm_call_audit (
                    tenant_id, user_id, request_id, correlation_id,
                    requested_model, resolved_model,
                    estimated_cost_cents, cap_cents,
                    decision, reason,
                    input_tokens, output_tokens,
                    prompt_fingerprint
                ) VALUES (
                    :tenant_id, :user_id, :request_id, :correlation_id,
                    :requested_model, :resolved_model,
                    :estimated_cost_cents, :cap_cents,
                    :decision, :reason,
                    :input_tokens, :output_tokens,
                    :prompt_fingerprint
                )
            """),
            {
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "request_id": decision.request_id,
                "correlation_id": correlation_id,
                "requested_model": requested_model,
                "resolved_model": decision.resolved_model,
                "estimated_cost_cents": decision.estimated_cost_cents,
                "cap_cents": decision.cap_cents,
                "decision": decision.action.value,
                "reason": decision.reason,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "prompt_fingerprint": fingerprint,
            },
        )

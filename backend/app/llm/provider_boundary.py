"""
Provider boundary for future LLM integrations (B0.7-P0).

This module is intentionally stub-only:
- It MUST NOT call any external LLM provider.
- It provides a single choke-point API for future provider normalization and
  enforcement (timeouts, breakers, cost tracking, caching).

Non-vacuous guarantee:
- The boundary is imported by the LLM worker layer (see app.workers.llm).
- Unit tests exercise stub behavior so enforcement cannot pass "because nothing exists".
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderBoundaryResult:
    """
    Deterministic stub result for the provider boundary.

    This shape is intentionally minimal and stable; it is used only to prove
    the boundary exists and is callable without introducing provider traffic.
    """

    provider: str
    model: str
    output_text: str
    reasoning_trace: str | None
    usage: Mapping[str, int]


class SkeldirLLMProviderBoundary:
    """
    Stub boundary interface.

    Future implementations will wrap aisuite (mandatory per B0.7 intent) behind
    this boundary, but B0.7-P0 must remain provider-free.
    """

    boundary_id = "b07_p0_stub"

    def complete(self, *, prompt: Mapping[str, Any], max_cost_cents: int) -> ProviderBoundaryResult:
        _ = (prompt, max_cost_cents)
        return ProviderBoundaryResult(
            provider="stub",
            model="stub",
            output_text="stubbed",
            reasoning_trace=None,
            usage={"input_tokens": 0, "output_tokens": 0, "cost_cents": 0, "latency_ms": 0},
        )


def get_llm_provider_boundary() -> SkeldirLLMProviderBoundary:
    return SkeldirLLMProviderBoundary()

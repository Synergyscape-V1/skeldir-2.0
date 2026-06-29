"""Explicit unavailable benchmark metadata for B2.5-P5."""

from __future__ import annotations


def unavailable_benchmark_metadata() -> dict[str, object]:
    """Return honest benchmark metadata until B2.10A owns benchmark authority."""
    return {
        "benchmark_status": "unavailable",
        "benchmark_authority": "explicitly_unavailable",
        "benchmark_ref": None,
        "benchmark_hash": None,
        "unavailable_reason": "benchmark_source_not_configured",
    }

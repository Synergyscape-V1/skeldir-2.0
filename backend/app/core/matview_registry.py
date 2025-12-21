"""
Canonical materialized view registry.

This module defines the authoritative list of matviews managed by the system.
All refresh operations MUST use this registry.

B0.5.4.0: Centralized registry to close H-C drift (hardcoded list mismatch).
EG-2: Removed deprecated views (mv_realtime_revenue, mv_reconciliation_status)
      dropped by migration 202511171400 (superseded by canonical views).
"""
from typing import List


# Canonical matview list - MUST match pg_matviews in target DB.
# B0.5.4.0 contract: 5 canonical matviews.
MATERIALIZED_VIEWS: List[str] = [
    "mv_allocation_summary",
    "mv_channel_performance",
    "mv_daily_revenue_summary",
    "mv_realtime_revenue",
    "mv_reconciliation_status",
]


def get_all_matviews() -> List[str]:
    """
    Return canonical list of all managed materialized views.

    This is the single source of truth for matview inventory.
    Tests MUST assert this list matches actual pg_matviews in DB.

    Returns:
        List of materialized view names
    """
    return MATERIALIZED_VIEWS.copy()


def validate_matview_name(view_name: str) -> bool:
    """
    Validate that a matview name is in the canonical registry.

    Args:
        view_name: Name of materialized view to check

    Returns:
        True if view_name is in registry, False otherwise
    """
    return view_name in MATERIALIZED_VIEWS

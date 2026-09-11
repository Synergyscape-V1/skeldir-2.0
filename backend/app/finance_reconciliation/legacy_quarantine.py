"""B2.6-P1 legacy reconciliation quarantine record (authority infrastructure).

The legacy reconciliation surfaces below remain mounted in the production
application for contract compatibility only. They are explicitly
non-authoritative: no canonical B2.6 financial consumer may derive truth
from them through import, dynamic load, helper, database relation, or
network/service invocation. Canonical verification coverage is obtained
solely by resolving scope through
``app.finance_reconciliation.coverage_authority.resolve_canonical_coverage``,
which re-derives truth from the sovereign B2.3 source. Caller-supplied
observations -- including legacy values wrapped in the current DTO shape --
are always refused by the fail-closed admission shim.

This module declares quarantine facts. It performs no network fetch and
mints no canonical value, so declaration here can never become authority.
"""

from __future__ import annotations

from typing import Any, Mapping


LEGACY_QUARANTINE_STATUS = "compatibility_only_non_authoritative"
LEGACY_NON_AUTHORITATIVE_ROUTE_PATHS = frozenset(
    {
        "/api/reconciliation/status",
        "/api/reconciliation/platform/{platform_id}",
        "/api/reconciliation/sync",
    }
)
LEGACY_NON_AUTHORITATIVE_MODULES = frozenset(
    {
        "app.services.revenue_reconciliation",
        "app.api.reconciliation",
        "app.api.export",
    }
)
LEGACY_NON_AUTHORITATIVE_RELATIONS = frozenset(
    {
        "public.revenue_ledger",
        "public.reconciliation_runs",
    }
)
LEGACY_QUARANTINE_ENFORCEMENT = (
    "app.finance_reconciliation.legacy_quarantine"
    "+app.finance_reconciliation.coverage_authority."
    "admit_canonical_verification_coverage"
    "+static_capability_fences"
)
LEGACY_QUARANTINE_NOTE = (
    "Legacy reconciliation output is visible only as an explicitly "
    "non-authoritative compatibility diagnostic. It cannot enter canonical "
    "B2.6 financial truth through any direct, indirect, dynamic, database, "
    "or network path."
)


class LegacyAuthorityError(ValueError):
    """A legacy reconciliation origin was presented where authority is required."""


def refuse_legacy_as_canonical(candidate: Any) -> Any:
    """Refuse any legacy reconciliation value offered as canonical truth."""
    raise LegacyAuthorityError(
        "legacy_reconciliation_output_cannot_become_canonical_B2.6_truth"
    )


def mark_legacy_diagnostic(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Wrap a legacy payload as explicitly non-authoritative diagnostic data."""
    return {
        "authority": "non_authoritative_legacy_diagnostic",
        "quarantine_status": LEGACY_QUARANTINE_STATUS,
        "payload": dict(payload),
    }


def is_canonical_b26_authority(candidate: Any) -> bool:
    """Report whether a value already carries sealed canonical authority.

    Corrective IV removed transferable canonical tokens: no in-memory object
    carries authority by itself, so this helper always reports False. The
    only canonical values are fresh return values of the sovereign resolver
    in the execution that performed the sovereign read; every other value --
    including resolver copies, diagnostic rebuilds, and legacy wrappers --
    is structurally non-canonical. Sinks must resolve scope rather than
    inspecting object identity.
    """
    return False

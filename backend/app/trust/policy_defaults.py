"""Conservative B2.5-P5 policy authority defaults."""

from __future__ import annotations


FORBIDDEN_ACTION_SCOPES: tuple[str, ...] = (
    "trust.action.execute",
    "trust.policy.override",
    "trust.envelope.mutate",
)


def read_only_policy_authority(
    allowed_scopes: tuple[str, ...] = ("trust.envelope.read", "trust.envelope.verify"),
) -> dict[str, object]:
    """Return the only P5 policy authority state allowed for unsigned builds."""
    return {
        "policy_state": "read_only",
        "allowed_scopes": list(allowed_scopes),
        "forbidden_scopes": list(FORBIDDEN_ACTION_SCOPES),
        "reason_code": "p1_contract_boundary_only",
    }

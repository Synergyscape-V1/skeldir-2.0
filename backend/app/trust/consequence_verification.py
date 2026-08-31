"""Public-key adjudication of a durably retained signing consequence.

Corrective XVII requires that durable completion project ``issued`` only from an
artifact that actually verifies, and that recovery promote a stale
``signature_known`` row only on the same terms. That adjudication is neither
provenance auditing nor signing: it is the consequence boundary deciding
whether durable evidence is admissible, using public key material only.

It lives in its own module so that ``app.trust.audit`` keeps the phase
isolation its own gate enforces and depends on one narrow, named capability
rather than on the verification surface as a whole. Nothing here holds, reads,
or can reach private key material.
"""

from __future__ import annotations

from typing import Any

from app.trust.key_registry import TrustKeyRegistry
from app.trust.runtime_keys import (
    RuntimeTrustKeyConfigurationError,
    load_runtime_verification_registry,
)
from app.trust.verification import verify_trust_envelope


class RetainedConsequenceUnverifiable(RuntimeError):
    """No public authority available could adjudicate the retained artifact."""


def adjudicate_retained_consequence(
    artifact: dict[str, Any],
    *,
    supplied_registry: TrustKeyRegistry | None = None,
) -> tuple[bool, str]:
    """Return whether a retained artifact verifies, and the deciding reason.

    A caller-supplied registry is consulted first so that a process which
    already holds the relevant public material does not depend on the runtime
    registry being configured. The process-wide public verification authority is
    consulted second, and only as a second authority: resolving it eagerly would
    turn "no public verification authority configured" into "issuance is
    impossible" for every caller that supplied its own key material.
    """
    registries: list[TrustKeyRegistry] = []
    if supplied_registry is not None:
        registries.append(supplied_registry.public_only())
    try:
        registries.append(load_runtime_verification_registry().public_only())
    except RuntimeTrustKeyConfigurationError as exc:
        if not registries:
            raise RetainedConsequenceUnverifiable(
                "retained_consequence_verification_authority_unavailable"
            ) from exc

    reason = "no_registry"
    for registry in registries:
        result = verify_trust_envelope(artifact, key_registry=registry)
        reason = str(result.reason_code)
        if result.verification_status == "verified":
            return True, reason
    return False, reason

"""Closure-private custody for signer-produced TrustEnvelope consequences.

B2.5-P13 Corrective XVII requires durable completion to consume evidence that
can only be minted by the governed Ed25519 signer.  A signed-looking ``dict`` is
not that evidence: any caller can construct one.  This module therefore keeps
the signed artifact and its tenant/attempt binding in a closure-private ledger
and exposes only an opaque random handle.

The handle is minted by :mod:`app.trust.signing` after the private-key call
returns and redeemed by :mod:`app.trust.audit` immediately before the signer
principal persists the exact artifact.  Callers cannot author or transplant
the material because it never travels on the handle.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import secrets
import sys
from typing import Any, Callable
from uuid import UUID


class SigningConsequenceError(RuntimeError):
    """Raised when consequence custody is used outside its trusted boundary."""


@dataclass(frozen=True)
class SigningConsequenceMaterial:
    """Exact physical result of one governed signing attempt."""

    tenant_id: UUID
    audit_ref: str
    attempt_id: UUID
    signed_envelope: dict[str, Any]


class SignedTrustEnvelopeConsequence:
    """Opaque single-use reference to a signer-produced artifact."""

    __slots__ = ("_handle",)

    def __init__(self, handle: str) -> None:
        self._handle = handle


_HANDLE_BYTES = 32
_MINT_MODULE = "app.trust.signing"
_REDEEM_MODULE = "app.trust.audit"


def _calling_module(depth: int) -> str:
    try:
        frame = sys._getframe(depth)
    except ValueError as exc:  # pragma: no cover - defensive
        raise SigningConsequenceError("signing_consequence_caller_unknown") from exc
    name = frame.f_globals.get("__name__")
    return name if isinstance(name, str) else ""


def _assert_caller(expected: str, operation: str) -> None:
    caller = _calling_module(3)
    if caller != expected:
        raise SigningConsequenceError(
            f"signing_consequence_untrusted_caller:{operation}:{caller or 'unknown'}"
        )


def _new_ledger() -> tuple[
    Callable[[SigningConsequenceMaterial], SignedTrustEnvelopeConsequence],
    Callable[[object], SigningConsequenceMaterial],
]:
    entries: dict[str, SigningConsequenceMaterial] = {}

    def mint(material: SigningConsequenceMaterial) -> SignedTrustEnvelopeConsequence:
        _assert_caller(_MINT_MODULE, "mint")
        if not isinstance(material, SigningConsequenceMaterial):
            raise SigningConsequenceError("signing_consequence_material_invalid")
        handle = secrets.token_urlsafe(_HANDLE_BYTES)
        entries[handle] = SigningConsequenceMaterial(
            tenant_id=material.tenant_id,
            audit_ref=material.audit_ref,
            attempt_id=material.attempt_id,
            signed_envelope=deepcopy(material.signed_envelope),
        )
        return SignedTrustEnvelopeConsequence(handle)

    def redeem(capability: object) -> SigningConsequenceMaterial:
        _assert_caller(_REDEEM_MODULE, "redeem")
        handle = getattr(capability, "_handle", None)
        if not isinstance(capability, SignedTrustEnvelopeConsequence) or not isinstance(
            handle, str
        ):
            raise SigningConsequenceError("signing_consequence_capability_required")
        material = entries.pop(handle, None)
        if material is None:
            raise SigningConsequenceError("signing_consequence_handle_unknown")
        return material

    return mint, redeem


mint_signing_consequence, redeem_signing_consequence = _new_ledger()

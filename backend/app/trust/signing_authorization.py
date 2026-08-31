"""Opaque custody for a durable, tenant-bound permission to sign.

The public API cannot transfer the process-local P5 authority capability to a
separate signer process.  The signer therefore re-establishes authority from
PostgreSQL: the exact unsigned envelope must match the durable P7 audit row and
the requested attempt must be the current ``signing`` attempt.  This module
keeps that validated material closure-private between ``audit`` and ``signing``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import secrets
import sys
from typing import Any, Callable
from uuid import UUID


class DurableSigningAuthorizationError(RuntimeError):
    """Raised when durable signing authority crosses an untrusted seam."""


@dataclass(frozen=True)
class DurableSigningAuthorizationMaterial:
    """Exact P7-authorized claim and its current attempt identity."""

    tenant_id: UUID
    audit_ref: str
    attempt_id: UUID
    unsigned_envelope: dict[str, Any]


class DurableSigningAuthorization:
    """Opaque single-use reference to validated durable signing authority."""

    __slots__ = ("_handle",)

    def __init__(self, handle: str) -> None:
        self._handle = handle


def _calling_module(depth: int) -> str:
    try:
        frame = sys._getframe(depth)
    except ValueError as exc:  # pragma: no cover - defensive
        raise DurableSigningAuthorizationError(
            "durable_signing_authorization_caller_unknown"
        ) from exc
    name = frame.f_globals.get("__name__")
    return name if isinstance(name, str) else ""


def _assert_caller(expected: str, operation: str) -> None:
    caller = _calling_module(3)
    if caller != expected:
        raise DurableSigningAuthorizationError(
            "durable_signing_authorization_untrusted_caller:"
            f"{operation}:{caller or 'unknown'}"
        )


def _new_ledger() -> tuple[
    Callable[[DurableSigningAuthorizationMaterial], DurableSigningAuthorization],
    Callable[[object], DurableSigningAuthorizationMaterial],
]:
    entries: dict[str, DurableSigningAuthorizationMaterial] = {}

    def mint(
        material: DurableSigningAuthorizationMaterial,
    ) -> DurableSigningAuthorization:
        _assert_caller("app.trust.audit", "mint")
        if not isinstance(material, DurableSigningAuthorizationMaterial):
            raise DurableSigningAuthorizationError(
                "durable_signing_authorization_material_invalid"
            )
        handle = secrets.token_urlsafe(32)
        entries[handle] = DurableSigningAuthorizationMaterial(
            tenant_id=material.tenant_id,
            audit_ref=material.audit_ref,
            attempt_id=material.attempt_id,
            unsigned_envelope=deepcopy(material.unsigned_envelope),
        )
        return DurableSigningAuthorization(handle)

    def redeem(capability: object) -> DurableSigningAuthorizationMaterial:
        _assert_caller("app.trust.signing", "redeem")
        handle = getattr(capability, "_handle", None)
        if not isinstance(capability, DurableSigningAuthorization) or not isinstance(
            handle, str
        ):
            raise DurableSigningAuthorizationError(
                "durable_signing_authorization_capability_required"
            )
        material = entries.pop(handle, None)
        if material is None:
            raise DurableSigningAuthorizationError(
                "durable_signing_authorization_handle_unknown"
            )
        return material

    return mint, redeem


mint_durable_signing_authorization, redeem_durable_signing_authorization = _new_ledger()

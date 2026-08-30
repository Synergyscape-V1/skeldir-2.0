"""Closure-private provenance ledger for P5 witness and P8 issuance authority.

B2.5-P13 Corrective XV, H-XV-01.

Before this module the two trust capabilities -- ``TrustEnvelopeBuildWitness``
and ``AuthorizedTrustEnvelope`` -- were "sealed" by comparing an attribute
against a module-level ``object()``. That is not a boundary. ``_CAPABILITY_SEAL``
was importable, and ``getattr(donor, "_seal")`` retrieved it from any instance,
so arbitrary same-process code could mint a capability over a payload it wrote
itself and obtain a real Ed25519 signature over fabricated money. That was
demonstrated, not theorised: three independent constructions (direct
constructor, ``object.__new__`` + ``object.__setattr__``, and seal transplant)
each produced a publicly verifiable envelope carrying revenue no tenant earned.

The replacement rests on two physical properties rather than on naming
convention:

1. **The authoritative bytes never travel with the handle.** Minting stores the
   canonical payload in a table held in a closure cell. The handle is a 256-bit
   random string. Redemption returns the *stored* bytes, so a fabricated or
   transplanted handle cannot smuggle a payload: there is nothing in the object
   for an attacker to author.
2. **Minting and redeeming are restricted to a declared trusted computing
   base.** Each entry point checks the calling module against
   ``TRUSTED_ISSUANCE_MODULES``. The check reads the *direct* caller, which is
   always the trust module itself even when the work is hopped onto a worker
   thread by ``asyncio.to_thread``.

Capability handles are single-use, which also gives issuance a physical
anti-replay property: one mint redeems exactly once.

Threat model -- stated plainly rather than overclaimed
-----------------------------------------------------
This boundary is inescapable for every *production-reachable caller outside the
declared TCB*: constructors, aliases, wrappers, dynamic imports, ``getattr``,
reflection over instances, module reload, serialization/reconstruction,
``copy``/``deepcopy``, ``object.__new__``, ``object.__setattr__``, monkeypatch
substitution, alternate factories, sibling signers and dynamic dispatch all
fail closed, because none of them can produce a handle the ledger issued.

It is **not** a defence against code that walks interpreter internals --
``function.__closure__[i].cell_contents``, ``gc.get_objects()``, frame
manipulation, or C-level memory access. That exclusion is honest rather than
convenient: such code can read the Ed25519 private key straight out of
``TrustKeyRegistry`` and sign whatever it likes, so no capability design
expressible in CPython can defend against it. Code with that reach is inside
the TCB by construction. See
``docs/security/b25_p13_c15_trusted_computing_base.md``.
"""

from __future__ import annotations

import secrets
import sys
from typing import Callable


class IssuanceAuthorityLedgerError(RuntimeError):
    """Raised when issuance authority is minted or redeemed outside the TCB."""


# The only modules permitted to mint or redeem TrustEnvelope issuance authority.
# Any other caller -- production, test, or adversarial -- fails closed.
TRUSTED_ISSUANCE_MODULES = frozenset(
    {
        "app.trust.builder",
        "app.trust.semantic_authority",
        "app.trust.signing",
    }
)

_HANDLE_BYTES = 32


def _calling_module(depth: int) -> str:
    """Return the module name of the frame ``depth`` levels above this helper."""

    try:
        frame = sys._getframe(depth)
    except ValueError as exc:  # pragma: no cover - stack shorter than expected
        raise IssuanceAuthorityLedgerError("issuance_authority_caller_unknown") from exc
    name = frame.f_globals.get("__name__")
    return name if isinstance(name, str) else ""


def _assert_trusted_caller(operation: str, depth: int) -> None:
    # +2 skips this helper and ``_calling_module`` itself, so ``depth=1`` names
    # the module that called ``mint``/``redeem`` rather than the ledger.
    caller = _calling_module(depth + 2)
    if caller not in TRUSTED_ISSUANCE_MODULES:
        raise IssuanceAuthorityLedgerError(
            f"issuance_authority_untrusted_caller:{operation}:{caller or 'unknown'}"
        )


def _new_ledger(label: str) -> tuple[Callable[..., str], Callable[..., bytes]]:
    """Build a mint/redeem pair over a table reachable only through them.

    ``entries`` is a closure cell. It is deliberately not a module attribute,
    so importing this module yields no way to add an entry.
    """

    entries: dict[str, bytes] = {}

    def mint(material: bytes) -> str:
        _assert_trusted_caller(f"mint:{label}", 1)
        if not isinstance(material, bytes) or not material:
            raise IssuanceAuthorityLedgerError(f"issuance_authority_material:{label}")
        handle = secrets.token_urlsafe(_HANDLE_BYTES)
        entries[handle] = material
        return handle

    def redeem(handle: object, *, consume: bool) -> bytes:
        _assert_trusted_caller(f"redeem:{label}", 1)
        if not isinstance(handle, str):
            raise IssuanceAuthorityLedgerError(
                f"issuance_authority_handle_invalid:{label}"
            )
        material = entries.pop(handle, None) if consume else entries.get(handle)
        if material is None:
            raise IssuanceAuthorityLedgerError(
                f"issuance_authority_handle_unknown:{label}"
            )
        return material

    return mint, redeem


mint_build_witness_authority, redeem_build_witness_authority = _new_ledger("witness")
mint_issuance_capability, redeem_issuance_capability = _new_ledger("capability")

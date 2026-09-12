"""B2.6-P1 candidate-bound proof manifest (Corrective VI).

Defect class closed here
------------------------

Representation-as-proof. A required runtime proof was a non-empty string:
``("FAKE",)``, ``("V-999",)``, duplicate, and foreign proof identifiers all
registered, and an implementation swap preserving the strings kept
authorization. The strings attested nothing about any candidate, tree,
executable, contract, or lifecycle outcome.

Class-closure theorem
---------------------

A proof identifier binds a real candidate proof only through the conjunction
of three independently observable facts, all re-verified on every canonical
execution:

1. **Manifest membership.** The identifier is a member of the governed
   required set for the exact sink and contract version named here. Unknown,
   empty, malformed, and denylisted identifiers are refused at registration
   time -- they can never reach an authorizer.
2. **Executable binding.** The sink registration carries the SHA-256 of the
   implementation source that was reviewed for this candidate. Every
   canonical execution re-hashes the live implementation and refuses on
   divergence, so a stale proof from a different executable cannot authorize
   a replaced implementation.
3. **Candidate binding.** The CI proof plane adjudicates the exact
   candidate SHA/tree (``adjudicate_b26_p1_proof_plane``); merge-group
   adjudication plus landed-artifact equivalence extend that binding to the
   protected main tree. The manifest records the contract version so a proof
   minted under a different semantic authority is refused even when its
   characters match.

What this module does NOT do
----------------------------

It does not fetch CI artifacts at runtime (the canonical path has no
network capability and must not gain one). The runtime half of the binding
is (1) + (2) + contract-version equality; the CI half is the existing
proof-plane adjudication of the exact candidate. Either half failing closed
refuses authorization.

Sovereign sources composed (never reimplemented)
------------------------------------------------

* The governed sink set is the contract's ``future_insertion_seam``
  (observed through ``coverage_authority.GOVERNED_CANONICAL_SINK_NAMES``).
* The contract version is ``semantic_contract.B26_P1_CONTRACT_VERSION``.
* Implementation hashing uses ``hashlib``/``inspect`` over the reviewed
  source; the hash is an observation of the artifact that will run.
"""

from __future__ import annotations

import re
from typing import Iterable


B26_P1_PROOF_MANIFEST_VERSION = "b2.6-p1-proof-manifest-v1"

# Proof identifiers that independent falsification has shown to be accepted
# by string-only checks. Membership in this set is always refused, even if
# a future required set were to name a colliding string.
DENYLISTED_PROOF_IDS = frozenset(
    {
        "FAKE",
        "FAKE-PROOF",
        "V-999",
        "V-0",
        "VI-0",
        "anything",
        "test",
        "probe",
    }
)

# Identifiers admitted as candidate-bound proof references: Corrective-V
# consequence cells (``V-N``) and Corrective-VI consequence cells (``VI-N``),
# optionally suffixed for sub-directions (for example ``VI-6-DDL``).
_PROOF_ID_PATTERN = re.compile(r"^(V|VI)-[1-9][0-9]*(?:-[A-Z0-9]+)*$")

# Governed required proof set per canonical sink for the current contract
# version. Every governed sink's registration must carry exactly this set:
# a missing proof is an incomplete claim, an extra proof is an ungoverned
# claim, and any other string is a forgery.
REQUIRED_SINK_PROOFS: dict[str, tuple[str, ...]] = {
    "future_B2.6_deterministic_reconciliation_projection_boundary": (
        "V-2",
        "V-3",
        "V-4",
    ),
    "future_finance_projection": ("V-2", "V-3", "V-4"),
    "future_B2.6_TrustEnvelope_projection": ("V-2", "V-3", "V-4"),
}


class ProofBindingError(ValueError):
    """A proof identifier does not bind a real candidate proof."""


def is_wellformed_proof_id(proof_id: str) -> bool:
    """Report whether a proof identifier is well-formed and not denylisted."""
    if not isinstance(proof_id, str):
        return False
    candidate = proof_id.strip()
    if not candidate or candidate != proof_id:
        return False
    if candidate in DENYLISTED_PROOF_IDS:
        return False
    return _PROOF_ID_PATTERN.match(candidate) is not None


def required_proofs_for_sink(sink_id: str) -> tuple[str, ...]:
    """Return the governed required proof set for a canonical sink."""
    required = REQUIRED_SINK_PROOFS.get(str(sink_id))
    if required is None:
        raise ProofBindingError(f"proof_manifest_unknown_sink:{sink_id}")
    return required


def require_proofs_bound(
    *,
    sink_id: str,
    required_runtime_proof_ids: Iterable[str],
    contract_version: str,
) -> tuple[str, ...]:
    """Require candidate-bound proofs for a sink registration.

    Refuses: unknown sinks, empty proof sets, malformed or denylisted
    identifiers, any set other than the governed required set, and any
    contract version other than the live semantic authority. Returns the
    bound proof tuple on success.
    """
    from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
        B26_P1_CONTRACT_VERSION,
    )

    required = required_proofs_for_sink(sink_id)
    proofs = tuple(required_runtime_proof_ids)
    if not proofs:
        raise ProofBindingError(
            f"proof_manifest_requires_runtime_proofs:{sink_id}"
        )
    for proof_id in proofs:
        if not is_wellformed_proof_id(proof_id):
            raise ProofBindingError(
                f"proof_manifest_proof_not_bound:{sink_id}:{proof_id}"
            )
    if tuple(proofs) != tuple(required):
        raise ProofBindingError(
            f"proof_manifest_required_set_mismatch:{sink_id}:"
            f"required={','.join(required)}"
        )
    if contract_version != B26_P1_CONTRACT_VERSION:
        raise ProofBindingError(
            f"proof_manifest_contract_version_mismatch:{sink_id}:{contract_version}"
        )
    return tuple(proofs)


def require_successor_proofs_bound(
    *,
    registration_id: str,
    required_runtime_proof_ids: Iterable[str],
) -> tuple[str, ...]:
    """Require well-formed, non-denylisted proofs for a successor declaration.

    Successor declarations reference Corrective-VI proof cells; the bar at
    declaration time is well-formedness plus denylist refusal. Durable
    authorization additionally requires P2 migration-backed binding (see
    :func:`canonical_sink.authorize_successor_persistence`), so a
    well-formed declaration alone authorizes nothing durable.
    """
    proofs = tuple(required_runtime_proof_ids)
    if not proofs:
        raise ProofBindingError(
            f"proof_manifest_successor_requires_runtime_proofs:{registration_id}"
        )
    for proof_id in proofs:
        if not is_wellformed_proof_id(proof_id):
            raise ProofBindingError(
                f"proof_manifest_successor_proof_not_bound:{registration_id}:{proof_id}"
            )
    return tuple(proofs)

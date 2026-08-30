# B2.5-P13 C15 — TrustEnvelope Issuance: Trusted Computing Base and Threat Model

Corrective Action XV, H-XV-01 / RC-XV-01.

This document exists because the previous position was never written down, and
an unwritten boundary turned out to be no boundary at all.

## What was actually true before

`AuthorizedTrustEnvelope` was described as the capability that made raw
caller-authored payloads ineligible for TrustEnvelope signing. In practice it
proved only that its holder had read the module. Three constructions, each a
few lines long, minted a valid capability over a payload the attacker wrote
themselves — carrying `verified_revenue_minor = 999999999`, money no tenant
earned — obtained a real Ed25519 signature, and passed public verification:

1. calling the dataclass constructor with the importable `_CAPABILITY_SEAL`;
2. `object.__new__` plus `object.__setattr__`, bypassing the constructor;
3. transplanting the seal off a donor instance with `getattr`.

The root cause was not a missing check. It was that `authority_proof_hash` was
a hash of the very bytes the holder supplied, so the "proof" was a statement
about self-consistency rather than about provenance, and both the seal and the
hash function were module-level importables.

## Trusted computing base

Exactly two modules may mint or redeem TrustEnvelope issuance authority. The
list is enforced in code at
`backend/app/trust/issuance_authority_ledger.py::TRUSTED_ISSUANCE_MODULES`, and
pinned by test, so it cannot drift silently:

| Module | Authority |
|---|---|
| `app.trust.builder` | Mints the P5 build witness from authoritative tenant-scoped rows |
| `app.trust.semantic_authority` | Mints the P7-authorised issuance capability after full semantic correspondence and redeems it when the signer invokes the capability's private payload resolver |

Two physical properties, not naming conventions, carry the boundary:

1. **The authoritative bytes never travel with the handle.** Minting stores the
   canonical payload in a table held in a closure cell; the handle is a 256-bit
   random string; redemption returns the *stored* bytes. A fabricated or
   transplanted handle has no payload to smuggle, because the object carries
   none.
2. **Mint and redeem check the calling module.** The check reads the direct
   caller, which remains the trust module itself even when work is hopped onto a
   worker thread by `asyncio.to_thread`.

Capability handles are single-use, so one authorised mint is redeemable exactly
once. That is also the anti-replay property behind one-logical-issuance /
one-lineage.

## Database-layer issuance authority (Corrective XVI)

The application-layer TCB above governs who may *mint and redeem* signing
authority in-process. It cannot govern who may *assert, in durable history*,
that a signature happened, because that assertion is a database write and any
holder of the application's database credentials can attempt one.

Corrective XVI therefore adds a second, independent boundary at the database:

| Principal | Issuance-consequence authority |
|---|---|
| `app_user` (API, generic workers) | None. Every transition into or out of a consequence-bearing state, and every write of crypto evidence or lineage counters, raises `trust_issuance_authority_violation`. |
| `app_worker`, `app_dispatch_publisher` | None, by the same guard. |
| `app_trust_issuer` | May perform legal transitions only, and remains bound by the transition graph, terminal immutability, tenant binding, monotonic lineage, and the evidence CHECK constraints. It holds no INSERT privilege. |
| `migration_owner` (schema owner) | Migration authority, which is out of runtime scope by definition. |

The guard keys on `session_user`, not `current_user`, so membership and
`SET ROLE` cannot reach it: obtaining issuance authority requires a separate
login with a separate credential.

## Inside the threat model

Every production-reachable caller outside the two modules above. All of the
following fail closed, and each is exercised as a negative control in
`backend/tests/trust/test_b25_p13_c15_issuance_truth.py`:

constructor access, aliases, wrappers, dynamic imports, `getattr`, reflection
over instances, module reload, serialization and reconstruction, `copy` and
`deepcopy`, `object.__new__`, `object.__setattr__`, monkeypatch-style
substitution, alternate factories, sibling signers, dynamic dispatch, and
direct calls into the ledger from an untrusted module.

## Outside the threat model

Code that walks interpreter internals: `function.__closure__[i].cell_contents`,
`gc.get_objects()`, frame manipulation, `ctypes`, or any C-level memory access.

This exclusion is stated because it is true, not because it is convenient. Such
code can read the Ed25519 private key straight out of `TrustKeyRegistry` and
sign whatever it likes, so **no capability design expressible in CPython can
defend against it**. An attacker with that reach has already won by a shorter
route than forging a capability. Code with that level of access is inside the
TCB by construction.

The practical consequence for deployment: the security of TrustEnvelope
issuance depends on controlling *what code runs inside the API process*. It does
not depend on, and must not be described as depending on, Python's underscore
prefixes or module privacy — those are documentation, not enforcement.

## What would invalidate this document

* Adding a module to `TRUSTED_ISSUANCE_MODULES` without a recorded reason.
* Re-introducing a payload field on `AuthorizedTrustEnvelope` or
  `TrustEnvelopeBuildWitness`, which would restore the transplant surface.
* Any new call site for `sign_trust_envelope` outside the inventory pinned by
  `scripts/ci/validate_b25_p13_c14_closure.py`.
* Making capability redemption non-consuming, which would restore replay.

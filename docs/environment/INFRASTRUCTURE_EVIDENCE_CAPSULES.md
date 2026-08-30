# Infrastructure Evidence Capsules

B2.5-P13 Corrective XV, Exit Gate D / RC-XV-05.

An infrastructure result may be reused across audits **only** when a capsule
records what made it true and the current audit target is mechanically compared
against those inputs. This file is that ledger.

Reusing a topology result without this comparison is one of the directive's
automatic failure conditions:

> a relevant infrastructure topology change reuses stale `PASS-INFRASTRUCTURE`
> evidence

## What a capsule is not

`PASS-INFRASTRUCTURE` does **not** mean current semantics are correct, and it
does **not** mean the documented local developer experience works. Semantic
change requires fresh `PASS-SEMANTIC-FALSIFICATION`; local workflow claims
require fresh `PASS-LOCAL-REPRODUCIBILITY`. A capsule can never be used to
answer either question. See `SUPPORTED_ENVIRONMENTS.md`.

## Carry-forward rule

```text
capsule causal inputs unchanged   -> PASS-INFRASTRUCTURE — CARRIED, DIFF-CONFIRMED
any relevant input changed        -> CAPSULE INVALIDATED — fresh validation required
```

The comparison is mechanical: recompute the hashes in the capsule's *causal
inputs* table and diff them against the recorded values. A capsule whose inputs
cannot be recomputed is invalid, not "probably fine".

---

## IEC-XV-01 — PostgreSQL 15 least-privilege topology and migration chain

| Field | Value |
|---|---|
| Evidence ID | `IEC-XV-01` |
| Original validated SHA | `0941d3599680b6317638bad69a4b0c44d0e365fa` (+ Corrective XV working tree) |
| Validated property | A PostgreSQL 15 database provisioned by `prepare_migration_authority_boundary.py` reaches Alembic head with six non-superuser, non-RLS-bypassing roles |
| Runtime result | PostgreSQL 15.19; `alembic upgrade head` -> `202608291200`; six roles present, every `rolsuper=false` and `rolbypassrls=false` |
| Negative controls used | Runtime identity asserted **not** to bypass RLS (a superuser connection would make tenant-isolation journeys pass for the wrong reason); first real-fit attempt as `app_user` must fail with `permission denied for table bayesian_model_fits` before `app_worker` succeeds |
| External mutable dependencies | Docker Hub `postgres:15-alpine` tag |
| Validated | 2026-08-29, Corrective XV |

### Causal inputs

| Input | Value |
|---|---|
| PostgreSQL image digest | `sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b` |
| Reported server version | `PostgreSQL 15.19 on x86_64-pc-linux-musl` |
| Alembic head revision | `202608291200` |
| Migration chain hash | `0eb23c997c2d9c143d1677a6b0bb6837cdf2721aebd907205141b7ccd630452a` |
| `scripts/database/prepare_migration_authority_boundary.py` | `82f56e211f578f27a5f2142fbc4a83fc2d494bef6951bb9fa46ce0bb7ece4868` |
| `.github/actions/setup-postgres-ci/action.yml` | `e003992e5d026e6f9447a4cbf687c520182dfd9ac7b2f710dc8605b2c72f283e` |

### Invalidation conditions

* The PostgreSQL major version or image digest changes.
* Any file under `alembic/versions/` is added, removed, or modified (migration
  chain hash changes).
* `prepare_migration_authority_boundary.py` or the setup action changes.
* The runtime role set, or any role's `rolsuper` / `rolbypassrls`, changes.

**This capsule was invalidated and re-validated during Corrective XV**, because
`202608291200_b25_p13_c15_issuance_completion_state.py` changed the migration
chain hash. That is the rule working, not an exception to it.

---

## IEC-XV-02 — Compose topology surfaces

| Field | Value |
|---|---|
| Evidence ID | `IEC-XV-02` |
| Validated property | The declared Compose surfaces resolve and declare the services `SUPPORTED_ENVIRONMENTS.md` attributes to them |
| Runtime result | `docker-compose.local.yml` declares `postgres`, `migrate`, `worker`, `api`, `smoke`, `validator`; PostgreSQL pinned `postgres:15-alpine` |
| Validated | 2026-08-29, Corrective XV |

### Causal inputs

| Input | Value |
|---|---|
| `docker-compose.local.yml` | `e03f299a6729057ad9bce336cb01c59571d9b151dc98f40c76ca36554e3f8620` |
| `docker-compose.e2e.yml` | `2a257a58b29326d2b1b2270a297cb80fe08400aba6a84ce000ac71863c297c29` |

### Invalidation conditions

* Either Compose file changes.
* A service is added to or removed from a declared surface.
* The topology contract table in `SUPPORTED_ENVIRONMENTS.md` changes.

---

## IEC-XV-03 — Merge-governing P13 proof graph

| Field | Value |
|---|---|
| Evidence ID | `IEC-XV-03` |
| Validated property | The required `B2.5-P13 E2E Trust Closure` aggregate fails unless every load-bearing job succeeds |
| Runtime result | Aggregate requires `core`, `c9-positive-confidence`, `c10-artifact-topology`, `c13-semantic-history`, `c14-semantic-authority`, `c15-issuance-truth` |
| Negative control | `scripts/ci/validate_b25_p13_c15_closure.py --negative-control` mutates the aggregate's `needs:` list and must turn red |
| Validated | 2026-08-29, Corrective XV |

### Causal inputs

| Input | Value |
|---|---|
| `.github/workflows/b2_5-p13-e2e-trust-closure.yml` (pre-XV) | `f04767205a34e0377542d81e971dfedc3ad1a7881ec7f35cc7d6a43d864e55e9` |

### Invalidation conditions

* The workflow file changes (Corrective XV changes it, adding the C15 job —
  this capsule's hash is the pre-change baseline and is recorded so the diff is
  auditable).
* Any job is removed from the aggregate's `needs:` list.
* A load-bearing step gains `continue-on-error`.

---

## Capsules explicitly **not** claimed

Stated so absence is not mistaken for coverage:

* **Live multi-role Bayesian worker physics (C6/C7/C9/C10/C11/C12 behavioural
  tier).** Corrective XV did not touch those code paths, and no capsule is
  offered for them here. They are proven by the CI production-equivalent
  surface, not by this ledger.
* **Public internet JWKS endpoint.** No deployed issuer was exercised. The
  historical-key journey in `test_b25_p13_c15_issuance_truth.py` uses the real
  HTTP route with public-only key material, which is the product boundary; it is
  not a claim about a hosted DNS endpoint.

# Infrastructure Evidence Capsules

B2.5-P13 Correctives XV-XVI, infrastructure evidence ledger.

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

## IEC-XVI-01 — PostgreSQL 15 bidirectional issuance truth

| Field | Value |
|---|---|
| Evidence ID | `IEC-XVI-01` |
| Original validated SHA | `be29cc6c644d65516bbac26537c0e597ed419ef3` + Corrective XVI working tree |
| Validated property | A fresh PostgreSQL 15 database reaches `202608301200`; a non-superuser, non-`BYPASSRLS` migration owner completes `head -> 202608291200 -> head`; and ordinary `app_user` cannot create `issued` history with a fabricated hash, a NULL hash, or the migration-only legacy state |
| Runtime result | PostgreSQL 15.19; migration round trip passed; role flags `migration_owner=false:false`, `app_user=false:false`, `app_worker=false:false`, `app_dispatch_publisher=false:false`; the three direct SQL falsifiers were rejected |
| Negative controls used | The pre-remediation schema accepted both a fabricated signature hash and NULL signature hash. The C16 behavioral gate repeats those exact ordinary-role writes and additionally attempts a runtime transition to `issued_legacy`. |
| External mutable dependencies | Docker Hub `postgres:15-alpine` digest below |
| Validated | 2026-08-30, Corrective XVI |

### Causal inputs

| Input | Value |
|---|---|
| PostgreSQL image digest | `sha256:fe0737ba566a2c5b2a28f34433c0a423261900ec17b9bf7ad115e1aae7e57f1b` |
| Reported server version | `PostgreSQL 15.19` |
| Alembic head revision | `202608301200` |
| Migration chain hash | `043c5496a65e84e4a1aade33d64be911eca137d3313bf964f026423ee580a0e2` (`SHA-256` over sorted relative path, NUL, and file bytes) |
| C16 migration | `2782242252d285e356dc1ad7aa8ff32ebaf1b31c430b5cf4f6a785237e6bcd13` |
| `prepare_migration_authority_boundary.py` | `82f56e211f578f27a5f2142fbc4a83fc2d494bef6951bb9fa46ce0bb7ece4868` |
| PostgreSQL setup action | `e003992e5d026e6f9447a4cbf687c520182dfd9ac7b2f710dc8605b2c72f283e` |

### Invalidation conditions

* PostgreSQL major version or image digest changes.
* Any migration is added, removed, or modified.
* The role bootstrap, migration authority, issuance constraint, or legacy-state
  transition trigger changes.
* A runtime principal gains `rolsuper` or `rolbypassrls`.

---

## IEC-XVI-02 — Independent production Bayesian topology

| Field | Value |
|---|---|
| Evidence ID | `IEC-XVI-02` |
| Original validated SHA | `be29cc6c644d65516bbac26537c0e597ed419ef3` + Corrective XVI working tree |
| Validated property | A clean production Bayesian image contains its governed dependency closure, physically executes the declared four-chain topology twice, and completes the real positive-confidence journey through distinct publisher and execution-worker database principals |
| Runtime result | Image `sha256:ced00fc360a02759f6a611c1cbd4db96fee78869ad5286aa8ca56db65c068fb6`; two runs each observed 4 chains and 4,000 posterior draws, R-hat 1.000934, ESS 1821.77, zero divergences, no identical chain pairs; containment was 1 PyMC core, 1 BLAS core, worker concurrency 1; positive-confidence journey passed |
| Runtime authority | Production attestation `direct_postgres_deployment_attested`; PostgreSQL 15; `app_dispatch_publisher` and `app_worker` are distinct non-superuser/non-bypass principals |
| Negative controls used | The production policy rejected an invented attestation label. The first positive journey then exposed transaction-scoped `now()` predating a later source-read completion and the corrected `clock_timestamp()` journey passed. |
| Reproduction | `scripts/ci/run_b25_p13_c16_production_topology_proof.sh` and `docs/environment/B2.5-P13 INDEPENDENT PRODUCTION TOPOLOGY REPRODUCTION.md` |
| Validated | 2026-08-30, Corrective XVI |

### Causal inputs

| Input | Value |
|---|---|
| Topology proof runner | `61daed0fec81eecb301853e07d06ec6cdffae6b609e4b4d0af3fdbac890e3120` |
| `backend/Dockerfile.bayesian` | `b303bc67a3f0fc514b8bbb37bcff673e8c000cf2d9a149841a5c14f074f5190e` |
| `fit_execution.py` | `0c2b833c84996c6147de8e949f412981773d0d9e09a2c031e573cfa63d23a272` |
| `inference_profile.py` | `1c22f8a04ee3343fc628975041e2cfefa6a0a161dfa963c44403c833853199d5` |
| Positive-confidence journey | `c475450be930a4090d715ca5571672e093010ee47c9f77b490fadda794c39108` |
| Policy bundle hash | `66cb748ab92eca922c27fca5f27e41a2d3282d7d511e7674524f018f9bc83a28` |

### Invalidation conditions

* Any causal input changes.
* The image, worker command, publisher command, queue routing, database role,
  topology attestation, inference profile, or confidence completion changes.
* A result is reused without rebuilding the image and rerunning both the
  physical topology and positive-confidence journey.

---

## IEC-XVI-03 — C16 proof graph and serialized schema deployment

| Field | Value |
|---|---|
| Evidence ID | `IEC-XVI-03` |
| Original validated SHA | `be29cc6c644d65516bbac26537c0e597ed419ef3` + Corrective XVI working tree |
| Validated property | The merge-governing aggregate requires the C16 behavioral/static gate, and production schema deployments for `main` share one stable, non-cancelling concurrency group across push and `workflow_run` triggers |
| Runtime result | Aggregate `needs` includes `c16-bidirectional-truth`; the C16 job runs PostgreSQL 15 migration round-trip, an issuance-authority topology assertion, six behavioral falsifiers, twenty-five semantic negative controls, and three live-database runtime negative controls; schema deployment uses `production-schema-deployment-${{ github.repository }}-main` with `cancel-in-progress: false` |
| Negative control | The C16 validator mutates each state-machine, route-ordering, constraint, privilege, issuance-custody, transition-graph, lineage, TCB, workflow-attachment, aggregate, deployment-concurrency, survey, topology, and runtime-falsifier obligation and requires all twenty-five mutations to turn red. Three further controls mutate the live database and process configuration: dropping the authority trigger, replacing it with a permissive body, and handing issuance custody back to the ordinary runtime DSN |
| Validated | 2026-08-30, Corrective XVI candidate; authoritative run URLs are recorded in the XVI report after protected-main merge |

### Causal inputs

| Input | Value |
|---|---|
| P13 proof workflow | `728f5f94dcb993e1914a4e25329715782f5f7c42a72458a6980b3b43fbeef710` |
| Production schema workflow | `b6a33b01a1cdfd7cc222b3fe53888e2890ff1a56cb6cd0646413f7c73024b529` |
| C16 static validator | `514cce7cd25e36c85b5d89f21acb721fdac142a379ae6011448e48ff3159958f` |

### Invalidation conditions

* Either workflow, the C16 validator, or its runtime test changes.
* `c16-bidirectional-truth` leaves the aggregate, becomes non-required, or a
  load-bearing step gains `continue-on-error`.
* The production deployment concurrency group varies by triggering run or
  permits cancellation.

---

## IEC-XVI-04 — Narrowed issuance-consequence database authority

| Field | Value |
|---|---|
| Evidence ID | `IEC-XVI-04` |
| Original validated SHA | `be29cc6c644d65516bbac26537c0e597ed419ef3` + Corrective XVI working tree |
| Validated property | On a PostgreSQL 15 database provisioned by the repository's own script and migrated to head, no ordinary runtime principal can turn structural plausibility into authoritative completed-issuance history, and the narrowed principal that can transition issuance remains bounded by the transition graph, terminal immutability, tenant binding, and monotonic lineage |
| Runtime result | PostgreSQL 15.19; `alembic upgrade head` -> `202608301200`; seven roles present, every `rolsuper=false` and `rolbypassrls=false`. A 15-case role x state matrix executed against `app_user`, `app_worker` and `app_trust_issuer`: 45/45 refusals. `app_user` and `app_worker` refused at `trust_issuance_authority_violation:principal`; `app_trust_issuer` refused at `transition`, `terminal`, `tenant_rebind`, `lineage_regression`, missing INSERT privilege, and the evidence CHECK constraints |
| Positive control | The legitimate `authorized -> signing -> issued` lineage completes under `app_trust_issuer` and retains the 64-byte signature; a retry after an unresolved outcome completes with `issuance_attempt_count=2, issuance_unknown_outcome_count=1`, so history models the reality that more than one signature may physically exist for one logical request |
| Negative controls used | Trigger dropped -> matrix RED -> restored -> GREEN. Trigger body replaced with an unconditional `RETURN NEW` -> RED -> migration round-trip restore -> GREEN. `TRUST_ISSUANCE_DATABASE_URL` pointed at the ordinary runtime DSN -> post-signature falsifier RED (fail-closed) -> restored -> GREEN |
| External mutable dependencies | Docker Hub `postgres:15-alpine` tag |
| Validated | 2026-08-30, Corrective XVI |

### Causal inputs

| Input | Value |
|---|---|
| C16 migration | `2906d2d1fa1a891301643d7f71d72d366ed175c9b67c7863f8b3d01abb2632f9` |
| `scripts/database/prepare_migration_authority_boundary.py` | `e832f126753753de72fb61f425e56c34186726274550ceb1ec17e2c59ea0ee8a` |
| `backend/app/trust/issuance_session.py` | `685ec215b8bddc76aa352cbfee9ca66653af5746f9164f9c64c7c8f524e90e40` |
| `backend/app/trust/audit.py` | `4bccdc5e6f45add454d79fd11a87f547db5fae9fc11975bfda69a6fd62d260d3` |
| `.github/actions/setup-postgres-ci/action.yml` | `d5d7031dd9cdc5ea083fa8610440515d8dbe35ff07fe3425f2aee5684b1eb2df` |

### Invalidation conditions

* The C16 migration, the provisioning script, the issuance custody module, the
  issuance writes in `audit.py`, or the setup action changes.
* The runtime role set changes, or any role's `rolsuper` / `rolbypassrls`
  changes, or `app_trust_issuer` gains membership in `app_rw`, `app_ro`,
  `app_user`, or `app_worker`.
* `trust_access_log_issuance_authority_guard` is dropped, disabled, or ceases to
  key on `session_user`.
* `app_trust_issuer` gains any table privilege beyond `SELECT, UPDATE` on
  `public.trust_access_log`.

---

## IEC-XV-01 — PostgreSQL 15 least-privilege topology and migration chain

| Field | Value |
|---|---|
| Evidence ID | `IEC-XV-01` |
| Original validated SHA | `0941d3599680b6317638bad69a4b0c44d0e365fa` (+ Corrective XV working tree) |
| Validated property | A PostgreSQL 15 database provisioned by `prepare_migration_authority_boundary.py` reaches Alembic head with six non-superuser, non-RLS-bypassing roles |
| Runtime result | PostgreSQL 15.19; `alembic upgrade head` -> `202608291200`; six roles present, every `rolsuper=false` and `rolbypassrls=false`. Superseded by `IEC-XVI-04`, which revalidates the same property at head `202608301200` with the seventh (`app_trust_issuer`) principal present. |
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

* **Hosted production Bayesian infrastructure.** IEC-XVI-02 proves the
  independently reproducible production-image topology against a fresh local
  PostgreSQL 15 deployment. It does not claim that a hosted production service
  was deployed or sampled.
* **Public internet JWKS endpoint.** No deployed issuer was exercised. The
  historical-key journey in `test_b25_p13_c15_issuance_truth.py` uses the real
  HTTP route with public-only key material, which is the product boundary; it is
  not a claim about a hosted DNS endpoint.

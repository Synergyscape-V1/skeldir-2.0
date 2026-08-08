# CI Topology Map

## Workflow Inventory

- Total workflow files: `49`.
- Default-path workflow files: `44`.
- Primary monolith: `.github/workflows/ci.yml` with `5784` lines and `69` jobs after M3 reduction.
- M3 governance workflow: `.github/workflows/m3-ci-governance.yml`.
- M4 operational runbook workflow: `.github/workflows/m4-operational-runbooks.yml`.
- B2.4 insertion lane: `.github/workflows/b2_4-gate-dry-run.yml`.

## Major Jobs

- `Governance Guardrails`: Postgres-only, forensics index, required status checks, branch protection integrity.
- `Contract Semantic Drift Gate`: registry-backed `contract-governance` cohort plus negative controls and runtime semantic checks.
- `B2.1-P0` through `B2.1-P6`: required DB-backed deterministic attribution preservation jobs using `.github/actions/setup-postgres-ci`.
- `B2.2-P5` and `B2.2-P6`: required webhook performance/closure jobs using `.github/actions/setup-postgres-ci`.
- `B2.3 Composite Proof Harness`: required B2.3 closure job using `.github/actions/setup-postgres-ci`.
- `M3 CI Governance`: registry, matrix, topology, B2.4 dry-run, metrics, and cohort-summary validation.

## Required Branch Contexts

- `B0.7 P2 Runtime Proof (LLM + Redaction)`
- `Celery Foundation B0.5.1`
- `Validate Contracts`
- `Frontend Contract Consumption Gate`
- `Mock Usability Gate`
- `Phase 1 Negative Controls`
- `Phase 1 Runtime Conformance`
- `JWT Tenant Context Invariants`
- `B1.2 P6 RBAC Proofs`
- `B1.2 P7 Worker Coherence Proofs`
- `B1.2 P8 Error Contract Proofs`
- `B1.2 P9 E2E System Proofs`
- `B0.6 Phase 2 Adjudication`
- `Phase Gates (B0.3)`
- `Phase 8 Regression Gate (Full Physics)`
- `b11-p2-secret-chokepoint-gate`
- `b11-p2-readiness-gate`
- `b11-p4-static-and-runtime-gate`
- `b11-p4-ci-audit-gate`
- `Contract Semantic Drift Gate`
- `B1.4 P0 Privacy Authority Lock`
- `B1.3 P0 Governance & Scope Lock`
- `B1.3 P1 Contract Authority Proofs`
- `B1.3 P2 Handshake State Proofs`
- `B1.3 P3 Durable Lifecycle Schema Proofs`
- `B1.3 P4 Boundary Hardening Proofs`
- `B1.3 P5 Adapter Layer Proofs`
- `B1.3 P6 Runtime Lifecycle Proofs`
- `B1.3 P7 Refresh Orchestration Proofs`
- `B1.3 P8 Failure & Baseline Proofs`
- `B1.3 P9 Core Substrate Closure Proofs`
- `B1.3 P10 Provider Tranche Proofs`
- `B1.3 P11 E2E System Proofs`
- `B1.4 P1 Ingress Contract Sanitization`
- `B1.4 P2 Session Authority Proofs`
- `B1.4 P3 Attribution Locality Proofs`
- `B1.4 P4 Retention + Deterministic Deletion Proofs`
- `B1.4 P5 Export Log Artifact No-Leak`
- `B1.4 P6 Merge-Blocking Privacy Proof Plane Binding`
- `B1.4 P7 E2E Privacy System Proofs`
- `B2.1-P0 Runtime Authority Closeout`
- `B2.1-P1 Semantic Replay Lock`
- `B2.1-P2 Strategy Kernel + Session Boundary Proofs`
- `B2.1-P3 Persistence Authority + Minimal Read Surface`
- `B2.1-P4 Queue Isolation + Performance Semantics Lock`
- `B2.1-P5 Non-Vacuous Proof Harness + Merge-Blocking Adjudication`
- `B2.1-P6 Full End-to-End Closure + Downstream Readiness`
- `B2.2-P5 Webhook Latency Adjudication`
- `B2.2-P6 Merge-Blocking Closure + Downstream Readiness`
- `B2.3 Composite Proof Harness`
- `B2.4 Gate Dry Run`
- `B2.4-P1 DB Proof`
- `B2.4-P4 PostgreSQL Runtime Proof`
- `B2.4-P5 Bayesian Runtime Harness`
- `B2.4-P5 PostgreSQL Runtime Proof`
- `B2.4-P6 Real Fit Worker Proof`
- `validate-b24-p6-real-fit-worker`
- `B2.4-P7 Diagnostic Semantics Proof`
- `validate-b24-p7-diagnostics`
- `B2.4-P8 Artifact Lifecycle Proof`
- `validate-b24-p8-artifact-lifecycle`
- `B2.4-P9 Worker Tenant Hygiene Proof`
- `B2.4-P10 Read-Only Projection Proof`
- `B2.4-P11 CI Gates and Negative Control Harness`
- `B2.5-P8 Signing Verification`
- `B2.5-P9 Machine Identity`
- `B2.5-P10 Trust API Surface`
- `B2.5-P11 Export Compatibility`
- `B1.7 Explanation Runtime Adjudication`
- `B1.7 P4 Mixed Workload Benchmark`
- `m0-maintainability-scope-lock`
- `validate-ops-runbooks`
- `runtime-ops-proofs`

## Jobs That Call scripts/ci Enforcers

Registered enforcer invocations are indexed in `docs/ci/enforcer_registry.yaml`. Current default-path `ci.yml` script invocations: `74` after M3, down from baseline `97`.

## Jobs That Use DB Setup

M3 removed repeated direct `prepare_migration_authority_boundary.py` blocks from `ci.yml` and replaced them with 11 uses of `.github/actions/setup-postgres-ci/action.yml`.

## M0/M1/M2 Protected Gates

- M0 Maintainability Scope Lock: `.github/workflows/m0-maintainability-scope-lock.yml`, required context `m0-maintainability-scope-lock`.
- M1 Local Development Authority: `.github/workflows/m1-local-dev-authority.yml`, preservation workflow remains unchanged by M3.
- M2 Test Feedback Loop: `.github/workflows/m2-test-feedback-loop.yml`, preservation workflow remains unchanged by M3.
- M4 Operational Runbooks: `.github/workflows/m4-operational-runbooks.yml`, required contexts `validate-ops-runbooks` and `runtime-ops-proofs`.

## Active Gates

Active and required gates are distinguished by `status`, `default_execution`, `execution_cohort`, and `ci_visibility` in `docs/ci/enforcer_registry.yaml`.

## Historical/Legacy Gates

No historical or legacy gates still execute by default after M3 classification. Uncalled `scripts/ci/*.py` files are classified as `utility` in the executable registry and dispositioned in `docs/ci/gate_subsumption_matrix.yaml`.

## Execution Cohorts

- `b2-4-dry-run`: 16 registered gate(s)
- `contract-governance`: 25 registered gate(s)
- `db-backed-governance`: 18 registered gate(s)
- `m0-m1-m2-preservation`: 3 registered gate(s)
- `static-governance`: 43 registered gate(s)
- `utility-only`: 3 registered gate(s)

## Candidate Consolidation Surfaces

- Additional B2.1/B2.2 runtime jobs can move more repeated benchmark artifact handling into shared scripts after current required contexts are observed green on `main`.
- Older non-required workflow-specific DB setup blocks outside `ci.yml` remain candidates, but M3 avoids changing them until required-context preservation is proven.

## B2.4 Insertion Lane

B2.4 gates attach through `.github/workflows/b2_4-gate-dry-run.yml` and the `b2-4-dry-run` registry cohort. The aggregate `B2.4 Gate Dry Run` job is required on protected `main` because it executes the static P1-P10 validator lane and fails on missing Makefile/registry wiring. P1's dedicated `B2.4-P1 DB Proof` is required because it proves the authority schema and RLS/GUC substrate against real PostgreSQL. P4's dedicated `B2.4-P4 PostgreSQL Runtime Proof` is required because it proves resource-bound persistence behavior against real PostgreSQL. P5's dedicated `B2.4-P5 Bayesian Runtime Harness` and `B2.4-P5 PostgreSQL Runtime Proof` are required because they carry the native Bayesian runtime containment proof and the durable timeout fallback proof. P6's dedicated `B2.4-P6 Real Fit Worker Proof` is required because it proves fit-id-only runtime execution under `app_user`, frozen P2/P4 source replay, source-derived observed input, and child-only PyMC execution. P7's dedicated `B2.4-P7 Diagnostic Semantics Proof` is required because it proves governed child-side diagnostics, finite-value thresholding, strict zero-divergence interval conditionality, bounded interval summaries, and no interval exposure after failed diagnostics. P8's dedicated `B2.4-P8 Artifact Lifecycle Proof` is required because it proves Postgres-native bounded artifact persistence, exact stored-byte hash verification, tenant quota enforcement, audit-preserving pruning, and the absence of cloud/local/large-object storage. P9's dedicated `B2.4-P9 Worker Tenant Hygiene Proof` is required because it proves transaction-local tenant context, clean connection return, tenant/fit/hash/attempt workspaces and compiledirs, tenant-bound artifact refs, parent env immutability, failure cleanup, and log payload hygiene. P10's dedicated `B2.4-P10 Read-Only Projection Proof` is required because it proves deterministic-left confidence projection, backend-owned confidence semantics, no-fit/stale-fit preservation, payload/authority airgap, no compute trigger, and no frontend-owned thresholding. P11's dedicated `B2.4-P11 CI Gates and Negative Control Harness` is required because it proves the B2.4 gate system cannot silently omit, skip, unregister, downgrade, or overclaim P1-P12 proof jobs. P12's dedicated `B2.4-P12 Internal E2E Proof Harness` is required because it proves internal/local/CI composition across committed visibility, state-driven async waiting, artifact lifecycle, sealed payloads, tenant hygiene, projection semantics, and non-overclaim boundaries. The metadata dry-run lane does not expand `ci.yml` and does not mutate M0/M1/M2 workflows.

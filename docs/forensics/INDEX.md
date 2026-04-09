# Forensics Evidence Index

This index enumerates evidence packs stored under `docs/forensics/`.

## Hygiene
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Hygiene | docs/forensics/evidence_hygiene_remediation_evidence.md | Evidence hygiene remediation proof pack | PR #15 / fa5d30c | pending |

## Phase remediation evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| B0.7 Context inventory | docs/forensics/b07_context_inventory_evidence.md | Evidence-backed baseline of B0.7 readiness (static + runtime where possible) | PR #50 / 4696a51 | pending |
| B0.7 P0 CI harness | docs/forensics/b07_p0_ci_harness.md | Non-vacuous contracts + provider boundary + CI substrate proof (worker) | PR #51 / 8874821 | https://github.com/Muk223/skeldir-2.0/actions/runs/21723348773 |
| B0.7 P2 remediation | docs/forensics/b07_p2_remediation_evidence.md | Continuous runtime proof + redaction/fail-fast remediation evidence (main push-run verified) | PR #54 / 34761ec | https://github.com/Muk223/skeldir-2.0/actions/runs/21768773155 |
| B0.7 Phase 5 compute safety | docs/forensics/b07_phase5_compute_safety_proof_index.md | Compute safety proof index for EG5.1-EG5.9 (LLM/Bayesian bounded-compute gates). | PR #85 / eace60adb | https://github.com/Muk223/skeldir-2.0/actions/runs/21995773671 |
| B0.7 Phase 6 complexity router | docs/forensics/b07_phase6_complexity_router_policy_proof_index.md | Deterministic router + policy + ledger + CI proof index for EG6.0-EG6.7. | pending | pending |
| B0.7 Phase 6 remediation evidence | docs/forensics/b07_phase6_complexity_router_policy_remediation_evidence.md | Detailed findings + implementation/remediation evidence for H6.1-H6.7 and EG6.0-EG6.7. | pending | pending |
| B0.7 Phase 7 ledger/cost/cache/audit | docs/forensics/b07_phase7_ledger_cost_cache_audit_remediation_evidence.md | Ledger write-path unification, runtime grants, cost+reconciliation proof, and cache performance adjudication bundle for EG7.1-EG7.3. | PR #88 / pending | pending |
| B0.7 P4 remediation | docs/forensics/b07_p4_remediation_evidence.md | E2E distributed runtime proof + operational readiness closure pack (compose + SQL dashboards + runbooks) | pending | pending |
| B0.7 Phase 8 closure pack | docs/forensics/b07_phase8_end_to_end_operational_readiness_proof_index.md | Unified end-to-end closure pack across attribution/revenue/LLM topologies with explicit CI-sanity vs full-physics authority semantics and staging full-physics evidence path (EG8.1-EG8.7). | PR #93 / ead847e | CI subset: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22108568630 ; Full physics: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22108574603 |
| B1.1 P1 remediation findings | docs/forensics/evidence/b11_p1/B11_P1_FINDINGS_AND_REMEDIATIONS.md | B1.1-P1 SSOT contract, namespacing boundary, IaC control-plane, and CI adjudication findings/remediation record. | PR #109 / pending | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22242378414 |
| B1.1 P1 proof index | docs/forensics/evidence/b11_p1/PROOF_INDEX.md | Gate-to-artifact proof map for B1.1-P1 (SSOT, namespace deny, IaC state, audit evidence, CI links). | PR #109 / pending | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22242378414 |
| B1.1 P1 corrective remediation report | docs/forensics/evidence/b11_p1/B11_P1_CORRECTIVE_REMEDIATION_REPORT.md | Corrective-action report for Gate 3/4/5 with branch-protection hardening and CI-role audit proof closure. | PR #109 / pending | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22242378414 |
| B1.1 P2 proof index | docs/forensics/evidence/b11_p2/PROOF_INDEX.md | Secret choke point + fail-closed readiness proof index with CI non-vacuity artifacts. | PR #110 / pending | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22245400181 |
| B1.1 P3 remediation findings | docs/forensics/evidence/b11_p3/B11_P3_FINDINGS_AND_REMEDIATIONS.md | P3 cryptographic secret rotation findings/remediation including key-ring cache semantics and bounded verification/decrypt behavior. | PR #111 / pending | pending |
| B1.1 P3 proof index | docs/forensics/evidence/b11_p3/PROOF_INDEX.md | Gate-to-artifact proof map for P3 rotation drills, cache bounds, and envelope key-ID decrypt constraints. | PR #111 / pending | pending |
| B1.1 P4 proof index | docs/forensics/evidence/b11_p4/PROOF_INDEX.md | Gate-to-artifact proof map for DB/provider secret migration, CI OIDC retrieval, CloudTrail audit tethering, and rotation-readiness drills. | PR #121 / pending | pending |
| B1.1 P4 findings/remediation | docs/forensics/evidence/b11_p4/B11_P4_FINDINGS_AND_REMEDIATIONS.md | Corrective findings/remediation for H01/H02/H06/H07/H09 including non-vacuous rotation drills, Gate 4 durable-evidence refresh, and immutable evidence mapping updates. | PR #121 / pending | pending |
| B1.1 P5 proof index | docs/forensics/evidence/b11_p5/PROOF_INDEX.md | Gate-to-artifact proof map for webhook secret ciphertext/key-id redesign, rotation-safe decrypt, bounded cache invalidation, and CI adjudication evidence. | PR #122 / e4194c78f | pending |
| B1.1 P5 findings/remediation | docs/forensics/evidence/b11_p5/B11_P5_FINDINGS_AND_REMEDIATIONS.md | Corrective findings/remediation for zero-downtime expand/contract migration design, sync cache eviction, and CI artifact mapping for phase closure. | PR #122 / e4194c78f | pending |
| B1.1 P6 closure pack | docs/forensics/evidence/b11_p6/README.md | End-to-end B1.1 closure pack index for integrated gates, immutable proof mapping, and CI adjudication artifacts. | PR #134 / c796821340dcef441ab15394f8e78a5f9a617c44 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22408597678 |
| B1.1 P6 proof index | docs/forensics/evidence/b11_p6/PROOF_INDEX.md | Durable commit->run->bundle mapping scaffold for P6 gates with populated authoritative main-run evidence anchors. | PR #134 / c796821340dcef441ab15394f8e78a5f9a617c44 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22408597678 |
| B1.1 P6 findings/remediation | docs/forensics/evidence/b11_p6/B11_P6_FINDINGS_AND_REMEDIATIONS.md | Final H01/H02 validation and gate-by-gate immutable checksum closure for B1.1-P6. | PR #134 / c796821340dcef441ab15394f8e78a5f9a617c44 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22408597678 |
| B1.2 context inventory report | docs/forensics/B1.2_Context_Inventory_Report.md | B1.2 context inventory with B1.2-P0 remediation execution notes and evidence pointers. | PR #135 / pending | pending |
| B1.3 context inventory report | docs/forensics/B1.3_Context_Inventory_Report.md | B1.3 forensic inventory (H01-H34) and implementation-readiness verdict against main/runtime/CI authority. | PR #pending / pending | pending |
| B1.3-P0 remediation evidence pack | docs/forensics/B1.3-P0_Remediation_Evidence_Pack.md | Adjudication lock + scope-truth lock remediation ledger with branch-protection, CODEOWNERS, and CI proof pointers. | PR #pending / pending | pending |
| B1.3-P2 remediation evidence pack | docs/forensics/B1.3-P2_Remediation_Evidence_Pack.md | Ephemeral OAuth handshake state substrate remediation ledger with replay/expiry/GC proofs and P2 adjudication status. | pending | pending |
| B1.3-P3 remediation evidence pack | docs/forensics/B1.3-P3_Remediation_Evidence_Pack.md | Durable lifecycle schema extension evidence for metadata/ciphertext separation, canonical hierarchy continuity, and P3 adjudication lock. | PR #pending / pending | pending |
| B1.3-P4 remediation evidence pack | docs/forensics/B1.3-P4_Remediation_Evidence_Pack.md | Secret-path exclusivity, least-privilege mutation RBAC, structural non-leak boundary hardening, and P4 CI adjudication proof. | PR #189 / 248067af0 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22925728358 |
| B1.3-P5 remediation evidence pack | docs/forensics/B1.3-P5_Remediation_Evidence_Pack.md | Provider-neutral OAuth lifecycle adapter-layer remediation evidence with deterministic adapter proofs, capability-truth lock, outbound exception-boundary hardening, and authoritative merge/governance restoration proof. | PR #192 / ad61c80d3 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22966484204 |
| B1.3-P6 remediation evidence pack | docs/forensics/B1.3-P6 Remediation Evidence Pack.md | Runtime lifecycle introduction evidence for authorize/callback/status/disconnect composition, adapter dispatch lock, callback state integrity, safe status/disconnect semantics, and P6 adjudication gate closure. | PR #194 / pending | pending |
| B1.3-P7 remediation evidence pack | docs/forensics/B1.3-P7 Remediation Evidence Pack.md | Refresh orchestration + canonical valid-token resolution evidence for scheduler/task topology, failure-class policy, single-flight locking, non-leak task/result surfaces, and P7 adjudication closure. | PR #195 / pending | pending |
| B1.3-P8 remediation evidence pack | docs/forensics/B1.3-P8 Remediation Evidence Pack.md | Failure taxonomy + graceful degradation + provider baseline stabilization evidence including refresh-state mapping, churn suppression, supported-tranche proofs, and P8 adjudication lock. | PR #196 / pending | pending |
| B1.3-P9 remediation evidence pack | docs/forensics/B1.3-P9 Remediation Evidence Pack.md | Core substrate closure pack evidence for composed OAuth lifecycle proof, deterministic+real provider composition, tenant isolation/worker-envelope parity negatives, and P9 adjudication gate wiring. | PR #197 / fc2b52a6f210401f1abc4af589739669afdc7068 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23025369493 |
| B1.3-P10 remediation evidence pack | docs/forensics/B1.3-P10 Remediation Evidence Pack.md | Provider rollout tranche closure evidence for six-provider target lock, tranche truth/governance alignment, provider-specific lifecycle proofs, CI-safe proof topology, refresh credential concurrency safety, and P10 adjudication gate wiring. | PR #pending / pending | pending |
| B1.3-P11 remediation evidence pack | docs/forensics/B1.3-P11 Remediation Evidence Pack.md | Final IC2-style composed lifecycle closure evidence for six-provider-integrated E2E proofs, multi-tenant safety negatives, artifact-integrity lock, and enforcement-plane required-check governance. | PR #202 / a4bb72b15 | pending |
| B1.4-P0 remediation evidence pack | docs/forensics/B1.4-P0 Remediation Evidence Pack.md | Corrective-action remediation ledger for governance integrity lock, DSAR OpenAPI exposure, event-lifecycle authority adjudication, and universal-main CI closeout validation. | PR #207 / open | https://github.com/Synergyscape-V1/skeldir-2.0/pull/207 |
| B1.4-P0 privacy authority lock remediation pack | docs/forensics/B1.4-P0_Privacy_Authority_Lock_Remediation_Pack.md | Companion privacy-authority lock pack documenting hypothesis outcomes, runtime/contract/CI remediations, and post-merge coherence evidence updates for B1.4-P0 corrective closeout. | PR #207 / open | https://github.com/Synergyscape-V1/skeldir-2.0/pull/207 |
| B1.4-P1 remediation evidence pack | docs/forensics/B1.4-P1 Remediation Evidence Pack .md | Bounded corrective closeout for production-typed DLQ replay contract safety, multi-hour cross-midnight continuity proof hardening, migration-authority adjudication, and semantic clarity remediation. | PR #213 / e98b6a065063235ff7eb25526ed4affec5e148cd | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23305159063 |
| B1.4-P2 remediation evidence pack | docs/forensics/B1.4-P2 Remediation Evidence Pack .md | Event substrate rewrite + session authority introduction follow-up corrective closeout evidence for expired-session severance, bounded-scope adjudication, and post-merge main-green proof. | PR #218 / d33c2d23248d38c75fd7f07b7a0d45d8bd6a4430 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23353935825 |
| B1.4-P3 remediation evidence pack | docs/forensics/B1.4-P3 Remediation Evidence Pack .md | Terminal infrastructure corrective evidence for historical aggregate export recovery, ephemeral order/click continuity substrate, universal webhook continuity wiring, and DB-backed TTL hard-delete proofs. | PR #223 / 9e6cde8e707aea17acaac901d050806db46a3775 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23385964517 |
| B1.4-P4 remediation evidence pack | docs/forensics/B1.4-P4 Remediation Evidence Pack .md | Corrective closeout evidence for audit-safe erasure artifacts (`compliance_audit_ledger`), indexed deletion lookup hardening, placeholder reinsertion elimination, split-substrate finality, and preservation-suite proof continuity. | PR #227 + PR #228 / fdda35627df3f10dd00dc90ad0fd996f5fac3d74 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23410591042 ; https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23411625043 |
| B1.4-P5 remediation evidence pack | docs/forensics/B1.4-P5 Remediation Evidence Pack .md | Export allowlist + logging/failure-surface + artifact scanner no-leak closure evidence with hypothesis adjudication, non-vacuous gates, and preservation-suite reruns. | PR #230 / pending | https://github.com/Synergyscape-V1/skeldir-2.0/pull/230 |
| B1.4-P6 remediation evidence pack | docs/forensics/B1.4-P6 Remediation Evidence Pack .md | Merge-blocking privacy proof-plane binding evidence covering P0-P5 topology adjudication, non-vacuous negative controls, artifact durability, governance/workflow alignment, and explicit P7 branch-protection hardware deferral encoding. | PR #233 / 6d1c58b3af33345c5dda7f538174529e9d92ba85 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23456296864 |
| B1.4-P7 remediation evidence pack | docs/forensics/B1.4-P7 Remediation Evidence Pack .md | Final composed privacy-system closure evidence for P0-P6 preservation, non-vacuous E2E negatives, artifact/legal closure, and live branch-protection hardware enforcement. | PR #236 / 192312c61b874a142396d6a14f2e40853f665860 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23464811905 |
| B1.5 context inventory report | docs/forensics/B1.5_Context_Inventory_Report.md | Forensic B1.5 substrate inventory and H01-H15 adjudication against repo/runtime/CI authority. | PR #239 / c0646dc4a52f0a4c6dc2418b2ffa81ac59a6ada0 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23512177349 |
| B1.5-P0 remediation evidence pack | docs/forensics/B1.5-P0 Remediation Evidence Pack .md | Authority lock + scope lock + invariant lock remediation with non-vacuous enforcement and CI adjudication evidence. | PR #239 / c0646dc4a52f0a4c6dc2418b2ffa81ac59a6ada0 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23512177349 |
| B1.5-P1 remediation evidence pack | docs/forensics/B1.5-P1 Remediation Evidence Pack .md | Lifecycle authority selection/subordination remediation with canonical grammar enforcement, worker terminalization lockout, and non-vacuous CI/runtime proofs. | PR #243 / de9a096f3 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23557640390 |
| B1.5-P2 remediation evidence pack | docs/forensics/B1.5-P2 Remediation Evidence Pack .md | Contract addendum + polling vocabulary completion evidence covering review mutation routes, idempotency semantics, truthful status URLs, deterministic-vs-synthesis separation, and CI semantic adjudication hardening. | PR #244 / cd569d0ec0ee45096388cbdaecbb800c6b9fc407 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23564887680 |
| B1.5-P3 remediation evidence pack | docs/forensics/B1.5-P3 Remediation Evidence Pack .md | Runtime route binding and review-state enforcement evidence covering mounted B1.5 runtime surfaces, authority binding, legal transitions, Postgres-native idempotent replay, strict request boundary rejection, failure-surface truth, audit mutation persistence, lightweight polling projection discipline, and runtime conformance closure. | pending | pending |
| B1.5-P4 remediation evidence pack | docs/forensics/B1.5-P4 Remediation Evidence Pack .md | Mock-plane/SDK/typed-boundary convergence evidence covering default B1.5 mock startup + health coverage, regenerated frontend contract types, generated-operation consumer compile gates, typed deterministic-vs-synthesis separation enforcement, and non-vacuous regression controls. | PR #248 / 85cecd2806a2bb41fd24b291c8a3395e5cb1294c | pending |
| B1.5-P5 remediation evidence pack | docs/forensics/B1.5-P5 Remediation Evidence Pack .md | Frontend control-grammar wiring + follow-up corrective evidence covering attempt-scoped idempotency stability, backend problem-response UX mapping, strict deterministic-vs-synthesis rendering, bounded scope controls, and non-vacuous CI enforcement proofs. | PR #259 / pending | pending |
| B1.5-P6 remediation evidence pack | docs/forensics/B1.5-P6 Remediation Evidence Pack .md | Anti-cyborg governance lock evidence covering realtime exception registry, TypeScript AST/graph import fencing, machine-readable prohibited-signature matrix, deny-by-default escalation overrides, and non-vacuous negative controls. | PR #261 / 77f54a45ae4e19da8361436165ff31adae40e428 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23693538309 |
| B1.5-P7 remediation evidence pack | docs/forensics/B1.5-P7 Remediation Evidence Pack .md | Follow-up corrective evidence replacing synthetic browser conflict with backend-generated conflict truth, enforcing fail-closed browser execution, and wiring a deploy barrier while human validation remains pending. | PR #267 / 9c0bcdc6cdfdf6e682ff4bd7225f28c3c0e59d21 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23755766510 |
| B1.6-P1 remediation evidence pack | docs/forensics/B1.6-P1 Remediation Evidence Pack .md | Authority contract lock + typed upstream validation context + failure-sink grant/write prerequisite + breaker-policy lock + CI boundary guard evidence for B1.6-P1. | pending | pending |
| B1.6-P2 remediation evidence pack | docs/forensics/B1.6-P2 Remediation Evidence Pack .md | Canonical provider-boundary validation kernel evidence covering generic schema binding, deterministic normalization, typed fail-closed validation outcomes, cache replay re-validation semantics, and CI adjudication gates for B1.6-P2. | PR #271 / 9b2a4328033f0172116949fa5ce9b9731de86fbb | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23810228223 |
| B1.6-P3 remediation evidence pack | docs/forensics/B1.6-P3 Remediation Evidence Pack .md | Directive-2 corrective evidence covering schema-composed numeric validation via Pydantic context, zero fresh provider calls on ordinary cache drift, direct invalid-binding/non-numeric fail-closed runtime proofs, and CI topology hardening for post-merge main backend adjudication. | PR #pending / pending | pending |
| B1.6-P4 remediation evidence pack | docs/forensics/B1.6-P4 Remediation Evidence Pack .md | Request-local correction-informed regeneration, single attempt-budget cap, sink isolation, fail-closed API fallback hardening, and adjudicative CI gate wiring for B1.6-P4. | PR #277 / f52a2704c05c1d3800e00e2be9bd4a17fca4a42f | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23865525556 |
| B1.6-P5 remediation evidence pack | docs/forensics/B1.6-P5 Remediation Evidence Pack .md | Structured failure audit hardening with sink-write failure isolation, explicit degraded-audit semantics, non-processing job finalization proof under telemetry failure, deterministic rejection-rate/threshold simulation continuity, and non-vacuous CI adjudication closure for B1.6-P5. | PR pending / pending | pending |
| B1.6-P6 remediation evidence pack | docs/forensics/B1.6-P6 Remediation Evidence Pack .md | Mounted runtime adjudication evidence proving investigation/budget hallucination blocking before persistence and user-visible response, cache replay rejection without provider reentry, failure-sink insert proof, and merge-blocking CI gate wiring for B1.6-P6. Includes post-merge verification on latest `main` head. | PR #283 / 14586c7f61d7c8699a5c9442cf6baa37251d4272 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23911498320 |
| B1.7-P1 remediation evidence pack | docs/forensics/B1.7-P1 Remediation Evidence Pack .md | Deterministic route->service->DB authority-read closure evidence with authority/explanation structural separation, tenant-bound cross-tenant denial proofs, and CI adjudication wiring for B1.7-P1. | PR #290 / 90c05a3fe0854c30199c8b23c8493bd6468d6719 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23963399116 |
| B1.7-P2 remediation evidence pack | docs/forensics/B1.7-P2 Remediation Evidence Pack .md | Fast-tier provider-neutral override + strict output envelope + deterministic numeric validation binding + safe timeout/validation degradation proof closure for B1.7-P2. | pending | pending |
| B1.7-P3 remediation evidence pack | docs/forensics/B1.7-P3 Remediation Evidence Pack .md | Deterministic watermark-first cache replay identity, stale replay rejection without provider reentry, and structured truth-snapshot coherence proof closure for B1.7-P3. | PR #294 / ef803d16f524e5fef5a817d6a07a3ccc06cf54d2 | pending |
| B1.7-P4 remediation evidence pack | docs/forensics/B1.7-P4 Remediation Evidence Pack .md | Cold-path strategy closure evidence for Pattern B (`prewarm_required`) with bounded event-driven prewarm policy, contract-governed execution-state metadata, dedicated mixed-workload benchmark topology, and CI non-vacuous strategy enforcers. | PR #295/#296/#297 / c5d06d701 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24009750629 |
| B1.7-P5 remediation evidence pack | docs/forensics/B1.7-P5 Remediation Evidence Pack .md | Merge-blocking adjudication closure evidence for mounted explanation runtime proofs, fail-closed route/contract parity, anti-chat inclusion, and protected-branch required-context activation for B1.7. | PR #299 + PR #300 / 5369948c1 + 2ad5c4bed | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24098243784 |
| B1.7-P6 remediation evidence pack | docs/forensics/B1.7-P6 Remediation Evidence Pack .md | Final end-to-end validation remediation evidence covering composed mounted correctness, benchmark gate adjudication topology, benchmark validity hardening, and protected-branch PR/main closure semantics for B1.7-P6. | PR #315 / d4e63e52c | CI pending (PR #315); benchmark + post-merge main evidence pending |
| B1.5-P7 mental-model study README | docs/forensics/evidence/b15_p7/mental_model_study/README.md | Study package index for human-executed async-review mental-model validation protocol and evidence handling rules. | PR #263 / e17831ccf4b9114f315ded34668af63601e487de | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23711712032 |
| B1.5-P7 mental-model study protocol | docs/forensics/evidence/b15_p7/mental_model_study/protocol.md | Human-executable participant protocol for validating recommendation-review mental model comprehension. | PR #263 / e17831ccf4b9114f315ded34668af63601e487de | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23711712032 |
| B1.5-P7 mental-model facilitator script | docs/forensics/evidence/b15_p7/mental_model_study/facilitator_script.md | Standardized facilitator script to avoid introducing synchronous-chat framing bias during sessions. | PR #263 / e17831ccf4b9114f315ded34668af63601e487de | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23711712032 |
| B1.5-P7 mental-model scoring rubric | docs/forensics/evidence/b15_p7/mental_model_study/scoring_rubric.md | Scoring rubric defining pass/fail interpretation for async review-model understanding. | PR #263 / e17831ccf4b9114f315ded34668af63601e487de | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23711712032 |
| B1.5-P7 mental-model execution checklist | docs/forensics/evidence/b15_p7/mental_model_study/execution_checklist.md | Session-by-session execution checklist to preserve protocol integrity and evidentiary traceability. | PR #263 / e17831ccf4b9114f315ded34668af63601e487de | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/23711712032 |
| B1.2-P5 context baseline | docs/forensics/B1.2-P5_CONTEXT_BASELINE.md | Hypothesis-to-evidence baseline mapping (H01-H06) for revocation substrate remediation (denylist + tokens_invalid_before). | PR #158 / 6a0dc5a5a | pending |
| B1.2-P5 remediation evidence | docs/forensics/B1.2-P5_REMEDIATION_EVIDENCE.md | Exit-gate mapped proof for immediate revocation semantics (denylist + kill-switch) with worker parity and non-vacuous negative controls. | PR #158 / 6a0dc5a5a | pending |
| B1.2-P5 cost/GC baseline | docs/forensics/B1.2-P5_COST_GC_BASELINE.md | Baseline adjudication for hot-path DB I/O and denylist GC operational gaps prior to corrective action. | PR #159 / 08c3ccd9e | pending |
| B1.2-P5 cost/GC corrective evidence | docs/forensics/B1.2-P5_COST_GC_CORRECTIVE_EVIDENCE.md | Exit-gate mapped corrective evidence for cache-based revocation hot path, propagation SLA, bounded denylist GC, and non-vacuous negative controls. | PR #159 / 08c3ccd9e | pending |
| B1.2-P5 GC singleflight baseline | docs/forensics/B1.2-P5_GC_SINGLEFLIGHT_BASELINE.md | Baseline adjudication for denylist GC distributed-concurrency safety and missing fleet singleflight proofs. | PR #pending / pending | pending |
| B1.2-P5 GC singleflight corrective evidence | docs/forensics/B1.2-P5_GC_SINGLEFLIGHT_CORRECTIVE_EVIDENCE.md | Exit-gate mapped corrective evidence for Postgres advisory-lock singleflight GC, deterministic concurrent proof, and non-vacuous negative controls. | PR #pending / pending | pending |
| B1.2-P6 state baseline | docs/forensics/evidence/b12_p6/P6_state_baseline.md | Pre-remediation baseline for RBAC source-of-truth wiring, route modality boundaries, and revocation integration seams. | PR #161 / pending | pending |
| B1.2-P6 remediation evidence | docs/forensics/evidence/b12_p6/B1.2-P6_Evidence.md | Exit-gate mapped evidence for RBAC enforcement, role claims, immediate revocation semantics, bounded-cost hot path, contract preservation, and forensic CI-green closure. | PR #169 / bde5411f0 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22699128520 |
| B1.2-P6 v2 baseline | docs/forensics/evidence/b12_p6/P6_v2_baseline.md | v2 corrective baseline for scope visibility, Security-scoped enforcement, refresh role-authority source, and branch-protection required-check truth. | PR #pending / pending | pending |
| B1.2-P6 v2 corrective evidence | docs/forensics/evidence/b12_p6/B1.2-P6_v2_CORRECTIVE_EVIDENCE.md | Corrective-action evidence mapping EG6.C1/EG6.A1/EG6.D1/EG6.T1/EG6.R1/EG6.P1/EG6.CI1 to concrete code, tests, CI checks, and branch-protection enforcement. | PR #pending / pending | pending |
| B1.2-P6 v3 corrective baseline | docs/forensics/evidence/b12_p6/P6_v3_corrective_baseline.md | v3 corrective baseline validating/remediating fat-scope embedding, scope-native enforcement, OpenAPI admin default-deny lint reflection, refresh 200 downgrade semantics, and C3 stability. | PR #170 / 510e85565 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22730370980 |
| B1.2-P6 v3 corrective evidence | docs/forensics/evidence/b12_p6/B1.2-P6_v3_CORRECTIVE_EVIDENCE.md | Exit-gate mapped v3 corrective evidence for scope-native RBAC, fat JWT scopes, OpenAPI-reflected admin default-deny proof, refresh downgrade 200 behavior, contract/mapping validation, and merge-blocking CI adjudication. | PR #170 / c7bc9224d | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22731013903 |
| B1.2-P6 v5 baseline | docs/forensics/evidence/b12_p6/P6_v5_baseline.md | v5 pre-remediation baseline for scheme overloading, default-deny/security-presence gaps, empty-scope access declarations, and refresh empty-role fallback risk. | PR #171 / fc32dac71 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22737883482 |
| B1.2-P6 v5 corrective evidence | docs/forensics/evidence/b12_p6/B1.2-P6_v5_CORRECTIVE_EVIDENCE.md | v5 corrective evidence mapping scheme-explicit security, default-deny + scope coverage OpenAPI lint, refresh downgrade/deletion semantics, contract artifact validation, required-check enforcement context, and final CI-green closure remediation. | PR #172 / 235964b1ae4710aa8644230722f0709d30f0da3f | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22739351063 |
| B1.2-P7 state baseline | docs/forensics/evidence/b12_p7/P7_state_baseline.md | Baseline validation for worker-plane authority envelope, revocation path, enqueue choke-point, tenant binding parity, and non-eager proof readiness. | PR #pending / pending | pending |
| B1.2-P7 task inventory | docs/forensics/evidence/b12_p7/P7_task_inventory.md | Repo-derived Celery task classification ledger and tenant enqueue call-site map for EG7.1 adjudication. | PR #pending / pending | pending |
| B1.2-P7 evidence pack | docs/forensics/evidence/b12_p7/B1.2-P7_EVIDENCE.md | Exit-gate mapped worker coherence closure evidence (EG7.1-EG7.7), including CI required-check wiring. | PR #pending / pending | pending |
| B1.2-P7 v2 corrective evidence | docs/forensics/evidence/b12_p7/B1.2-P7_v2_CORRECTIVE_EVIDENCE.md | v2 corrective evidence with follow-up main-CI failure adjudication (`B0.5.3.3`), v3 prefork/boundary remediations, and merge-to-main adjudication logs. | PR #176 / 212c4e606 | merged |
| B1.2-P7 v3 prefork baseline | docs/forensics/evidence/b12_p7/P7_v3_prefork_baseline.md | Corrective baseline for prefork LISTEN/NOTIFY fork-safety proof gaps, System authority origination boundary gaps, and canonical context proof gaps before v3 remediation. | PR #176 / 8f366db11 | merged |
| B1.2-P8 auth error normalization evidence | docs/forensics/evidence/b12_p8/B1.2-P8_EVIDENCE.md | Exit-gate mapped evidence for non-leaky 401/403 canonical ProblemDetails parity across JWT + HMAC modalities, including runtime and contract proofs. | PR #pending / pending | pending |
| B1.2-P8 auth failure emitter map | docs/forensics/evidence/b12_p8/auth_failure_emitter_map.md | Static emitter-to-normalizer map for every audited auth failure path, plus runtime static inventory pointer. | PR #pending / pending | pending |
| B1.2-P8 v2 corrective baseline | docs/forensics/evidence/b12_p8/P8_v2_baseline.md | Corrective baseline validating webhook auth control-flow asymmetry, monkeypatch-proof gaps, body-size policy absence, and branch-protection required-check drift. | PR #179 / pending | pending |
| B1.2-P8 v2 corrective evidence | docs/forensics/evidence/b12_p8/B1.2-P8_v2_CORRECTIVE_EVIDENCE.md | Corrective-action closure evidence for constant-work webhook auth, pre-crypto size cap, deterministic control-flow/header/422 proofs, and CI/branch-protection adjudication. | PR #179 / pending | pending |
| B1.2-P9 baseline | docs/forensics/evidence/b12_p9/P9_baseline.md | Forensic baseline for final IC2-style composed E2E gate readiness, blocker hypotheses, and live branch-protection state capture. | PR #180 / f7db72803b9b5775996d7c304444406ca03fef9c | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22829740847 |
| B1.2-P9 evidence pack | docs/forensics/B1.2-P9_EVIDENCE.md | Exit-gate mapped evidence for EG9.1-EG9.5 and EG9.CI across composed API/DB/worker/webhook runtime with CI enforcement-plane linkage. | PR #180 / f7db72803b9b5775996d7c304444406ca03fef9c | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22829740847 |
| B1.2-P4 context baseline | docs/forensics/B1.2-P4_CONTEXT_BASELINE.md | Hypothesis-to-evidence baseline mapping (H01-H06) for token issuance and refresh lifecycle remediation. | PR #154 / pending | pending |
| B1.2-P4 remediation evidence | docs/forensics/B1.2-P4_REMEDIATION_EVIDENCE.md | Exit-gate mapped proof for token issuance/refresh lifecycle (15m access, 30d opaque refresh, hash-at-rest, rotate-on-use, race safety). | PR #154 / pending | pending |
| B1.2-P4 corrective baseline | docs/forensics/B1.2-P4_CORRECTIVE_BASELINE.md | Corrective-action baseline mapping for H01-H04 (family-revoke on reuse, tenant determinism, secret-only hashing, attacker-first proof gap). | PR #155 / 89b57ecd4e3837658d11614c8a6460cf9a540511 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22634785208 |
| B1.2-P4 corrective evidence | docs/forensics/B1.2-P4_CORRECTIVE_EVIDENCE.md | Corrective exit-gate evidence for tenant-required issuance, secret-only hashing, family revocation on reuse, and non-vacuous negative controls. | PR #155 / 89b57ecd4e3837658d11614c8a6460cf9a540511 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22634785208 |
| B1.2-P4 EG2a/EG5a baseline | docs/forensics/B1.2-P4_EG2a_EG5a_BASELINE.md | Baseline hypothesis adjudication for miss-path timing oracle (EG2a) and revocation lineage scope (EG5a). | PR #pending / pending | pending |
| B1.2-P4 EG2a/EG5a corrective evidence | docs/forensics/B1.2-P4_EG2a_EG5a_CORRECTIVE_EVIDENCE.md | Corrective proof map for miss-path dummy-bcrypt, family-scoped revocation, parallel-family survival, and non-vacuous negative controls. | PR #pending / pending | pending |
| B1.2-P3 PG stampede baseline | docs/forensics/B1.2-P3_PG_STAMPEDE_BASELINE.md | Baseline evidence mapping H01-H05 for fleet-level JWT refresh stampede risk prior to Postgres singleflight corrective work. | PR #150 / pending | pending |
| B1.2-P3 PG stampede corrective evidence | docs/forensics/B1.2-P3_PG_STAMPEDE_CORRECTIVE_EVIDENCE.md | Exit-gate mapped corrective evidence for Postgres-backed singleflight + shared JWKS cache + multi-process CI adjudication. | PR #150 / pending | pending |
| B1.2-P3 v4 baseline | docs/forensics/B1.2-P3_V4_BASELINE.md | Baseline findings for lock semantics, lock-miss behavior, steady-state DB access, and required-check enrollment before v4 corrective patch. | PR #152 / be61ff457 | https://github.com/Synergyscape-V1/skeldir-2.0/commit/be61ff45799bb43d4b719f0b9657535bae8afd32/checks |
| B1.2-P3 v4 corrective evidence | docs/forensics/B1.2-P3_V4_CORRECTIVE_EVIDENCE.md | Exit-gate mapped evidence for transaction-scoped xact lock, bounded lock-miss polling, hot-path 0-DB proof, and enforcement-plane required-check wiring. | PR #152 / be61ff457 | Main CI: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22590523182 ; Full physics: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22590911549 |
| B1.2-P0 adjudication map | docs/forensics/evidence/b12_p0/B1.2-P0_Adjudication_Map.md | One-page adjudication map: required checks, invariant mapping, and auth topology/error inventory counts. | PR #135 / pending | pending |
| B1.2-P0 remediation evidence | docs/forensics/evidence/b12_p0/B1.2-P0_REMEDIATION_EVIDENCE.md | Findings/remediations + local/CI proof trails for contract authority and required-check lock. | PR #135 / pending | pending |
| B1.2-P0 proof index | docs/forensics/evidence/b12_p0/PROOF_INDEX.md | Hypothesis verdict map (H01-H04) and exit-gate evidence pointers with reproducible commands. | PR #137 / pending | pending |
| B1.2-P1 remediation evidence | docs/forensics/evidence/b12_p1/B1.2-P1_REMEDIATION_EVIDENCE.md | Gate-to-proof map for transaction-local tenant context safety across API + worker planes, with CI-enforced non-vacuous negative controls and post-merge main adjudication links. | PR #139 / a045d5cb0 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22498347686 |
| B1.2-P2 remediation evidence | docs/forensics/B1.2-P2_REMEDIATION_EVIDENCE.md | Initial findings + remediations for privacy-safe auth substrate, RLS isolation, migration reversibility, and 0-PII CI audits, including post-remediation main adjudication closure details. | PR #142 / dbcba1412 | pending |
| B1.2-P2 corrective baseline proof | docs/forensics/B1.2-P2_CORRECTIVE_PROOF_BASELINE.md | Pre-remediation SQL baseline for users registry least-privilege corrective gap (roles, grants, users RLS, lookup boundary, users schema invariant). | PR #143 / 29bce1176 | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22527505704 |
| B1.2-P2 corrective evidence | docs/forensics/B1.2-P2_CORRECTIVE_EVIDENCE.md | Exit-gate mapped corrective evidence for users registry least-privilege lock (self-only users RLS, non-enumerability, tenantless lookup boundary, CI negative controls). | PR #144 / pending | pending |
| B1.2-P2 INSERT baseline proof | docs/forensics/B1.2-P2_INSERT_BASELINE.md | Baseline proof for users INSERT denial under FORCE RLS (policy inventory, grants, runtime-role insert attempt, provisioning-path discovery). | PR #145 / 9dc215eef | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22529557933 |
| B1.2-P2 INSERT corrective evidence | docs/forensics/B1.2-P2_INSERT_CORRECTIVE_EVIDENCE.md | Exit-gate mapped evidence for users pre-auth INSERT viability under FORCE RLS, including non-vacuous INSERT-policy regression control. | PR #145 / 9dc215eef | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/22529557933 |
| B0.3 Phase 2 hypothesis matrix | docs/forensics/b03_phase2_hypothesis_matrix.md | Hypothesis-driven adjudication of H2.* schema-closure risks with evidence pointers. | PR #71 / pending | pending |
| B0.3 Phase 2 schema closure | docs/forensics/b03_phase2_schema_closure_evidence.md | Runtime-backed EG2.1-EG2.5 closure evidence for authoritative schema + ledger contract. | PR #71 / pending | pending |
| B0.4 Phase 3 remediation | docs/forensics/b04_phase3_ingestion_integrity_remediation.md | Privacy ingestion integrity + revised customer-profile performance gate authority (EG3.1-EG3.5). | PR #72 / 20b3ffb | pending |
| B0.4 Phase 4 remediation | docs/forensics/b04_phase4_multitenancy_security_closure_evidence.md | Multi-tenancy/security closure evidence (RLS+FORCE coverage, runtime identity proof, DLQ lane isolation, B0.4 gate execution). | PR #81 / c44e778 | https://github.com/Muk223/skeldir-2.0/actions/runs/21959566889 |
| B055 Phase 3 v2 | docs/forensics/b055_phase3_remediation_v2_integrity_evidence.md | Phase 3 integrity remediation evidence pack | PR #17 / 93b58be | pending |
| B055 Phase 3 EG9 context | docs/forensics/b055_phase3_eg9_topology_idempotency_context.md | Pre-remediation topology/DI/idempotency baseline | PR #18 / 214a98d | https://github.com/Muk223/skeldir-2.0/actions/runs/20967066505 |
| B055 Phase 3 EG9 remediation | docs/forensics/b055_phase3_eg9_topology_idempotency_remediation_evidence.md | EG9/Topology/Idempotency remediation evidence | PR #18 / 214a98d | https://github.com/Muk223/skeldir-2.0/actions/runs/20967066505 |
| B055 Phase 3 v4 | docs/forensics/b055_phase3_v4_orm_coc_idempotency_remediation_evidence.md | ORM parity + chain-of-custody + explanation idempotency evidence | PR #19 / 671ea4b | https://github.com/Muk223/skeldir-2.0/actions/runs/20973767676 |
| B055 Phase 3 v5 | docs/forensics/b055_phase3_v5_migrated_db_coc_stub_semantics_evidence.md | Migrated DB + CoC + stub semantics evidence (artifact promotion) | PR #19 / 3893c70 | https://github.com/Muk223/skeldir-2.0/actions/runs/20979320024 |
| B055 Phase 4 | docs/forensics/b055_phase4_remediation_evidence.md | CI adjudication evidence bundle + manifest enforcement | PR #20 / d34e1a9 | https://github.com/Muk223/skeldir-2.0/actions/runs/21003920055 |
| B055 Phase 5 remediation | docs/forensics/b055_phase5_remediation_evidence.md | Phase 5 hermeticity + determinism + cohesion remediation | PR #22 / adjudicated_sha (see MANIFEST.json) | Bundle manifest (workflow_run_id) |
| B055 Phase 5 follow-up | docs/forensics/b055_phase5_followup_evidence_pack.md | Phase 5 config lock + determinism + COC follow-up evidence | PR #22 / adjudicated_sha (see MANIFEST.json) | MANIFEST.json (artifact) |
| B055 Month bucket fix | docs/forensics/b055_month_bucket_remediation_evidence.md | Month bucket remediation (LLM monthly costs) | PR #23 / adjudicated_sha (see MANIFEST.json) | MANIFEST.json (artifact) |
| B0.5.6 Phase 0 | docs/forensics/b056_phase0_worker_observability_drift_inventory_evidence.md | Worker observability drift inventory (context-gathering) | pending | pending |
| B0.5.6 Phase 1 | docs/forensics/b056_phase1_drift_eradication_remediation_evidence.md | Worker HTTP sidecar eradication + guardrail | c2fefa4 / deee625 | CI #524 ✅ |
| B0.5.6 Phase 2 | docs/forensics/b056_phase2_health_semantics_remediation_evidence.md | Health semantics remediation evidence (live/ready/worker) | 96f605a | https://github.com/Muk223/skeldir-2.0/actions/runs/21100492747 |
| B0.5.6 Phase 2 EG5 (supporting proof) | docs/forensics/b056_phase2_eg5_probe_safety_ci_proof_evidence.md | Supporting EG5 HTTP cache proof; NOT acceptance authority. See "B0.5.6 Phase 2" row. | 96f605a | https://github.com/Muk223/skeldir-2.0/actions/runs/21100492747 |
| B0.5.6 Phase 2 CI ledger (historical - superseded) | docs/forensics/b056_phase2_health_semantics_ci_ledger_remediation_evidence.md | Historical CI remediation cycle; NOT acceptance authority. See "B0.5.6 Phase 2" row. | 4123168 | https://github.com/Muk223/skeldir-2.0/actions/runs/21099463882 |
| B0.5.6 Phase 2 ledger convergence | docs/forensics/b056_phase2_ledger_closure_convergence_evidence.md | EG7 ledger convergence proof (authoritative INDEX + metadata alignment). | 96f605a | https://github.com/Muk223/skeldir-2.0/actions/runs/21100492747 |
| B0.5.6 Phase 3 | docs/forensics/b056_phase3_metrics_hardening_remediation_evidence.md | Metrics hardening: cardinality/privacy enforcement as tests | 3afd141 | https://github.com/Muk223/skeldir-2.0/actions/runs/21116761325 |
| B0.5.6 Phase 3 CI enforcement | docs/forensics/b056_phase3_ci_enforcement_remediation_evidence.md | Proof that Phase 3 gates execute in CI (selection + logs) | 3afd141 | https://github.com/Muk223/skeldir-2.0/actions/runs/21116761325 |
| B0.5.6 Phase 4 | docs/forensics/b056_phase4_queue_depth_max_age_broker_truth_evidence.md | Queue depth + max age gauges from broker truth (cached) | 1533ef2 | https://github.com/Muk223/skeldir-2.0/actions/runs/21117888714 |
| B0.5.6 Phase 5 | docs/forensics/b056_phase5_task_metrics_topology_no_db_sink_evidence.md | Task metrics topology: exporter-only scrape, no DB sink, parent-owned pruning | 7ffb4e7 | https://github.com/Muk223/skeldir-2.0/actions/runs/21120122342 |
| B0.5.6 Phase 6 | docs/forensics/b056_phase6_structured_worker_logging_remediation_evidence.md | Structured worker lifecycle JSON logs (tenant_id in logs; metrics bounded; runtime proof via subprocess) | 1ce2016 | https://github.com/Muk223/skeldir-2.0/actions/runs/21146810238 |
| B0.5.6 Phase 7 | docs/forensics/b056_phase7_integration_tests_truthful_scrape_targets_evidence.md | Integration tests: truthful scrape targets (exporter vs API) + anti split-brain + privacy labels + health semantics | 829a300 | https://github.com/Muk223/skeldir-2.0/actions/runs/21153690592 |
| B0.5.6 Phase 8 | docs/forensics/b056_phase8_grafana_dashboard_template_evidence.md | Grafana dashboard template (worker throughput/error/latency + broker-truth backlog) + evidence closure | 70c9240 | https://github.com/Muk223/skeldir-2.0/actions/runs/21178399899 |
| B0.5.7 Phase 3 | docs/forensics/b057_phase3_webhook_ingestion_unblocking_evidence.md | Webhook ingestion unblocked under least-privilege runtime DB identity (mediated tenant secrets + CI gate) | 4a00100 | https://github.com/Muk223/skeldir-2.0/actions/runs/21221972452 |
| B0.5.7 Phase 4 | docs/forensics/b057_phase4_llm_audit_persistence_evidence.md | LLM stub audit persistence under RLS (least-privilege runtime) + DLQ failure capture + CI gate | 1a85b87 | https://github.com/Muk223/skeldir-2.0/actions/runs/21254559288 |
| B0.5.7 Phase 5 | docs/forensics/b057_phase5_full_chain_e2e_integration_evidence.md | Full-chain E2E webhook -> tasks -> matview refresh under least-privilege + RLS | 1a7f136 | https://github.com/Muk223/skeldir-2.0/actions/runs/21339065403 |
| B0.5.7 Phase 6 | docs/forensics/b057_phase6_ci_enforcement_governance_cleanup_evidence.md | CI enforcement + governance cleanup (least-privilege E2E, Postgres-only guardrails, INDEX enforcement) | 0a470df0f7b7d480ded10060cd4457955284e8ad | https://github.com/Muk223/skeldir-2.0/actions/runs/21340267507 |
| B0.5.7 Phase 7 | docs/forensics/b057_phase7_operational_readiness_closure_pack_evidence.md | Operational readiness closure pack + governance durability proof | ca485f1db918a5d8764c927189626d17e3093bf2 | https://github.com/Muk223/skeldir-2.0/actions/runs/21363064948 |
| B0.6 Phase 1 context delta | docs/forensics/phase1_context_delta_notes.md | Phase 1 re-validation context delta notes (pre-remediation) | PR #29 / pending | pending |
| B0.6 Phase 1 remediation | docs/forensics/b060_phase1_remediation_evidence_v2.md | Phase 1 remediation evidence pack (auth + tenant boundary) | PR #29 / d95d0fb | https://github.com/Muk223/skeldir-2.0/actions/runs/21411787347 |
| B0.6 Phase 1 remediation (superseded) | docs/forensics/b060_phase1_remediation_evidence.md | Superseded by v2 evidence pack. | PR #29 / d95d0fb | https://github.com/Muk223/skeldir-2.0/actions/runs/21411787347 |
| B0.6 Phase 2 context delta | docs/forensics/phase2_context_delta_notes.md | Phase 2 re-validation context delta notes (pre-remediation) | PR #31 / da40ccd | https://github.com/Muk223/skeldir-2.0/actions/runs/21445442097 |
| B0.6 Phase 2 remediation | docs/forensics/b060_phase2_remediation_evidence_v3.md | Phase 2 remediation evidence pack (mainline merge + required adjudication) | PR #31 / 32c9d17 | https://github.com/Muk223/skeldir-2.0/actions/runs/21449343218 |
| B0.6 Phase 2 remediation (superseded) | docs/forensics/b060_phase2_remediation_evidence_v2.md | Superseded by v3 evidence pack. | PR #31 / da40ccd | https://github.com/Muk223/skeldir-2.0/actions/runs/21445442097 |
| B0.6 Phase 2 remediation (superseded) | docs/forensics/b060_phase2_remediation_evidence.md | Superseded by v3 evidence pack. | PR #31 / da40ccd | https://github.com/Muk223/skeldir-2.0/actions/runs/21445442097 |
| B0.6 Phase 3 context delta | docs/forensics/b060_phase3_context_delta_notes.md | Phase 3 re-validation context delta notes (pre-remediation) | PR #33 / 60f4f6e | https://github.com/Muk223/skeldir-2.0/actions/runs/21452308598 |
| B0.6 Phase 3 context pack | docs/forensics/b06_realtime_revenue_context_pack.md | Realtime revenue baseline + hypotheses + gate status (updated) | PR #33 / 60f4f6e | https://github.com/Muk223/skeldir-2.0/actions/runs/21452308598 |
| B0.6 Phase 3 remediation | docs/forensics/b060_phase3_remediation_evidence.md | Phase 3 remediation evidence pack (cache + singleflight + CI gate) | PR #34 / de72347 | https://github.com/Muk223/skeldir-2.0/actions/runs/21452800838 |
| B0.6 Phase 4 remediation | docs/forensics/b060_phase4_remediation_evidence_v2.md | Phase 4 remediation evidence pack (providers + cache regression + CI gate) | PR #45 / 2b3b304 | https://github.com/Muk223/skeldir-2.0/actions/runs/21602853774 |
| B0.6 Phase 5 remediation | docs/forensics/b060_phase5_remediation_evidence.md | Phase 5 response semantics lock (fetch-time freshness + verified=false + CI gate) | PR pending / 5e1b26c | https://github.com/Muk223/skeldir-2.0/commit/5e1b26c86f941c97d11a9c905fa1efc224af4cce/checks |
| B0.6 Phase 6 context delta | docs/forensics/phase6_context_delta_notes.md | Phase 6 re-validation context delta notes (pre-remediation) | PR #48 / c1a0e3b | https://github.com/Muk223/skeldir-2.0/commit/c1a0e3bbd50895442278a2d0c0df4d8deff0ce1e/checks |
| B0.6 Phase 6 closure | docs/forensics/b060_phase6_closure_evidence.md | Phase 6 E2E integration + operational readiness closure (job-level pass; global CI pending). | 614e1b147eff91dd448cd5708f25b0be90d98aed | https://github.com/Muk223/skeldir-2.0/commit/614e1b147eff91dd448cd5708f25b0be90d98aed/checks |

## Design governance evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| D0 P0 evidence | docs/forensics/D0_P0_EVIDENCE.md | Design system investigation evidence (token naming governance baseline). | PR #48 / c1a0e3b | https://github.com/Muk223/skeldir-2.0/commit/c1a0e3bbd50895442278a2d0c0df4d8deff0ce1e/checks |
| D0 P0 enforcement evidence | docs/forensics/D0_P0_ENFORCEMENT_EVIDENCE.md | Design system enforcement evidence (lint + token validation). | PR #48 / c1a0e3b | https://github.com/Muk223/skeldir-2.0/commit/c1a0e3bbd50895442278a2d0c0df4d8deff0ce1e/checks |

## Root evidence packs
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Pre-exec | docs/forensics/root/PRE_EXECUTION_VALIDATION.md | Pre-execution validation snapshot | unknown (legacy) | unknown |
| B0.5.2 | docs/forensics/root/B0.5.2_Context_Inventory_Baseline.md | Context inventory baseline snapshot | unknown (legacy) | unknown |
| B0.5.2 | docs/forensics/root/B0.5.2_REMEDIATION_EXECUTION_SUMMARY.md | Remediation execution summary | unknown (legacy) | unknown |
| B0542 | docs/forensics/root/B0542_EVIDENCE_CLOSURE_PACK.md | Evidence closure pack | unknown (legacy) | unknown |
| B0543 | docs/forensics/root/B0543_REMEDIATION_EVIDENCE_PACK.md | Remediation evidence pack | unknown (legacy) | unknown |
| B0543 | docs/forensics/root/B0543_REMEDIATION_EVIDENCE_PACK_local_windows.md | Local Windows evidence pack | unknown (legacy) | unknown |
| B0544 | docs/forensics/root/B0544_CONTEXT_DUMP.md | Context dump | unknown (legacy) | unknown |
| B0544 | docs/forensics/root/B0544_EVIDENCE_PACK_local_windows.md | Local Windows evidence pack | unknown (legacy) | unknown |
| B0544 | docs/forensics/root/B0544_PULSE_SCHEDULER_SUMMARY.md | Pulse scheduler summary | unknown (legacy) | unknown |
| B0544 | docs/forensics/root/B0544_REMEDIATION_EVIDENCE_PACK_local_windows_v2.md | Local Windows evidence pack v2 | unknown (legacy) | unknown |
| B0545 | docs/forensics/root/B0545_REMEDIATION_EVIDENCE_v2.md | Remediation evidence v2 | unknown (legacy) | unknown |
| B0.5.7 Archive | docs/forensics/b057_context_gathering_inventory_evidence.md | Restored context-gathering inventory snapshot (pre-remediation). | 0a31d08e | archived |
| B0 | docs/forensics/root/B0_Implementation_Landscape_Local_Windows.md | Implementation landscape snapshot (Windows) | unknown (legacy) | unknown |
| Briefing | docs/forensics/root/DIRECTOR_BRIEFING_VALIDATION_RESULTS.md | Director briefing validation results | unknown (legacy) | unknown |
| Structural | docs/forensics/root/FORENSIC_STRUCTURAL_MAP.md | Structural map | unknown (legacy) | unknown |
| Phase | docs/forensics/root/PHASE_EXECUTION_SUMMARY.md | Phase execution summary | unknown (legacy) | unknown |
| Structural | docs/forensics/root/STRUCTURAL_HYPOTHESES_VALIDATION_REPORT.md | Hypotheses validation report | unknown (legacy) | unknown |
| Structural | docs/forensics/root/STRUCTURAL_INVENTORY_INDEX.md | Structural inventory index | unknown (legacy) | unknown |

## Evidence packs (docs/forensics/evidence)
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| EG-5 | docs/forensics/evidence/EG5_TEMPORAL_PARADOX.md | Temporal paradox gate evidence | unknown (legacy) | unknown |
| B054 | docs/forensics/evidence/b054-forensic-readiness-evidence.md | Forensic readiness evidence | unknown (legacy) | unknown |
| B0540 | docs/forensics/evidence/b0540-drift-remediation-preflight-evidence.md | Drift remediation preflight evidence | unknown (legacy) | unknown |
| B0540 | docs/forensics/evidence/b0540_ci_truthlayer_evidence.md | CI truth layer evidence | unknown (legacy) | unknown |
| B0541 | docs/forensics/evidence/b0541_soundness_readiness_evidence.md | Soundness readiness evidence | unknown (legacy) | unknown |
| B055 | docs/forensics/evidence/b055/b055_phase3_worker_stubs_evidence.md | Phase 3 worker stubs + ORM audit evidence | PR #17 / f03b8bc | pending |
| B0 | docs/forensics/evidence/b0_foundation_chain_green_state.md | Foundation chain green state | unknown (legacy) | unknown |
| B0 | docs/forensics/evidence/b0_system_phase_soundness_audit.md | System phase soundness audit | unknown (legacy) | unknown |
| Contract | docs/forensics/evidence/schema_contract_guard_evidence.md | Schema contract guard evidence | unknown (legacy) | unknown |
| Proof pack | docs/forensics/evidence/value_trace_proof_pack.md | Value trace proof pack | unknown (legacy) | unknown |

## Evidence value traces
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| VALUE_01 | docs/forensics/evidence/value_traces/value_01_revenue_trace.md | Value trace report | unknown (legacy) | unknown |
| VALUE_02 | docs/forensics/evidence/value_traces/value_02_constraint_trace.md | Value trace report | unknown (legacy) | unknown |
| VALUE_03 | docs/forensics/evidence/value_traces/value_03_provider_handshake.md | Value trace report | unknown (legacy) | unknown |
| VALUE_04 | docs/forensics/evidence/value_traces/value_04_registry_trace.md | Value trace report | unknown (legacy) | unknown |

## Backend evidence packs
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Backend B0.4 | docs/forensics/backend/B0.4 Local Codebase Context Report - Backend Engineer.md | Backend context report | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_Celery_Foundation_Execution_Summary.md | Celery foundation execution summary | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_Celery_Runbook.md | Celery runbook | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_EMPIRICAL_COMPLETION_EVIDENCE.md | Empirical completion evidence | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_EXECUTION_SUMMARY.md | Execution summary | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_Foundation_Forensic_Assessment.md | Foundation forensic assessment | unknown (legacy) | unknown |
| Backend B0.5.1 | docs/forensics/backend/B0.5.1_VALIDATION_STATUS_REPORT.md | Validation status report | unknown (legacy) | unknown |
| Backend B0.5.3 | docs/forensics/backend/B0.5.3.3_EXECUTIVE_SUMMARY.md | Executive summary | unknown (legacy) | unknown |
| Backend B0.5.3 | docs/forensics/backend/B0.5.3_attribution_worker_notes.md | Attribution worker notes | unknown (legacy) | unknown |
| Backend B0431 | docs/forensics/backend/B0431_REMEDIATION_SUMMARY.md | Remediation summary | unknown (legacy) | unknown |
| Backend B0431 | docs/forensics/backend/B0431_REMEDIATION_SUMMARY_FINAL.md | Remediation summary (final) | unknown (legacy) | unknown |
| Backend B043 | docs/forensics/backend/B043_COMPLETE_TECHNICAL_SUMMARY.md | Technical summary | unknown (legacy) | unknown |
| Backend B043 | docs/forensics/backend/B043_EXECUTION_SUMMARY.md | Execution summary | unknown (legacy) | unknown |
| Backend B044 | docs/forensics/backend/B044_EXECUTION_SUMMARY.md | Execution summary | unknown (legacy) | unknown |
| Backend B046 | docs/forensics/backend/B046_EXECUTION_SUMMARY.md | Execution summary | unknown (legacy) | unknown |
| Backend B0531 | docs/forensics/backend/b0531-queue-routing-dlq-evidence.md | Queue routing evidence | unknown (legacy) | unknown |
| Backend B0531 | docs/forensics/backend/B0531_GAP_CLOSURE_EXECUTION_SUMMARY.md | Gap closure execution summary | unknown (legacy) | unknown |
| Backend B0533 | docs/forensics/backend/B0533_EXECUTION_SUMMARY.md | Execution summary | unknown (legacy) | unknown |
| Backend B0533 | docs/forensics/backend/b0533_revenue_input_evidence.md | Revenue input evidence | unknown (legacy) | unknown |
| Backend B0533 | docs/forensics/backend/b0533_revenue_ledger_schema_ground_truth.md | Revenue ledger schema ground truth | unknown (legacy) | unknown |
| Backend B0534 | docs/forensics/backend/B0534_WORKER_TENANT_ISOLATION_EVIDENCE.md | Worker tenant isolation evidence | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_BASELINE.md | Celery forensics baseline | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_BINARY_QUESTIONS.md | Celery forensics binary questions | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_FAILURE_TAXONOMY.md | Celery forensics failure taxonomy | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_IMPACT.md | Celery forensics impact | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_LOCAL_REPRO.md | Celery forensics local repro | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_1_CELERY_FORENSICS_RUN_INVENTORY.md | Celery forensics run inventory | unknown (legacy) | unknown |
| Backend B0535 | docs/forensics/backend/B0535_READONLY_INGESTION_EVIDENCE.md | Readonly ingestion evidence | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_1_ASYNC_GUC_FIX_EVIDENCE.md | Async GUC fix evidence | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_1_FOUNDATION_RECOVERY_EVIDENCE.md | Foundation recovery evidence | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_DETERMINISTIC_TEST_VECTOR.md | Deterministic test vector | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_E2E_EVIDENCE.md | E2E evidence | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_E2E_HARNESS_TOPOLOGY.md | E2E harness topology | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_IDEMPOTENCY_BASELINE.md | Idempotency baseline | unknown (legacy) | unknown |
| Backend B0536 | docs/forensics/backend/B0536_PIPELINE_TRACE.md | Pipeline trace | unknown (legacy) | unknown |
| Backend B0541 | docs/forensics/backend/B0541_VIEW_REGISTRY_SUMMARY.md | View registry summary | unknown (legacy) | unknown |
| Backend B0542 | docs/forensics/backend/B0542_REFRESH_EXECUTOR_SUMMARY.md | Refresh executor summary | unknown (legacy) | unknown |
| Backend B0543 | docs/forensics/backend/B0543_TASK_LAYER_SUMMARY.md | Task layer summary | unknown (legacy) | unknown |
| Backend B0543 | docs/forensics/backend/GH_ANALYSIS_B0543_VALIDATION.md | GH analysis validation | unknown (legacy) | unknown |

## Backend API + runbooks
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Backend B0.4 | docs/forensics/backend/api/B0.4_INGESTION_SERVICE.md | Ingestion service reference | unknown (legacy) | unknown |
| Backend B0.4 | docs/forensics/backend/runbooks/B0.4_INGESTION_TROUBLESHOOTING.md | Ingestion troubleshooting runbook | unknown (legacy) | unknown |

## Backend validation evidence packs
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Validation | docs/forensics/backend/validation/EMPIRICAL_CHAIN.md | Phase gate chain snapshot | unknown (legacy) | unknown |
| Validation | docs/forensics/backend/validation/EMPIRICAL_VALIDATION_STATUS.md | Validation status | unknown (legacy) | unknown |
| Validation | docs/forensics/backend/validation/MANIFEST.md | Evidence manifest | unknown (legacy) | unknown |
| Validation | docs/forensics/backend/validation/REMEDIATION_FINAL_STATUS.md | Remediation final status | unknown (legacy) | unknown |

## Convergence evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Convergence B0.2 | docs/forensics/convergence/B0.2/backend_evidence.md | Convergence backend evidence | unknown (legacy) | unknown |
| Convergence B0.2 | docs/forensics/convergence/B0.2/CI_ORCHESTRATOR_STATUS.md | CI orchestrator status | unknown (legacy) | unknown |

## Validation runtime evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Runtime | docs/forensics/validation/runtime/context_gathering_summary.md | Runtime context gathering summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r0_preflight_summary.md | R0 preflight summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r1_summary.md | R1 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/R2_EXECUTION_SUMMARY.md | R2 execution summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r2_summary.md | R2 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r3_summary.md | R3 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r4_summary.md | R4 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r5_context_gathering_summary.md | R5 context gathering summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r5_summary.md | R5 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r6_summary.md | R6 summary | unknown (legacy) | unknown |
| Runtime | docs/forensics/validation/runtime/r7_summary.md | R7 summary | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_GAP_REPORT.md | R6 gap report | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/2b0236c802b0017a50c93903c330e23d49078013/R6_TASK_GOVERNANCE_MATRIX.md | R6 task governance matrix | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/540b1eab47622080a2d4447e674af8d7b3c6b0b6/R6_GAP_REPORT.md | R6 gap report | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/540b1eab47622080a2d4447e674af8d7b3c6b0b6/R6_TASK_GOVERNANCE_MATRIX.md | R6 task governance matrix | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/c7abcf220dc96f0029baa701341b1e6def10cbb5/R6_GAP_REPORT.md | R6 gap report | unknown (legacy) | unknown |
| Runtime R6 | docs/forensics/validation/runtime/R6_context_gathering/c7abcf220dc96f0029baa701341b1e6def10cbb5/R6_TASK_GOVERNANCE_MATRIX.md | R6 task governance matrix | unknown (legacy) | unknown |

## Archive evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Archive | docs/forensics/archive/ARCHITECTURAL_GAPS_REMEDIATION.md | Legacy remediation record | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/BUNDLING_MANIFEST_FIX.md | Bundling manifest fix | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/CONTRACT_ARTIFACTS_README.md | Contract artifacts archive | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/CONTRACT_ENFORCEMENT_SUMMARY.md | Contract enforcement summary | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/EMPIRICAL_VALIDATION_ACTION_PLAN.md | Empirical validation action plan | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/FRONTEND_IMPLEMENTATION_SPECIFICATION.md | Frontend implementation specification | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/FUNCTIONAL_REQUIREMENTS_FORENSIC_ANALYSIS.md | Functional requirements forensic analysis | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/IMPLEMENTATION_COMPLETE.md | Implementation complete record | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/INVESTIGATORY_ANSWERS.md | Investigatory answers | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/OPERATIONAL_GATES_IMPLEMENTATION_COMPLETE.md | Operational gates implementation complete | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/OPERATIONAL_VALIDATION_REPORT.md | Operational validation report | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/PHASE_EXIT_GATE_STATUS_MATRIX.md | Phase exit gate status matrix | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/PYDANTIC_PIPELINE_IMPLEMENTATION_SUMMARY.md | Pydantic pipeline implementation summary | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/README.md | Archive index | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/REMEDIATION_EXECUTIVE_SUMMARY.md | Remediation executive summary | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/REPLIT_BASELINE_VALIDATION.md | Replit baseline validation | unknown (legacy) | unknown |
| Archive | docs/forensics/archive/completed-phases/B0.1-B0.3_EVALUATION_ANSWERS.md | Completed phase evaluation answers | unknown (legacy) | unknown |
| Archive B0.1 | docs/forensics/archive/completed-phases/b0.1/B0.1_API_CONTRACT_DEFINITION_EVALUATION.md | API contract definition evaluation | unknown (legacy) | unknown |
| Archive B0.1 | docs/forensics/archive/completed-phases/b0.1/B0.1_EMPIRICAL_SUBSTANTIATION_RESPONSE.md | Empirical substantiation response | unknown (legacy) | unknown |
| Archive B0.1 | docs/forensics/archive/completed-phases/b0.1/B0.1_PHASE_FORENSIC_EVALUATION_RESPONSE.md | Phase forensic evaluation response | unknown (legacy) | unknown |
| Archive B0.3 | docs/forensics/archive/completed-phases/b0.3/B0.3_FORENSIC_ANALYSIS_ANSWERS.md | Forensic analysis answers | unknown (legacy) | unknown |
| Archive B0.3 | docs/forensics/archive/completed-phases/b0.3/B0.3_FORENSIC_ANALYSIS_BILLY_ALEX.md | Forensic analysis (Billy/Alex) | unknown (legacy) | unknown |
| Archive B0.3 | docs/forensics/archive/completed-phases/b0.3/B0.3_FORENSIC_ANALYSIS_COMPLETE.md | Forensic analysis complete | unknown (legacy) | unknown |
| Archive B0.3 | docs/forensics/archive/completed-phases/b0.3/B0.3_FORENSIC_ANALYSIS_RESPONSE.md | Forensic analysis response | unknown (legacy) | unknown |

## Deployment + implementation evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Deployment | docs/forensics/deployment/GITHUB_DEPLOYMENT_SUMMARY.md | Deployment summary | unknown (legacy) | unknown |
| Implementation | docs/forensics/implementation/contract-enforcement-validation-report.md | Contract enforcement validation report | unknown (legacy) | unknown |

## DB evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| DB B0.4 | docs/forensics/db/B0.4_BASELINE_CONTEXT_SYNTHESIS.md | DB baseline context synthesis | unknown (legacy) | unknown |

## Legacy artifact evidence (artifacts_vt_run3)
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| VALUE_01 | docs/forensics/artifacts_vt_run3/phase-VALUE_01/EMPIRICAL_CHAIN.md | Empirical chain snapshot | unknown (legacy) | unknown |
| VALUE_01 | docs/forensics/artifacts_vt_run3/phase-VALUE_01/EMPIRICAL_VALIDATION_STATUS.md | Validation status | unknown (legacy) | unknown |
| VALUE_01 | docs/forensics/artifacts_vt_run3/phase-VALUE_01/MANIFEST.md | Evidence manifest | unknown (legacy) | unknown |
| VALUE_01 | docs/forensics/artifacts_vt_run3/phase-VALUE_01/REMEDIATION_FINAL_STATUS.md | Remediation final status | unknown (legacy) | unknown |
| VALUE_02 | docs/forensics/artifacts_vt_run3/phase-VALUE_02/EMPIRICAL_CHAIN.md | Empirical chain snapshot | unknown (legacy) | unknown |
| VALUE_02 | docs/forensics/artifacts_vt_run3/phase-VALUE_02/EMPIRICAL_VALIDATION_STATUS.md | Validation status | unknown (legacy) | unknown |
| VALUE_02 | docs/forensics/artifacts_vt_run3/phase-VALUE_02/MANIFEST.md | Evidence manifest | unknown (legacy) | unknown |
| VALUE_02 | docs/forensics/artifacts_vt_run3/phase-VALUE_02/REMEDIATION_FINAL_STATUS.md | Remediation final status | unknown (legacy) | unknown |
| VALUE_03 | docs/forensics/artifacts_vt_run3/phase-VALUE_03/EMPIRICAL_CHAIN.md | Empirical chain snapshot | unknown (legacy) | unknown |
| VALUE_03 | docs/forensics/artifacts_vt_run3/phase-VALUE_03/EMPIRICAL_VALIDATION_STATUS.md | Validation status | unknown (legacy) | unknown |
| VALUE_03 | docs/forensics/artifacts_vt_run3/phase-VALUE_03/MANIFEST.md | Evidence manifest | unknown (legacy) | unknown |
| VALUE_03 | docs/forensics/artifacts_vt_run3/phase-VALUE_03/REMEDIATION_FINAL_STATUS.md | Remediation final status | unknown (legacy) | unknown |
| VALUE_04 | docs/forensics/artifacts_vt_run3/phase-VALUE_04/EMPIRICAL_CHAIN.md | Empirical chain snapshot | unknown (legacy) | unknown |
| VALUE_04 | docs/forensics/artifacts_vt_run3/phase-VALUE_04/EMPIRICAL_VALIDATION_STATUS.md | Validation status | unknown (legacy) | unknown |
| VALUE_04 | docs/forensics/artifacts_vt_run3/phase-VALUE_04/MANIFEST.md | Evidence manifest | unknown (legacy) | unknown |
| VALUE_04 | docs/forensics/artifacts_vt_run3/phase-VALUE_04/REMEDIATION_FINAL_STATUS.md | Remediation final status | unknown (legacy) | unknown |

## Proof pack (CI-generated)
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| EG-5 | docs/forensics/proof_pack/value_trace_proof_pack.md | CI-generated proof pack (human-readable) | CI-generated | CI-generated |

# Forensics Evidence Index

This index enumerates evidence packs stored under `docs/forensics/`.

## Hygiene
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
| Hygiene | docs/forensics/evidence_hygiene_remediation_evidence.md | Evidence hygiene remediation proof pack | PR #15 / fa5d30c | pending |

## Phase remediation evidence
| Phase/Topic | Evidence pack | Purpose | PR/Commit | CI Run |
| --- | --- | --- | --- | --- |
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
| B0.6 Phase 5 remediation | docs/forensics/b060_phase5_remediation_evidence.md | Phase 5 response semantics lock (fetch-time freshness + verified=false + CI gate) | PR pending / 5e1b26c | https://github.com/Muk223/skeldir-2.0/commit/5e1b26c58bcd7dfb6b7c9bc0f6e6efc9f32a2a7d/checks |

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

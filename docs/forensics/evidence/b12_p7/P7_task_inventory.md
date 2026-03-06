# P7 Task Inventory

Generated from `main` code in `backend/app/tasks`.

## Classification Ledger

| Task Name | Module | Queue | Class | Envelope Enforcement | DB Touchpoint Summary |
|---|---|---|---|---|---|
| app.tasks.attribution.recompute_window | app/tasks/attribution.py | attribution | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Reads `attribution_events`; writes `attribution_recompute_jobs`, `attribution_allocations` |
| app.tasks.llm.route | app/tasks/llm.py | llm | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Uses tenant-bound session; LLM audit/storage path |
| app.tasks.llm.explanation | app/tasks/llm.py | llm | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Uses tenant-bound session |
| app.tasks.llm.investigation | app/tasks/llm.py | llm | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Uses tenant-bound session |
| app.tasks.llm.budget_optimization | app/tasks/llm.py | llm | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Uses tenant-bound session |
| app.tasks.maintenance.refresh_matview_for_tenant | app/tasks/maintenance.py | maintenance | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Tenant-specific matview refresh |
| app.tasks.maintenance.scan_for_pii_contamination | app/tasks/maintenance.py | maintenance | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Tenant-bound DB connectivity + scan stub |
| app.tasks.maintenance.enforce_data_retention | app/tasks/maintenance.py | maintenance | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Deletes tenant-scoped mutable data |
| app.tasks.matviews.refresh_single | app/tasks/matviews.py | maintenance | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Tenant matview refresh pipeline |
| app.tasks.matviews.refresh_all_for_tenant | app/tasks/matviews.py | maintenance | TENANT_SCOPED | `TenantTask` + `AuthorityEnvelope` | Tenant matview refresh fanout |
| app.tasks.health.probe | app/tasks/health.py | housekeeping | GLOBAL_OBSERVABILITY | N/A | Read-only probe |
| app.tasks.housekeeping.ping | app/tasks/housekeeping.py | housekeeping | GLOBAL_OBSERVABILITY | N/A | Read-only probe |
| app.tasks.matviews.pulse_matviews_global | app/tasks/matviews.py | maintenance | GLOBAL_MAINTENANCE | N/A | Reads tenants; enqueues tenant tasks with `SystemContext` |
| app.tasks.maintenance.scan_for_pii_contamination_all_tenants | app/tasks/maintenance.py | maintenance | GLOBAL_MAINTENANCE | N/A | Reads tenants; enqueues tenant tasks with `SystemContext` |
| app.tasks.maintenance.enforce_data_retention_all_tenants | app/tasks/maintenance.py | maintenance | GLOBAL_MAINTENANCE | N/A | Reads tenants; enqueues tenant tasks with `SystemContext` |
| app.tasks.maintenance.gc_expired_access_token_denylist | app/tasks/maintenance.py | maintenance | GLOBAL_MAINTENANCE | N/A | Tenant-iterative denylist cleanup (internal system operation) |
| app.tasks.maintenance.refresh_all_matviews_global_legacy | app/tasks/maintenance.py | maintenance | GLOBAL_MAINTENANCE (legacy) | N/A | Legacy global matview refresh path |
| app.tasks.r4_failure_semantics.* | app/tasks/r4_failure_semantics.py | housekeeping | GLOBAL_OBSERVABILITY (adversarial harness) | N/A | Test harness writes/reads probe tables |
| app.tasks.r6_resource_governance.* | app/tasks/r6_resource_governance.py | housekeeping/maintenance | GLOBAL_OBSERVABILITY | N/A | Diagnostics only |

## Tenant Enqueue Call-Site Map (Production Code)

| Call Site | Task | Path | Envelope |
|---|---|---|---|
| `enqueue_tenant_task(...)` | recompute_window | app/services/attribution.py | `SystemContext` |
| `enqueue_tenant_task(...)` | llm.* | app/services/llm_dispatch.py | `SessionContext` when `jti/iat` present, otherwise `SystemContext` |
| `tenant_task_signature(...)` + chain | recompute_window -> matview_refresh_all_for_tenant | app/api/webhooks.py | `SystemContext` |
| `enqueue_tenant_task(...)` | matview_refresh_all_for_tenant | app/tasks/matviews.py (pulse fanout) | `SystemContext` |
| `enqueue_tenant_task(...)` | scan_for_pii_contamination | app/tasks/maintenance.py (all-tenant fanout) | `SystemContext` |
| `enqueue_tenant_task(...)` | enforce_data_retention | app/tasks/maintenance.py (all-tenant fanout) | `SystemContext` |

## Producer Bypass Guard

- Direct `.delay()`/`.apply_async()` on tenant task symbols in `backend/app` is blocked by `backend/tests/test_b12_p7_enqueue_and_envelope.py::test_no_direct_delay_or_apply_async_for_tenant_tasks_in_app_code`.
- Canonical choke-point module: `backend/app/tasks/enqueue.py`.

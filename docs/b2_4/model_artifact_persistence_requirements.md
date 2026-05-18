# B2.4 Model Artifact Persistence Requirements

## Scope

This is a design contract for future migrations. M5 does not add tables, migrations, SQLAlchemy models, or production persistence code.

## `bayesian_model_fits`

Required fields:

- `id UUID PRIMARY KEY`.
- `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`.
- `correlation_id UUID NOT NULL`.
- `model_type TEXT NOT NULL`.
- `model_version TEXT NOT NULL`.
- `status TEXT NOT NULL`.
- `fallback_reason TEXT NULL`.
- `fallback_applied BOOLEAN NOT NULL DEFAULT false`.
- `source_window_start TIMESTAMPTZ NOT NULL`.
- `source_window_end TIMESTAMPTZ NOT NULL`.
- `source_snapshot_hash TEXT NOT NULL`.
- `eligibility_status TEXT NOT NULL`.
- `minimum_event_count_required INTEGER NOT NULL`.
- `minimum_matched_revenue_event_count_required INTEGER NOT NULL`.
- `observed_event_count INTEGER NOT NULL`.
- `observed_matched_revenue_event_count INTEGER NOT NULL`.
- `sampling_started_at TIMESTAMPTZ NULL`.
- `last_fit_at TIMESTAMPTZ NULL`.
- `completed_at TIMESTAMPTZ NULL`.
- `compute_refit_locked_until TIMESTAMPTZ NULL`.
- `eligibility_retry_after TIMESTAMPTZ NULL`.
- `task_id TEXT NULL`.
- `attempt_count INTEGER NOT NULL DEFAULT 0`.
- `runtime_ms INTEGER NULL`.
- `timeout_seconds INTEGER NULL`.
- `r_hat_max NUMERIC NULL`.
- `ess_min INTEGER NULL`.
- `divergences INTEGER NULL`.
- `hdi_probability NUMERIC NULL`.
- `credible_interval_status TEXT NOT NULL`.
- `diagnostic_payload JSONB NOT NULL DEFAULT '{}'::jsonb`.
- `error_class TEXT NULL`.
- `error_code TEXT NULL`.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

Status constraints:

- `status IN ('eligibility_checked','queued','running','converged','fallback_only','failed','aborted')`.
- `credible_interval_status IN ('available','unavailable','failed_diagnostics','not_applicable','suppressed')`.
- `fallback_reason` constrained to the diagnostic protocol enum when present.

Critical constraints:

- `source_window_end > source_window_start`.
- `source_snapshot_hash` is non-empty SHA-256 hex.
- `converged` requires `r_hat_max < 1.01`, `ess_min > 400`, `divergences = 0`, `credible_interval_status='available'`, and at least one artifact row.
- `fallback_only` requires `fallback_applied=true` and non-null `fallback_reason`.
- `fallback_only/insufficient_data` requires `sampling_started_at IS NULL`, `last_fit_at IS NULL`, and `compute_refit_locked_until IS NULL`.
- `last_fit_at` is set only when sampling starts.

Indexes:

- `(tenant_id, created_at DESC)`.
- `(tenant_id, status, created_at DESC)`.
- `(tenant_id, model_type, source_window_end DESC)`.
- Unique or partial uniqueness over `(tenant_id, model_type, model_version, source_snapshot_hash)` for completed/converged fits as implementation requires.

## `bayesian_artifacts`

Required fields:

- `id UUID PRIMARY KEY`.
- `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`.
- `model_fit_id UUID NOT NULL REFERENCES bayesian_model_fits(id) ON DELETE CASCADE`.
- `artifact_type TEXT NOT NULL`.
- `artifact_ref TEXT NOT NULL`.
- `artifact_hash TEXT NOT NULL`.
- `storage_backend TEXT NOT NULL`.
- `content_type TEXT NOT NULL`.
- `byte_size INTEGER NOT NULL`.
- `canonicalization_version TEXT NOT NULL`.
- `source_snapshot_hash TEXT NOT NULL`.
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`.

Artifact types:

- `inference_data`.
- `diagnostic_summary`.
- `model_spec_snapshot`.
- `source_snapshot_manifest`.
- `posterior_summary`.

Storage backend governed enum:

- `postgres_jsonb`.
- `postgres_large_object`.
- `object_store`.
- `local_artifact_store`.

Initial B2.4 should prefer `postgres_jsonb` for small summaries and `local_artifact_store` only in local/dev proofs. Production object storage must not be introduced without a resolver and access-control decision record.

Artifact requirements:

- `artifact_ref` is stable and resolver-owned, formatted as `b24://{tenant_id}/{model_fit_id}/{artifact_type}/{artifact_hash}` unless a later resolver ADR replaces it.
- `artifact_hash` is SHA-256 over canonical artifact payload bytes.
- `artifact_hash` must be non-null for any converged fit.
- `source_snapshot_hash` must match the parent fit.
- `(tenant_id, artifact_ref)` is unique.

## Resolver Contract

The artifact resolver must:

- Require tenant context before resolution.
- Validate `artifact_hash` after loading payload.
- Reject cross-tenant artifact refs.
- Return typed payload metadata without exposing storage credentials.
- Treat missing artifacts as `artifact_persistence_failure` for convergence.

## RLS/GUC Expectations

Both tables must:

- Include `tenant_id UUID NOT NULL`.
- Enable row-level security.
- Define policy `USING (tenant_id = current_setting('app.current_tenant_id')::UUID)`.
- Be validated under runtime app user with missing-context negative control.
- Be reflected in `db/schema/canonical_schema.sql` after migration.

## Migration Expectations

Future migration must be reversible, deterministic, and branch-sequenced through existing Alembic conventions. It must update canonical schema reflection and include validators proving table existence, constraints, indexes, RLS, GUC enforcement, artifact ref stability, and cold-start no-lock behavior.

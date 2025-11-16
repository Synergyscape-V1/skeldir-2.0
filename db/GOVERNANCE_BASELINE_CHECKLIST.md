# Governance Baseline Checklist

This document lists all repo artifacts, config docs, and team protocols required for B0.3 governance baseline completion.

## Phase 0: Ownership, Layout, and ADRs

- [x] `/db/` directory structure created (12 subdirectories)
- [x] `db/OWNERSHIP.md` - Ownership map with owner assignments
- [x] `db/docs/adr/ADR-001-schema-source-of-truth.md` - Schema source-of-truth ADR
- [x] `db/docs/adr/ADR-002-migration-discipline.md` - Migration discipline ADR
- [x] All `.gitkeep` files created for empty directories

## Phase 1: Migration System Initialization

- [x] `alembic.ini` - Alembic configuration (parameterized, no hardcoded credentials)
- [x] `alembic/env.py` - Environment configuration (reads DATABASE_URL from env)
- [x] `alembic/script.py.mako` - Migration template
- [x] `alembic/versions/202511121302_baseline.py` - Baseline migration (empty DDL)
- [x] `db/docs/MIGRATION_SYSTEM.md` - Migration system documentation
- [x] `db/migrations/templates/versioned_migration.py.template` - Versioned migration template
- [x] `db/migrations/templates/repeatable_migration.py.template` - Repeatable migration template
- [x] `.env.example` - Environment variable template (DATABASE_URL placeholder)

## Phase 2: Schema Style Guide & Linting

- [x] `db/docs/SCHEMA_STYLE_GUIDE.md` - Complete style guide with all conventions
- [x] `db/docs/DDL_LINT_RULES.md` - Complete lint rules with examples
- [x] `db/docs/examples/example_table_ddl.sql` - Example DDL demonstrating all rules

## Phase 3: Contract→Schema Mapping Rulebook

- [x] `db/docs/CONTRACT_TO_SCHEMA_MAPPING.md` - Complete mapping rulebook
- [x] `db/docs/contract_schema_mapping.yaml` - Machine-readable mapping skeleton
- [x] `db/docs/examples/realtime_revenue_mapping_example.md` - Worked example mapping

## Phase 4: Extension Allow-List & Initialization Policy

- [x] `db/docs/EXTENSION_ALLOWLIST.md` - Extension allow-list with names and rationale
- [x] `db/migrations/templates/enable_extension.py.template` - Extension enablement template

## Phase 5: Roles, Grants, and RLS Template

- [x] `db/docs/ROLES_AND_GRANTS.md` - Role model with least-privilege matrix
- [x] `db/migrations/templates/rls_policy.py.template` - RLS macro template
- [x] `db/docs/examples/rls_application_example.sql` - Example RLS application

## Phase 6: Environment Safety & Migration Guardrails

- [x] `db/docs/MIGRATION_SAFETY_CHECKLIST.md` - Complete safety checklist (timeouts, backfill playbook)
- [x] `.env.example` - Updated with migration-related vars

## Phase 7: Schema Snapshots & Drift Detection

- [x] `db/docs/SCHEMA_SNAPSHOTS.md` - Snapshot format and process documentation
- [x] `db/snapshots/.gitkeep` - Snapshots directory
- [x] `.github/workflows/schema-drift-check.yml` - CI job spec (commented, not active)

## Phase 8: Documentation, PR Gates, and Review Checklists

- [x] `db/docs/DATA_DICTIONARY_GUIDE.md` - Data dictionary guide
- [x] `db/docs/ERD_POLICY.md` - ERD policy
- [x] `.github/PULL_REQUEST_TEMPLATE/schema-migration.md` - PR checklist template
- [x] `db/docs/data_dictionary/.gitkeep` - Data dictionary directory
- [x] `db/docs/erd/.gitkeep` - ERD directory

## Phase 9: Seed/Fixture Governance

- [x] `db/docs/SEEDING_POLICY.md` - Seeding policy (PII exclusion, tenant scoping, B0.2 alignment)
- [x] `db/seeds/.gitkeep` - Seeds directory
- [x] `db/seeds/templates/seed_template.sql.template` - Seed template

## Phase 10: Traceability & Commenting Standard

- [x] `db/docs/TRACEABILITY_STANDARD.md` - Traceability standard (correlation_id, actor_*)
- [x] `db/docs/examples/comment_examples.sql` - Comment examples
- [x] `db/docs/SCHEMA_STYLE_GUIDE.md` - Updated with comment standard

## Phase 11: Final Aggregate Consolidation & Exemplar DDL

- [x] `db/docs/examples/hypothetical_table_exemplar.sql` - Exemplar DDL demonstrating all governance rules
- [x] `db/GOVERNANCE_BASELINE_CHECKLIST.md` - This checklist
- [ ] `db/docs/GOVERNANCE_BASELINE_READINESS.md` - Readiness record (to be created)

## Global Minimum Requirements

- [x] Migration system: Tool chosen (Alembic), baseline stamped, templates documented
- [x] Style & mapping: Guides complete, machine-readable skeleton present
- [x] Security posture: Extension allow-list (names + rationale), roles/GRANTs matrix, RLS macro template ready
- [x] Safety: Migration safety checklist (timeouts/backfill playbook), approval matrix defined
- [x] Integrity: Snapshot spec, drift detection, ignore rules documented
- [x] Legibility: ERD policy, data dictionary guide, comment standard mandated
- [x] Process: PR checklist enforces all rules, seeding policy defined
- [x] Exemplar DDL: Non-applied exemplar demonstrates all governance rules working together

## Sign-Offs Required

- [ ] Backend Lead approval
- [ ] Frontend Lead approval (for contract mapping alignment)
- [ ] Product Owner approval

---

**Status**: Governance baseline artifacts complete. Awaiting sign-offs.






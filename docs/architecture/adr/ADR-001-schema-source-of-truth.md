# ADR-001: Schema Source-of-Truth

**Status**: Accepted  
**Date**: 2025-11-10  
**Deciders**: Backend Lead, Product Owner

## Context

Skeldir requires a single source of truth for database schema to ensure:
- Contract-faithful implementation (B0.1 OpenAPI contracts drive schema design)
- Reproducible environments (schema versioning enables deterministic deployments)
- Auditability (all schema changes are tracked and reviewable)
- Team alignment (clear ownership and review process)

Currently, no database schema exists (B0.3 not implemented). We need to establish governance baseline before implementing any domain tables.

## Decision

**The database schema is the canonical source of truth for data persistence.**

Key principles:
1. **Contracts Drive Schema**: OpenAPI contracts (B0.1) define the canonical API shape; database schema must faithfully implement contract requirements
2. **No Out-of-Band Changes**: All schema changes must go through migration system; manual DDL is forbidden
3. **Contract→Schema Traceability**: Every database table/column must be traceable to an OpenAPI contract requirement or architectural decision
4. **Versioned Schema**: All schema changes are versioned through Alembic migrations
5. **Reviewable Changes**: All migrations require peer review and approval

## Consequences

### Positive
- Single source of truth eliminates schema drift
- Contract-first approach ensures API and database alignment
- Versioned migrations enable rollback and reproducibility
- Review process ensures quality and compliance

### Negative
- Additional overhead for schema changes (migration process, review)
- Requires discipline to avoid out-of-band changes
- Initial setup requires governance baseline establishment

### Tradeoffs
- **Simplicity vs. Governance**: We choose governance overhead to prevent schema drift and ensure contract compliance
- **Speed vs. Safety**: We choose safety (review process) over speed (direct DDL changes)

## Contract→Schema Traceability Requirement

All database schema objects must be traceable to:
1. **OpenAPI Contract Requirements**: Tables/columns that implement contract response objects
2. **Architectural Decisions**: Schema objects required by architectural patterns (e.g., RLS for tenant isolation)
3. **Operational Requirements**: Schema objects for observability, auditability, or operational needs

Traceability is documented through:
- Migration comments linking to contract files
- Data dictionary entries referencing contract schemas
- ADRs documenting architectural schema decisions

---

**Approved By**:
- Backend Lead: [Signature/Date]
- Product Owner: [Signature/Date]





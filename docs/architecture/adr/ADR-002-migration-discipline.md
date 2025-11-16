# ADR-002: Migration Discipline

**Status**: Accepted  
**Date**: 2025-11-10  
**Deciders**: Backend Lead, Product Owner

## Context

Database schema changes must be:
- Reproducible across environments (dev, staging, production)
- Reversible (rollback capability)
- Reviewable (peer review process)
- Traceable (version history)

Without a disciplined migration process, we risk:
- Schema drift between environments
- Unreviewed changes causing production issues
- Inability to rollback problematic changes
- Loss of schema change history

## Decision

**All database schema changes must use the migration system. Manual DDL is forbidden.**

Key principles:
1. **Forbids Manual DDL**: No direct database changes allowed; all changes must go through Alembic migrations
2. **Mandates Migration Flow**: All schema changes follow: Create migration → Review → Approve → Apply
3. **Defines Review Process**: All migrations require peer review and approval before application
4. **Enforces Rollback**: All migrations must include reversible downgrade operations
5. **Requires Documentation**: All migrations must include comments explaining the change and rationale

## Consequences

### Positive
- Reproducible schema changes across all environments
- Rollback capability for problematic changes
- Review process catches issues before production
- Complete audit trail of schema evolution

### Negative
- Additional overhead for schema changes (migration creation, review)
- Requires discipline to avoid manual DDL
- Slower change velocity compared to direct DDL

### Tradeoffs
- **Speed vs. Safety**: We choose safety (review process) over speed (direct DDL)
- **Flexibility vs. Discipline**: We choose discipline (migration flow) over flexibility (ad-hoc changes)

## Review Process

1. **Create Migration**: Developer creates Alembic migration with required changes
2. **Self-Review**: Developer verifies migration follows style guide and governance rules
3. **Peer Review**: Another developer reviews migration for correctness and compliance
4. **Approval**: Backend Lead approves migration for application
5. **Apply**: Migration is applied to target environment (dev → staging → production)

## Migration Requirements

All migrations must:
- Include descriptive comments explaining the change
- Be reversible (include downgrade operation)
- Follow style guide conventions
- Include contract mapping rationale (if applicable)
- Pass lint rules and validation checks

---

**Approved By**:
- Backend Lead: [Signature/Date]
- Product Owner: [Signature/Date]





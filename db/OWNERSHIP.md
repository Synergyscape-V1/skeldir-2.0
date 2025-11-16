# Database Governance Ownership Map

This document defines ownership and review responsibilities for all database governance artifacts.

## Directory Ownership

| Directory | Owner | Email | Responsibility |
|-----------|-------|-------|----------------|
| `/db/migrations/versions/` | Backend Lead | backend-lead@skeldir.com | Versioned DDL migrations, migration review and approval |
| `/db/migrations/repeatable/` | Backend Lead | backend-lead@skeldir.com | Repeatable migrations (roles, RLS, policies) |
| `/db/migrations/templates/` | Backend Lead | backend-lead@skeldir.com | Migration templates and patterns |
| `/db/docs/` | Backend Lead | backend-lead@skeldir.com | Style guides, mapping rulebooks, checklists |
| `/db/docs/adr/` | Backend Lead + Product Owner | backend-lead@skeldir.com, product-owner@skeldir.com | Architecture Decision Records |
| `/db/docs/examples/` | Backend Lead | backend-lead@skeldir.com | Illustrative examples (not applied) |
| `/db/ops/` | DevOps Lead | devops-lead@skeldir.com | Runbooks and operational procedures |
| `/db/snapshots/` | DevOps Lead | devops-lead@skeldir.com | Schema dumps for drift detection |
| `/db/seeds/` | Backend Lead | backend-lead@skeldir.com | Seed data definitions |
| `/db/seeds/templates/` | Backend Lead | backend-lead@skeldir.com | Seed templates |
| `/db/docs/data_dictionary/` | Backend Lead | backend-lead@skeldir.com | Generated data dictionary |
| `/db/docs/erd/` | Backend Lead | backend-lead@skeldir.com | Entity-relationship diagrams |

## Review Responsibilities

- **Migration Review**: Backend Lead reviews all migration PRs for compliance with governance rules
- **ADR Review**: Backend Lead + Product Owner must approve all ADRs
- **Style Guide Changes**: Backend Lead + Frontend Lead review (for contract alignment)
- **Security Changes**: Backend Lead + Security Lead review (for RLS, roles, grants)
- **Operational Changes**: DevOps Lead reviews (for runbooks, snapshots)

## Escalation Path

1. **Technical Disputes**: Escalate to Backend Lead
2. **Architectural Disputes**: Escalate to Product Owner
3. **Security Concerns**: Escalate to Security Lead
4. **Process Disputes**: Escalate to Engineering Manager

## Review Sign-Off

**Date**: 2025-11-10  
**Reviewer**: Backend Team  
**Status**: Acknowledged - Directory structure and ownership map approved

---

*This ownership map is a living document and should be updated as team structure changes.*






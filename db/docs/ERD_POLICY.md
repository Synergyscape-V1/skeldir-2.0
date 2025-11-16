# Entity-Relationship Diagram (ERD) Policy

This document defines the process for generating and maintaining ERDs.

## Source Format

**Options**:
- **DBML** (Database Markup Language): Text-based, version-control friendly
- **Graphviz/DOT**: Graph description language
- **PostgreSQL-specific tools**: `pg_doc`, `pgAdmin`, etc.

**Recommended**: DBML for version control and text-based editing

**Rationale**: Text-based formats enable version control and diff-friendly changes.

## Regeneration Trigger

**Post-Migration**: Regenerate ERD after each migration that adds/modifies tables or relationships

**Procedure**:
1. Apply migration
2. Run ERD generator tool
3. Commit updated ERD
4. Review changes in PR

**Rationale**: Keeps ERD synchronized with schema changes.

## Storage Path

**Location**: `/db/docs/erd/`

**Files**:
- `schema.erd.dbml` - DBML source file
- `schema.erd.png` - Rendered diagram (optional, generated)
- `schema.erd.svg` - Rendered diagram (optional, generated)

**Version Control**: ERD source files are committed to version control

**Rationale**: Version-controlled ERD enables tracking of schema relationship changes.

## ERD Content Requirements

**Must Include**:
- All tables with primary keys
- All foreign key relationships
- Cardinalities (1:1, 1:N, N:M)
- Table comments (purpose, ownership)

**Optional**:
- Column details (for key columns only)
- Indexes (for important indexes)
- RLS policies (documented in comments)

**Rationale**: ERD provides high-level schema overview, not detailed column documentation.

## Generation Tools

**DBML Generation**:
- Manual: Write DBML from schema analysis
- Automated: Generate DBML from PostgreSQL schema (via `pg_doc` or custom script)

**Rendering**:
- **dbml2img**: Convert DBML to PNG/SVG
- **dbdiagram.io**: Online DBML renderer
- **dbml-cli**: Command-line DBML tools

**Rationale**: DBML ecosystem provides good tooling for generation and rendering.

## Example DBML Structure

```dbml
// Skeldir Database Schema ERD

Table tenants {
  id uuid [pk]
  name varchar
  created_at timestamptz
}

Table attribution_events {
  id uuid [pk]
  tenant_id uuid [ref: > tenants.id]
  revenue_cents integer
  created_at timestamptz
}

Ref: attribution_events.tenant_id > tenants.id [delete: cascade]
```

**Rationale**: DBML provides clear, readable schema representation.






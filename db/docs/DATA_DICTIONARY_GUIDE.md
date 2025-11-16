# Data Dictionary Guide

This document defines the process for generating and maintaining the data dictionary.

## Comment Requirements

**All database objects must have comments** using `COMMENT ON` statements.

**Minimum Content**:
- **Purpose**: What the object is used for
- **Data Class**: PII/non-PII classification
- **Ownership**: Which team/component owns this object

**Example**:
```sql
COMMENT ON TABLE attribution_events IS 
    'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII. Ownership: Attribution service.';

COMMENT ON COLUMN attribution_events.revenue_cents IS 
    'Revenue amount in cents (INTEGER). Purpose: Store revenue for attribution calculations. Data class: Non-PII.';
```

**Rationale**: Comments enable data dictionary generation and improve schema legibility.

## Generator Tool Specification

**Tool**: Parse DDL comments and generate markdown data dictionary

**Input**: 
- Migration files (extract `COMMENT ON` statements)
- Or: Live database schema (query `pg_description` system catalog)

**Output**: 
- Markdown file: `db/docs/data_dictionary/schema_dictionary.md`
- Structured format with tables, columns, constraints, indexes

**Example Output Structure**:
```markdown
# Data Dictionary

## Tables

### attribution_events

**Purpose**: Stores attribution events for revenue tracking  
**Data Class**: Non-PII  
**Ownership**: Attribution service

#### Columns

- `id` (uuid): Primary key UUID
- `tenant_id` (uuid): Foreign key to tenants table
- `revenue_cents` (integer): Revenue amount in cents (INTEGER)
- ...
```

**Tool Options**:
- Custom Python script parsing migration files
- PostgreSQL query: `SELECT * FROM pg_description JOIN pg_class ON ...`
- Third-party tool (e.g., `pg_doc`)

## Storage Path

**Location**: `/db/docs/data_dictionary/`

**Files**:
- `schema_dictionary.md` - Generated data dictionary
- `schema_dictionary.json` - Machine-readable format (optional)

**Version Control**: Data dictionary is committed to version control

**Rationale**: Version-controlled data dictionary enables tracking of schema documentation changes.

## Regeneration Trigger

**Post-Migration**: Regenerate data dictionary after each migration

**Procedure**:
1. Apply migration
2. Run data dictionary generator
3. Commit updated data dictionary
4. Review changes in PR

**Rationale**: Keeps data dictionary synchronized with schema changes.

## Integration with CI/CD

**Future Enhancement**: Automate data dictionary generation in CI/CD

**Workflow**:
1. Apply migrations in CI
2. Generate data dictionary
3. Compare with committed version
4. Fail CI if dictionary is out of sync

**Rationale**: Ensures data dictionary is always up-to-date.






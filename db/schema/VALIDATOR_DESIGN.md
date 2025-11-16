# Schema Compliance Validator Design

**Document Purpose**: Concrete design for automated schema validation tool that introspects live DB and compares against canonical specification

**Tool Name**: `validate-schema-compliance.py`  
**Location**: `scripts/validate-schema-compliance.py`  
**Version**: 1.0.0  
**Date**: 2025-11-15  
**Status**: ✅ DESIGN COMPLETE - Ready for implementation

---

## 1. Purpose

The schema compliance validator is an automated tool that:
- Loads canonical schema specification (YAML)
- Introspects live database schema via `information_schema` and `pg_*` system catalogs
- Compares actual vs. expected for all critical schema elements
- Outputs JSON report with mismatches categorized by severity
- Returns exit code based on severity of divergences

**Use Cases**:
- Pre-deployment validation
- CI/CD gate enforcement
- Manual schema audits
- Post-migration verification

---

## 2. Input Specifications

### 2.1 Canonical Schema Specification

**Primary Source**: `db/schema/canonical_schema.yaml`

**Required Fields** (per table):
```yaml
tables:
  table_name:
    columns:
      column_name:
        type: STRING          # e.g., "VARCHAR(255)", "UUID", "INTEGER"
        nullable: BOOLEAN     # true = NULL, false = NOT NULL
        default: STRING       # Default value expression (optional)
        invariant: STRING     # Invariant category (optional)
        check: STRING         # CHECK constraint definition (optional)
        unique: BOOLEAN       # UNIQUE constraint (optional)
        foreign_key: STRING   # FK definition (optional)
        
    constraints:
      - name: STRING
        type: STRING          # CHECK, UNIQUE, FK, PK
        definition: STRING
        
    indexes:
      - name: STRING
        columns: ARRAY[STRING]
        unique: BOOLEAN
        where: STRING         # WHERE clause for partial index (optional)
        ops: OBJECT           # Column operators like {created_at: DESC}
        include: ARRAY[STRING] # INCLUDE columns (optional)
```

### 2.2 Database Connection

**Method**: PostgreSQL connection string via environment variable or CLI argument

**Environment Variable**: `DATABASE_URL`

**CLI Argument**: `--database-url postgresql://user:pass@host:port/dbname`

**Required Permissions**:
- SELECT on `information_schema.*`
- SELECT on `pg_catalog.*`
- SELECT on `pg_indexes`
- SELECT on `pg_policies`

---

## 3. Introspection Logic

### 3.1 Column Introspection

**Query**: `information_schema.columns`

```python
def introspect_columns(conn, table_name: str) -> List[ColumnInfo]:
    """
    Introspect columns for a given table.
    
    Returns list of ColumnInfo with:
    - column_name
    - data_type (converted to canonical format)
    - is_nullable ("YES" → True, "NO" → False)
    - column_default (default value expression)
    """
    query = """
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
    """
    # Convert data_type to canonical format
    # e.g., "character varying" + character_maximum_length → "VARCHAR(255)"
    return parse_columns(conn.execute(query, (table_name,)))
```

**Type Normalization**:
- `character varying` + length → `VARCHAR(N)`
- `timestamp with time zone` → `TIMESTAMPTZ`
- `integer` → `INTEGER`
- `boolean` → `BOOLEAN`
- `jsonb` → `JSONB`
- `numeric` + precision + scale → `NUMERIC(P,S)`

### 3.2 Constraint Introspection

**Query**: `information_schema.table_constraints` + `information_schema.check_constraints`

```python
def introspect_constraints(conn, table_name: str) -> List[ConstraintInfo]:
    """
    Introspect constraints for a given table.
    
    Returns list of ConstraintInfo with:
    - constraint_name
    - constraint_type (CHECK, UNIQUE, FOREIGN KEY, PRIMARY KEY)
    - check_clause (for CHECK constraints)
    - constraint_columns (for UNIQUE, FK)
    - referenced_table (for FK)
    """
    query = """
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            cc.check_clause,
            kcu.column_name,
            ccu.table_name AS foreign_table_name
        FROM information_schema.table_constraints AS tc
        LEFT JOIN information_schema.check_constraints AS cc
            ON tc.constraint_name = cc.constraint_name
        LEFT JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        LEFT JOIN information_schema.constraint_column_usage AS ccu
            ON tc.constraint_name = ccu.constraint_name
        WHERE tc.table_schema = 'public'
          AND tc.table_name = %s
    """
    return parse_constraints(conn.execute(query, (table_name,)))
```

### 3.3 Index Introspection

**Query**: `pg_indexes`

```python
def introspect_indexes(conn, table_name: str) -> List[IndexInfo]:
    """
    Introspect indexes for a given table.
    
    Returns list of IndexInfo with:
    - index_name
    - index_columns (parsed from indexdef)
    - is_unique (parsed from indexdef)
    - where_clause (for partial indexes)
    """
    query = """
        SELECT 
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = %s
    """
    # Parse indexdef to extract columns, UNIQUE, WHERE clause
    return parse_indexes(conn.execute(query, (table_name,)))
```

**Index Definition Parsing**:
```python
def parse_index_definition(indexdef: str) -> IndexInfo:
    """
    Parse CREATE INDEX statement to extract:
    - UNIQUE flag
    - Column list with operators (DESC, etc.)
    - WHERE clause
    - INCLUDE columns
    
    Example:
    "CREATE UNIQUE INDEX idx_events_idempotency ON attribution_events USING btree (idempotency_key)"
    → IndexInfo(unique=True, columns=["idempotency_key"], where_clause=None)
    
    "CREATE INDEX idx_events_status ON attribution_events (processing_status, processed_at DESC) WHERE (processing_status = 'pending')"
    → IndexInfo(unique=False, columns=["processing_status", "processed_at"], 
                ops={"processed_at": "DESC"}, where_clause="processing_status = 'pending'")
    """
    # Use regex to parse components
    unique = "UNIQUE" in indexdef
    columns = extract_columns(indexdef)
    where_clause = extract_where(indexdef)
    include_columns = extract_include(indexdef)
    return IndexInfo(unique, columns, where_clause, include_columns)
```

### 3.4 RLS Policy Introspection

**Query**: `pg_policies` + `pg_class`

```python
def introspect_rls_policies(conn, table_name: str) -> RLSInfo:
    """
    Introspect RLS status and policies for a given table.
    
    Returns RLSInfo with:
    - rls_enabled (boolean)
    - rls_force (boolean)
    - policies (list of PolicyInfo)
    """
    # Check if RLS is enabled
    rls_query = """
        SELECT relrowsecurity, relforcerowsecurity
        FROM pg_class
        WHERE relname = %s
          AND relnamespace = 'public'::regnamespace
    """
    
    # Get policies
    policy_query = """
        SELECT 
            policyname,
            permissive,
            cmd,
            qual,
            with_check
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = %s
    """
    return parse_rls_info(
        conn.execute(rls_query, (table_name,)),
        conn.execute(policy_query, (table_name,))
    )
```

---

## 4. Comparison Logic

### 4.1 Column Comparison

```python
def compare_columns(canonical: ColumnSpec, actual: ColumnInfo) -> List[Divergence]:
    """
    Compare canonical column spec against actual column info.
    
    Checks:
    - Column exists
    - Type matches (with normalization)
    - Nullability matches
    - Default matches (if specified)
    """
    divergences = []
    
    if actual is None:
        divergences.append(Divergence(
            type="MISSING_COLUMN",
            severity=get_severity(canonical.invariant),
            table=canonical.table,
            element=canonical.column_name,
            expected=f"{canonical.type} {'NOT NULL' if not canonical.nullable else 'NULL'}",
            actual="MISSING",
            invariant=canonical.invariant,
            impact=f"Required for {canonical.required_for}"
        ))
        return divergences
    
    if not types_match(canonical.type, actual.data_type):
        divergences.append(Divergence(
            type="TYPE_MISMATCH",
            severity=get_severity(canonical.invariant),
            table=canonical.table,
            element=canonical.column_name,
            expected=canonical.type,
            actual=actual.data_type,
            invariant=canonical.invariant
        ))
    
    if canonical.nullable != actual.is_nullable:
        divergences.append(Divergence(
            type="NULLABILITY_MISMATCH",
            severity=get_severity(canonical.invariant),
            table=canonical.table,
            element=canonical.column_name,
            expected="NOT NULL" if not canonical.nullable else "NULL",
            actual="NULL" if actual.is_nullable else "NOT NULL",
            invariant=canonical.invariant
        ))
    
    return divergences
```

### 4.2 Constraint Comparison

```python
def compare_constraints(canonical: ConstraintSpec, actual: ConstraintInfo) -> List[Divergence]:
    """
    Compare canonical constraint spec against actual constraint.
    
    Checks:
    - Constraint exists
    - Type matches (CHECK, UNIQUE, FK, PK)
    - Definition matches (for CHECK constraints)
    """
    if actual is None:
        return [Divergence(
            type="MISSING_CONSTRAINT",
            severity=get_severity_for_constraint(canonical),
            table=canonical.table,
            element=canonical.constraint_name,
            expected=canonical.definition,
            actual="MISSING",
            invariant=canonical.invariant
        )]
    
    # For CHECK constraints, compare normalized definitions
    if canonical.type == "CHECK" and actual.type == "CHECK":
        if not check_clauses_equivalent(canonical.definition, actual.check_clause):
            return [Divergence(
                type="CONSTRAINT_MISMATCH",
                severity=get_severity_for_constraint(canonical),
                table=canonical.table,
                element=canonical.constraint_name,
                expected=canonical.definition,
                actual=actual.check_clause,
                invariant=canonical.invariant
            )]
    
    return []
```

### 4.3 Index Comparison

```python
def compare_indexes(canonical: IndexSpec, actual: IndexInfo) -> List[Divergence]:
    """
    Compare canonical index spec against actual index.
    
    Checks:
    - Index exists
    - UNIQUE flag matches
    - Columns match (order matters)
    - WHERE clause matches (for partial indexes)
    - INCLUDE columns match (for covering indexes)
    """
    if actual is None:
        return [Divergence(
            type="MISSING_INDEX",
            severity=get_severity_for_index(canonical),
            table=canonical.table,
            element=canonical.index_name,
            expected=f"({', '.join(canonical.columns)})" + 
                     (f" WHERE {canonical.where}" if canonical.where else ""),
            actual="MISSING",
            invariant=canonical.invariant
        )]
    
    divergences = []
    
    if canonical.unique != actual.unique:
        divergences.append(Divergence(
            type="INDEX_UNIQUENESS_MISMATCH",
            severity=get_severity_for_index(canonical),
            ...
        ))
    
    if canonical.columns != actual.columns:
        divergences.append(Divergence(
            type="INDEX_COLUMNS_MISMATCH",
            severity=get_severity_for_index(canonical),
            ...
        ))
    
    return divergences
```

---

## 5. Severity Mapping

```python
INVARIANT_SEVERITY_MAP = {
    "auth_critical": "BLOCKING",
    "privacy_critical": "BLOCKING",
    "processing_critical": "BLOCKING",
    "financial_critical": "BLOCKING",
    "analytics_important": "HIGH",
    None: "LOW"  # Elements without invariant tags
}

def get_severity(invariant: Optional[str]) -> str:
    """Map invariant category to severity level."""
    return INVARIANT_SEVERITY_MAP.get(invariant, "LOW")
```

---

## 6. Output Format

### 6.1 JSON Report Structure

```json
{
  "validation_date": "2025-11-15T10:30:00Z",
  "canonical_spec_version": "1.0.0",
  "database": "postgresql://localhost:5432/skeldir",
  "status": "FAIL",
  "summary": {
    "total_divergences": 42,
    "blocking": 28,
    "high": 10,
    "moderate": 3,
    "low": 1
  },
  "divergences": [
    {
      "type": "MISSING_COLUMN",
      "severity": "BLOCKING",
      "table": "tenants",
      "element": "api_key_hash",
      "expected": "VARCHAR(255) NOT NULL UNIQUE",
      "actual": "MISSING",
      "invariant": "auth_critical",
      "impact": "Required for B0.4 API Authentication",
      "required_for": ["B0.4 API Authentication"]
    },
    {
      "type": "NULLABILITY_MISMATCH",
      "severity": "BLOCKING",
      "table": "attribution_events",
      "element": "session_id",
      "expected": "NOT NULL",
      "actual": "NULL",
      "invariant": "privacy_critical",
      "impact": "Required for Attribution Logic"
    }
  ],
  "tables_checked": ["tenants", "attribution_events", "attribution_allocations", "revenue_ledger", "dead_events", "revenue_state_transitions"],
  "exit_code": 1
}
```

### 6.2 Console Output

```
Schema Compliance Validation Report
====================================
Date: 2025-11-15 10:30:00
Canonical Spec: v1.0.0
Database: postgresql://localhost:5432/skeldir

Summary:
--------
Total Divergences: 42
  BLOCKING: 28
  HIGH: 10
  MODERATE: 3
  LOW: 1

BLOCKING Issues (Phase Blocking):
----------------------------------
[1] MISSING_COLUMN: tenants.api_key_hash
    Expected: VARCHAR(255) NOT NULL UNIQUE
    Actual: MISSING
    Invariant: auth_critical
    Impact: Required for B0.4 API Authentication

[2] NULLABILITY_MISMATCH: attribution_events.session_id
    Expected: NOT NULL
    Actual: NULL
    Invariant: privacy_critical
    Impact: Required for Attribution Logic

... (26 more BLOCKING issues)

HIGH Issues (Feature Impact):
------------------------------
[29] MISSING_COLUMN: attribution_allocations.confidence_score
     Expected: NUMERIC(4,3) NOT NULL CHECK (0-1)
     Actual: MISSING
     Invariant: analytics_important
     Impact: Required for B2.1 Statistical Attribution

... (9 more HIGH issues)

Result: FAIL (28 BLOCKING divergences)
Exit Code: 1
```

---

## 7. Exit Code Logic

```python
def determine_exit_code(divergences: List[Divergence]) -> int:
    """
    Determine exit code based on divergence severity.
    
    Exit Codes:
    0 = PASS (no divergences or only LOW severity)
    1 = FAIL (one or more BLOCKING divergences)
    2 = WARN (HIGH divergences but no BLOCKING)
    """
    blocking_count = sum(1 for d in divergences if d.severity == "BLOCKING")
    high_count = sum(1 for d in divergences if d.severity == "HIGH")
    
    if blocking_count > 0:
        return 1  # FAIL - phase blocked
    elif high_count > 0:
        return 2  # WARN - degraded functionality
    else:
        return 0  # PASS - all critical elements compliant
```

---

## 8. CLI Interface

```bash
# Basic usage (uses DATABASE_URL environment variable)
python scripts/validate-schema-compliance.py

# Explicit database URL
python scripts/validate-schema-compliance.py --database-url postgresql://user:pass@host/db

# Output JSON to file
python scripts/validate-schema-compliance.py --output validation_results.json

# Verbose mode (print all divergences, not just summary)
python scripts/validate-schema-compliance.py --verbose

# Check specific tables only
python scripts/validate-schema-compliance.py --tables tenants,attribution_events

# Fail on HIGH severity (stricter mode)
python scripts/validate-schema-compliance.py --fail-on-high
```

---

## 9. CI/CD Integration

### 9.1 GitHub Actions Workflow

```yaml
name: Schema Validation

on:
  pull_request:
    paths:
      - 'alembic/versions/**'
      - 'db/schema/**'

jobs:
  validate-schema:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: skeldir_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install psycopg2-binary pyyaml
      
      - name: Apply migrations
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost:5432/skeldir_test
        run: |
          alembic upgrade head
      
      - name: Run schema validator
        env:
          DATABASE_URL: postgresql://test_user:test_password@localhost:5432/skeldir_test
        run: |
          python scripts/validate-schema-compliance.py --output validation_results.json
      
      - name: Upload validation report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: validation_results.json
      
      - name: Fail on divergences
        run: |
          exit $(python -c "import json; print(json.load(open('validation_results.json'))['exit_code'])")
```

---

## 10. Implementation Notes

### 10.1 Dependencies

```python
# requirements.txt additions
psycopg2-binary>=2.9.0  # PostgreSQL adapter
pyyaml>=6.0             # YAML parsing
```

### 10.2 Code Structure

```
scripts/
  validate-schema-compliance.py     # Main entry point
  schema_validator/
    __init__.py
    loader.py                        # Load canonical spec from YAML
    introspector.py                  # Database introspection
    comparator.py                    # Comparison logic
    reporter.py                      # Report generation
    cli.py                           # CLI argument parsing
```

### 10.3 Testing

**Unit Tests**: Mock database responses, test comparison logic

**Integration Tests**: Real PostgreSQL instance, apply migrations, run validator

**Test Cases**:
1. All tables match canonical → exit code 0
2. One BLOCKING divergence → exit code 1
3. One HIGH divergence → exit code 2
4. Type mismatch detected
5. Nullability mismatch detected
6. Missing index detected
7. Missing constraint detected

---

## 11. Maintenance

**Update Triggers**:
- Canonical spec changes → Re-run validator
- New invariant category added → Update severity map
- New constraint type added → Update introspection logic

**Versioning**: Validator version tied to canonical spec version

---

## Summary

**Tool**: `validate-schema-compliance.py`  
**Input**: Canonical YAML + Live DB connection  
**Output**: JSON report + Exit code (0/1/2)  
**Enforcement**: CI/CD gate that FAILS build on BLOCKING divergences  
**Maintenance**: Update when canonical spec changes

**Status**: ✅ **DESIGN COMPLETE - READY FOR IMPLEMENTATION**

**Next Steps**: Implement in Phase 9 of plan

**Signed**: AI Assistant (Claude)  
**Date**: 2025-11-15




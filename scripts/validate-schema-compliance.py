#!/usr/bin/env python3
"""
Schema Compliance Validator

Forensically validates live database schema against canonical specification.

Usage:
    python scripts/validate-schema-compliance.py [--database-url URL] [--output FILE] [--verbose]

Exit Codes:
    0 = PASS (no BLOCKING divergences)
    1 = FAIL (one or more BLOCKING divergences)
    2 = WARN (HIGH divergences but no BLOCKING)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from scripts.security.db_secret_access import resolve_runtime_database_url

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import yaml
except ImportError as e:
    print(f"ERROR: Missing required dependency: {e}", file=sys.stderr)
    print("Install with: pip install psycopg2-binary pyyaml", file=sys.stderr)
    sys.exit(1)


# Severity mapping from invariant categories
INVARIANT_SEVERITY_MAP = {
    "auth_critical": "BLOCKING",
    "privacy_critical": "BLOCKING",
    "processing_critical": "BLOCKING",
    "financial_critical": "BLOCKING",
    "analytics_important": "HIGH",
    None: "LOW",
}


class Divergence:
    """Represents a schema divergence from canonical specification."""
    
    def __init__(
        self,
        divergence_type: str,
        severity: str,
        table: str,
        element: str,
        expected: str,
        actual: str,
        invariant: Optional[str] = None,
        impact: Optional[str] = None,
        required_for: Optional[List[str]] = None,
    ):
        self.type = divergence_type
        self.severity = severity
        self.table = table
        self.element = element
        self.expected = expected
        self.actual = actual
        self.invariant = invariant
        self.impact = impact or ""
        self.required_for = required_for or []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "severity": self.severity,
            "table": self.table,
            "element": self.element,
            "expected": self.expected,
            "actual": self.actual,
            "invariant": self.invariant,
            "impact": self.impact,
            "required_for": self.required_for,
        }


class SchemaValidator:
    """Main validator class that compares canonical spec against live database."""
    
    def __init__(self, database_url: str, canonical_spec_path: str):
        self.database_url = database_url
        self.canonical_spec_path = canonical_spec_path
        self.conn = None
        self.canonical_spec = None
        self.divergences: List[Divergence] = []
    
    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(self.database_url)
        except Exception as e:
            print(f"ERROR: Failed to connect to database: {e}", file=sys.stderr)
            sys.exit(1)
    
    def load_canonical_spec(self):
        """Load canonical schema specification from YAML."""
        spec_path = Path(self.canonical_spec_path)
        if not spec_path.exists():
            print(f"ERROR: Canonical spec not found: {spec_path}", file=sys.stderr)
            sys.exit(1)
        
        with open(spec_path, 'r') as f:
            self.canonical_spec = yaml.safe_load(f)
    
    def normalize_type(self, pg_type: str, max_length: Optional[int] = None, 
                      precision: Optional[int] = None, scale: Optional[int] = None) -> str:
        """Normalize PostgreSQL type to canonical format."""
        type_map = {
            'character varying': 'VARCHAR',
            'timestamp with time zone': 'TIMESTAMPTZ',
            'timestamp without time zone': 'TIMESTAMP',
            'integer': 'INTEGER',
            'bigint': 'BIGINT',
            'boolean': 'BOOLEAN',
            'jsonb': 'JSONB',
            'text': 'TEXT',
            'uuid': 'UUID',
            'numeric': 'NUMERIC',
        }
        
        base_type = type_map.get(pg_type.lower(), pg_type.upper())
        
        if base_type == 'VARCHAR' and max_length:
            return f"VARCHAR({max_length})"
        elif base_type == 'NUMERIC' and precision and scale:
            return f"NUMERIC({precision},{scale})"
        elif base_type == 'NUMERIC' and precision:
            return f"NUMERIC({precision})"
        else:
            return base_type
    
    def introspect_columns(self, table_name: str) -> Dict[str, Dict]:
        """Introspect columns for a given table."""
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
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (table_name,))
            columns = {}
            for row in cur.fetchall():
                normalized_type = self.normalize_type(
                    row['data_type'],
                    row['character_maximum_length'],
                    row['numeric_precision'],
                    row['numeric_scale']
                )
                columns[row['column_name']] = {
                    'type': normalized_type,
                    'nullable': row['is_nullable'] == 'YES',
                    'default': row['column_default'],
                }
            return columns
    
    def introspect_indexes(self, table_name: str) -> Dict[str, Dict]:
        """Introspect indexes for a given table."""
        query = """
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = %s
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (table_name,))
            indexes = {}
            for row in cur.fetchall():
                indexdef = row['indexdef']
                is_unique = 'UNIQUE' in indexdef.upper()
                
                # Extract columns from index definition
                # Pattern: CREATE [UNIQUE] INDEX ... ON table USING btree (col1, col2 DESC)
                match = re.search(r'\(([^)]+)\)', indexdef)
                if match:
                    cols_str = match.group(1)
                    columns = []
                    for col_part in cols_str.split(','):
                        col_part = col_part.strip()
                        # Remove DESC/ASC operators for comparison
                        col_name = col_part.split()[0].strip('"')
                        columns.append(col_name)
                else:
                    columns = []
                
                # Extract WHERE clause
                where_match = re.search(r'WHERE\s+\((.+)\)', indexdef, re.IGNORECASE)
                where_clause = where_match.group(1) if where_match else None
                
                # Extract INCLUDE columns
                include_match = re.search(r'INCLUDE\s+\(([^)]+)\)', indexdef, re.IGNORECASE)
                include_cols = []
                if include_match:
                    include_cols = [c.strip().strip('"') for c in include_match.group(1).split(',')]
                
                indexes[row['indexname']] = {
                    'unique': is_unique,
                    'columns': columns,
                    'where_clause': where_clause,
                    'include': include_cols,
                }
            return indexes
    
    def introspect_constraints(self, table_name: str) -> Dict[str, Dict]:
        """Introspect constraints for a given table."""
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
                AND tc.constraint_schema = cc.constraint_schema
            LEFT JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.constraint_schema = kcu.constraint_schema
            LEFT JOIN information_schema.constraint_column_usage AS ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.constraint_schema = ccu.constraint_schema
            WHERE tc.table_schema = 'public'
              AND tc.table_name = %s
        """
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (table_name,))
            constraints = {}
            for row in cur.fetchall():
                constraint_name = row['constraint_name']
                if constraint_name not in constraints:
                    constraints[constraint_name] = {
                        'type': row['constraint_type'],
                        'check_clause': row['check_clause'],
                        'columns': [],
                        'foreign_table': row['foreign_table_name'],
                    }
                if row['column_name']:
                    constraints[constraint_name]['columns'].append(row['column_name'])
            return constraints
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if table exists in database."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            )
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (table_name,))
            return cur.fetchone()[0]
    
    def compare_table(self, table_name: str, table_spec: Dict):
        """Compare a single table against canonical specification."""
        if not self.check_table_exists(table_name):
            # Table missing entirely
            invariant = table_spec.get('rls_enabled', False) and 'privacy_critical' or None
            severity = INVARIANT_SEVERITY_MAP.get(invariant, "BLOCKING")
            self.divergences.append(Divergence(
                divergence_type="MISSING_TABLE",
                severity=severity,
                table=table_name,
                element=table_name,
                expected="Table exists",
                actual="MISSING",
                invariant=invariant,
                impact=f"Required table {table_name} does not exist",
            ))
            return
        
        # Introspect actual schema
        actual_columns = self.introspect_columns(table_name)
        actual_indexes = self.introspect_indexes(table_name)
        actual_constraints = self.introspect_constraints(table_name)
        
        # Compare columns
        canonical_columns = table_spec.get('columns', {})
        for col_name, col_spec in canonical_columns.items():
            if col_name not in actual_columns:
                # Missing column
                invariant = col_spec.get('invariant')
                severity = INVARIANT_SEVERITY_MAP.get(invariant, "LOW")
                required_for = col_spec.get('required_for', [])
                impact = f"Required for: {', '.join(required_for)}" if required_for else ""
                
                expected_type = col_spec.get('type', 'UNKNOWN')
                expected_nullable = "NULL" if col_spec.get('nullable', True) else "NOT NULL"
                expected_str = f"{expected_type} {expected_nullable}"
                
                self.divergences.append(Divergence(
                    divergence_type="MISSING_COLUMN",
                    severity=severity,
                    table=table_name,
                    element=col_name,
                    expected=expected_str,
                    actual="MISSING",
                    invariant=invariant,
                    impact=impact,
                    required_for=required_for,
                ))
            else:
                # Column exists - check type and nullability
                actual_col = actual_columns[col_name]
                expected_type = col_spec.get('type', '').upper()
                actual_type = actual_col['type'].upper()
                
                # Type comparison (normalize for comparison)
                if expected_type != actual_type:
                    # Allow some flexibility (e.g., TEXT vs VARCHAR)
                    if not (expected_type.startswith('VARCHAR') and actual_type == 'TEXT'):
                        invariant = col_spec.get('invariant')
                        severity = INVARIANT_SEVERITY_MAP.get(invariant, "LOW")
                        self.divergences.append(Divergence(
                            divergence_type="TYPE_MISMATCH",
                            severity=severity,
                            table=table_name,
                            element=col_name,
                            expected=expected_type,
                            actual=actual_type,
                            invariant=invariant,
                        ))
                
                # Nullability comparison
                expected_nullable = col_spec.get('nullable', True)
                actual_nullable = actual_col['nullable']
                if expected_nullable != actual_nullable:
                    invariant = col_spec.get('invariant')
                    severity = INVARIANT_SEVERITY_MAP.get(invariant, "BLOCKING")
                    self.divergences.append(Divergence(
                        divergence_type="NULLABILITY_MISMATCH",
                        severity=severity,
                        table=table_name,
                        element=col_name,
                        expected="NOT NULL" if not expected_nullable else "NULL",
                        actual="NULL" if actual_nullable else "NOT NULL",
                        invariant=invariant,
                    ))
                
                # Check UNIQUE constraint (if specified in canonical)
                if col_spec.get('unique', False):
                    # Check if there's a unique index on this column
                    has_unique_index = False
                    for idx_name, idx_info in actual_indexes.items():
                        if idx_info['unique'] and col_name in idx_info['columns']:
                            has_unique_index = True
                            break
                    
                    if not has_unique_index:
                        invariant = col_spec.get('invariant')
                        severity = INVARIANT_SEVERITY_MAP.get(invariant, "BLOCKING")
                        self.divergences.append(Divergence(
                            divergence_type="MISSING_UNIQUE_CONSTRAINT",
                            severity=severity,
                            table=table_name,
                            element=col_name,
                            expected="UNIQUE constraint",
                            actual="MISSING",
                            invariant=invariant,
                        ))
        
        # Compare indexes
        canonical_indexes = table_spec.get('indexes', [])
        for idx_spec in canonical_indexes:
            idx_name = idx_spec['name']
            if idx_name not in actual_indexes:
                # Missing index
                severity = "HIGH"  # Indexes are typically HIGH severity
                self.divergences.append(Divergence(
                    divergence_type="MISSING_INDEX",
                    severity=severity,
                    table=table_name,
                    element=idx_name,
                    expected=f"Index on {idx_spec.get('columns', [])}",
                    actual="MISSING",
                ))
            else:
                # Index exists - check uniqueness and columns
                actual_idx = actual_indexes[idx_name]
                expected_unique = idx_spec.get('unique', False)
                if expected_unique != actual_idx['unique']:
                    self.divergences.append(Divergence(
                        divergence_type="INDEX_UNIQUENESS_MISMATCH",
                        severity="HIGH",
                        table=table_name,
                        element=idx_name,
                        expected="UNIQUE" if expected_unique else "NON-UNIQUE",
                        actual="UNIQUE" if actual_idx['unique'] else "NON-UNIQUE",
                    ))
        
        # Compare constraints
        canonical_constraints = table_spec.get('constraints', [])
        for constraint_spec in canonical_constraints:
            constraint_name = constraint_spec['name']
            if constraint_name not in actual_constraints:
                # Missing constraint
                constraint_type = constraint_spec.get('type', 'CHECK')
                severity = "BLOCKING" if constraint_type == 'CHECK' else "HIGH"
                self.divergences.append(Divergence(
                    divergence_type="MISSING_CONSTRAINT",
                    severity=severity,
                    table=table_name,
                    element=constraint_name,
                    expected=constraint_spec.get('definition', ''),
                    actual="MISSING",
                ))
    
    def validate(self) -> List[Divergence]:
        """Run complete validation against all canonical tables."""
        tables_spec = self.canonical_spec.get('tables', {})
        
        for table_name, table_spec in tables_spec.items():
            self.compare_table(table_name, table_spec)
        
        return self.divergences
    
    def determine_exit_code(self) -> int:
        """Determine exit code based on divergence severity."""
        blocking_count = sum(1 for d in self.divergences if d.severity == "BLOCKING")
        high_count = sum(1 for d in self.divergences if d.severity == "HIGH")
        
        if blocking_count > 0:
            return 1  # FAIL
        elif high_count > 0:
            return 2  # WARN
        else:
            return 0  # PASS
    
    def generate_report(self) -> Dict:
        """Generate JSON report."""
        blocking_count = sum(1 for d in self.divergences if d.severity == "BLOCKING")
        high_count = sum(1 for d in self.divergences if d.severity == "HIGH")
        moderate_count = sum(1 for d in self.divergences if d.severity == "MODERATE")
        low_count = sum(1 for d in self.divergences if d.severity == "LOW")
        
        return {
            "validation_date": datetime.utcnow().isoformat() + "Z",
            "canonical_spec_version": self.canonical_spec.get('version', '1.0.0'),
            "database": self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url,
            "status": "FAIL" if blocking_count > 0 else ("WARN" if high_count > 0 else "PASS"),
            "summary": {
                "total_divergences": len(self.divergences),
                "blocking": blocking_count,
                "high": high_count,
                "moderate": moderate_count,
                "low": low_count,
            },
            "divergences": [d.to_dict() for d in self.divergences],
            "tables_checked": list(self.canonical_spec.get('tables', {}).keys()),
            "exit_code": self.determine_exit_code(),
        }
    
    def print_console_report(self, verbose: bool = False):
        """Print human-readable console report."""
        blocking = [d for d in self.divergences if d.severity == "BLOCKING"]
        high = [d for d in self.divergences if d.severity == "HIGH"]
        moderate = [d for d in self.divergences if d.severity == "MODERATE"]
        low = [d for d in self.divergences if d.severity == "LOW"]
        
        print("Schema Compliance Validation Report")
        print("=" * 50)
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Canonical Spec: v{self.canonical_spec.get('version', '1.0.0')}")
        print(f"Database: {self.database_url.split('@')[-1] if '@' in self.database_url else self.database_url}")
        print()
        print("Summary:")
        print("-" * 50)
        print(f"Total Divergences: {len(self.divergences)}")
        print(f"  BLOCKING: {len(blocking)}")
        print(f"  HIGH: {len(high)}")
        print(f"  MODERATE: {len(moderate)}")
        print(f"  LOW: {len(low)}")
        print()
        
        if blocking:
            print("BLOCKING Issues (Phase Blocking):")
            print("-" * 50)
            for i, d in enumerate(blocking, 1):
                print(f"[{i}] {d.type}: {d.table}.{d.element}")
                print(f"    Expected: {d.expected}")
                print(f"    Actual: {d.actual}")
                if d.invariant:
                    print(f"    Invariant: {d.invariant}")
                if d.impact:
                    print(f"    Impact: {d.impact}")
                print()
        
        if high and verbose:
            print("HIGH Issues (Feature Impact):")
            print("-" * 50)
            for i, d in enumerate(high, 1):
                print(f"[{i}] {d.type}: {d.table}.{d.element}")
                print(f"    Expected: {d.expected}")
                print(f"    Actual: {d.actual}")
                print()
        
        exit_code = self.determine_exit_code()
        status_map = {0: "PASS", 1: "FAIL", 2: "WARN"}
        print(f"Result: {status_map[exit_code]} ({len(blocking)} BLOCKING divergences)")
        print(f"Exit Code: {exit_code}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Validate database schema against canonical specification"
    )
    parser.add_argument(
        '--database-url',
        default=None,
        help='PostgreSQL connection string (or use DATABASE_URL env var)'
    )
    parser.add_argument(
        '--canonical-spec',
        default='db/schema/canonical_schema.yaml',
        help='Path to canonical schema YAML file'
    )
    parser.add_argument(
        '--output',
        help='Output JSON report to file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print all divergences, not just BLOCKING'
    )
    
    args = parser.parse_args()
    
    if not args.database_url:
        args.database_url = resolve_runtime_database_url()
    
    validator = SchemaValidator(args.database_url, args.canonical_spec)
    
    try:
        validator.connect()
        validator.load_canonical_spec()
        validator.validate()
        
        report = validator.generate_report()
        
        # Print console report
        validator.print_console_report(verbose=args.verbose)
        
        # Write JSON report if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nJSON report written to: {args.output}")
        
        # Exit with appropriate code
        sys.exit(report['exit_code'])
    
    except Exception as e:
        print(f"ERROR: Validation failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        validator.close()


if __name__ == '__main__':
    main()









#!/usr/bin/env python3
"""
Channel FK Validation Script

Validates that Foreign Key constraints exist for channel governance enforcement.
This script verifies the DB-level enforcement mechanisms required by the channel contract.

Exit Codes:
- 0: All FK constraints exist and are correctly configured
- 1: Missing or misconfigured FK constraints
- 2: Database connection or query error

Usage:
    python scripts/validate_channel_fks.py

Related Documents:
- db/docs/channel_contract.md (Section 4.1: Database-Level Enforcement)
- B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md (Phase 6 evidence)

Phase: 6 - Governance & Monitoring
"""

import sys
from typing import Dict, List, Tuple


def _import_db_secret_access():
    try:
        from scripts.security.db_secret_access import resolve_runtime_database_url
        return resolve_runtime_database_url
    except ModuleNotFoundError:
        from pathlib import Path

        for parent in Path(__file__).resolve().parents:
            if (parent / "scripts" / "security" / "db_secret_access.py").exists():
                sys.path.insert(0, str(parent))
                from scripts.security.db_secret_access import resolve_runtime_database_url
                return resolve_runtime_database_url
        raise


resolve_runtime_database_url = _import_db_secret_access()

# Database connection (would use actual connection in production)
# For now, we'll simulate or require psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("Warning: psycopg2 not installed. Install with: pip install psycopg2-binary", file=sys.stderr)


def get_db_connection():
    """
    Get database connection from environment variables.
    
    Expected environment variables:
    - DATABASE_URL: PostgreSQL connection string
    Or:
    - DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
    """
    if not HAS_PSYCOPG2:
        raise RuntimeError("psycopg2 is required for database validation")
    
    database_url = resolve_runtime_database_url().replace("postgresql+asyncpg://", "postgresql://", 1)
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)


def validate_fk_exists(
    conn,
    table_name: str,
    column_name: str,
    foreign_table: str,
    foreign_column: str,
    expected_constraint_name: str
) -> Tuple[bool, str]:
    """
    Validate that a specific FK constraint exists with correct configuration.
    
    Args:
        conn: Database connection
        table_name: Source table name
        column_name: Source column name
        foreign_table: Referenced table name
        foreign_column: Referenced column name
        expected_constraint_name: Expected FK constraint name
    
    Returns:
        (is_valid, message) tuple
    """
    query = """
        SELECT 
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
            AND kcu.column_name = %s
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (table_name, column_name))
        results = cur.fetchall()
    
    if not results:
        return False, f"FAIL: No FK constraint found on {table_name}.{column_name}"
    
    if len(results) > 1:
        return False, f"FAIL: Multiple FK constraints found on {table_name}.{column_name} (expected 1)"
    
    fk = results[0]
    
    # Validate constraint details
    errors = []
    
    if fk['constraint_name'] != expected_constraint_name:
        errors.append(f"  - Constraint name mismatch: expected '{expected_constraint_name}', got '{fk['constraint_name']}'")
    
    if fk['foreign_table_name'] != foreign_table:
        errors.append(f"  - Foreign table mismatch: expected '{foreign_table}', got '{fk['foreign_table_name']}'")
    
    if fk['foreign_column_name'] != foreign_column:
        errors.append(f"  - Foreign column mismatch: expected '{foreign_column}', got '{fk['foreign_column_name']}'")
    
    if errors:
        return False, f"FAIL: FK constraint exists but has configuration errors:\n" + "\n".join(errors)
    
    # Success
    message = (
        f"PASS: FK constraint '{fk['constraint_name']}' exists\n"
        f"  - Source: {table_name}.{column_name}\n"
        f"  - Target: {foreign_table}.{foreign_column}\n"
        f"  - Update Rule: {fk['update_rule']}\n"
        f"  - Delete Rule: {fk['delete_rule']}"
    )
    return True, message


def main() -> int:
    """
    Main validation routine.
    
    Returns:
        Exit code (0 = success, 1 = validation failure, 2 = error)
    """
    print("=" * 80)
    print("Channel FK Validation Script")
    print("Validating database-level enforcement of channel governance")
    print("=" * 80)
    print()
    
    # Check if we can run validation
    if not HAS_PSYCOPG2:
        print("ERROR: Cannot run validation without psycopg2", file=sys.stderr)
        print("Install with: pip install psycopg2-binary", file=sys.stderr)
        return 2
    
    try:
        conn = get_db_connection()
    except Exception as e:
        print(f"ERROR: Failed to connect to database: {e}", file=sys.stderr)
        return 2
    
    try:
        all_valid = True
        
        # Validation 1: attribution_events.channel FK
        print("Validation 1: attribution_events.channel FK to channel_taxonomy.code")
        print("-" * 80)
        is_valid, message = validate_fk_exists(
            conn,
            table_name='attribution_events',
            column_name='channel',
            foreign_table='channel_taxonomy',
            foreign_column='code',
            expected_constraint_name='fk_attribution_events_channel'
        )
        print(message)
        print()
        
        if not is_valid:
            all_valid = False
        
        # Validation 2: attribution_allocations.channel_code FK
        print("Validation 2: attribution_allocations.channel_code FK to channel_taxonomy.code")
        print("-" * 80)
        is_valid, message = validate_fk_exists(
            conn,
            table_name='attribution_allocations',
            column_name='channel_code',
            foreign_table='channel_taxonomy',
            foreign_column='code',
            expected_constraint_name='fk_attribution_allocations_channel_code'
        )
        print(message)
        print()
        
        if not is_valid:
            all_valid = False
        
        # Summary
        print("=" * 80)
        if all_valid:
            print("✓ All channel FK constraints are correctly configured")
            print("✓ Channel governance enforcement is active at database boundary")
            return 0
        else:
            print("✗ Some FK constraints are missing or misconfigured")
            print("✗ Channel governance may not be properly enforced")
            return 1
    
    except Exception as e:
        print(f"ERROR: Validation failed with exception: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 2
    
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())









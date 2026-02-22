#!/usr/bin/env python3
"""
Channel Data Integrity Validation Script

Validates that all persisted channel values are canonical (exist in channel_taxonomy).
This script detects any non-taxonomy channel values that bypassed FK constraints.

Exit Codes:
- 0: All channel values are canonical (zero integrity violations)
- 1: Non-canonical channel values detected (integrity violations exist)
- 2: Database connection or query error

Usage:
    python scripts/validate_channel_integrity.py

Related Documents:
- db/docs/channel_contract.md (Section 4.3: Continuous Integrity Checks)
- B0.3-P_CHANNEL_GOVERNANCE_REMEDIATION.md (Phase 6 evidence)

Phase: 6 - Governance & Monitoring
"""

import sys
from typing import List, Dict


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

# Database connection
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


def validate_events_channel_integrity(conn) -> tuple[bool, int, List[Dict]]:
    """
    Validate that all attribution_events.channel values exist in channel_taxonomy.
    
    Args:
        conn: Database connection
    
    Returns:
        (is_valid, invalid_count, invalid_values) tuple
    """
    query = """
        SELECT 
            channel,
            COUNT(*) AS event_count
        FROM attribution_events
        WHERE channel NOT IN (SELECT code FROM channel_taxonomy)
        GROUP BY channel
        ORDER BY event_count DESC, channel
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    invalid_count = sum(row['event_count'] for row in results)
    is_valid = invalid_count == 0
    
    return is_valid, invalid_count, results


def validate_allocations_channel_integrity(conn) -> tuple[bool, int, List[Dict]]:
    """
    Validate that all attribution_allocations.channel_code values exist in channel_taxonomy.
    
    Args:
        conn: Database connection
    
    Returns:
        (is_valid, invalid_count, invalid_values) tuple
    """
    query = """
        SELECT 
            channel_code,
            COUNT(*) AS allocation_count
        FROM attribution_allocations
        WHERE channel_code NOT IN (SELECT code FROM channel_taxonomy)
        GROUP BY channel_code
        ORDER BY allocation_count DESC, channel_code
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    invalid_count = sum(row['allocation_count'] for row in results)
    is_valid = invalid_count == 0
    
    return is_valid, invalid_count, results


def get_taxonomy_codes(conn) -> List[str]:
    """
    Get all canonical channel codes from channel_taxonomy.
    
    Args:
        conn: Database connection
    
    Returns:
        List of canonical channel codes
    """
    query = "SELECT code FROM channel_taxonomy WHERE is_active = true ORDER BY code"
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    return [row['code'] for row in results]


def main() -> int:
    """
    Main validation routine.
    
    Returns:
        Exit code (0 = success, 1 = integrity violations, 2 = error)
    """
    print("=" * 80)
    print("Channel Data Integrity Validation Script")
    print("Validating all persisted channel values are canonical")
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
        total_violations = 0
        
        # Get canonical codes for reference
        print("Canonical Channel Codes (from channel_taxonomy):")
        print("-" * 80)
        taxonomy_codes = get_taxonomy_codes(conn)
        for code in taxonomy_codes:
            print(f"  - {code}")
        print(f"Total: {len(taxonomy_codes)} canonical codes")
        print()
        
        # Validation 1: attribution_events.channel integrity
        print("Validation 1: attribution_events.channel integrity")
        print("-" * 80)
        is_valid, invalid_count, invalid_values = validate_events_channel_integrity(conn)
        
        if is_valid:
            print("✓ PASS: All attribution_events.channel values are canonical")
            print(f"  - Invalid values: 0")
        else:
            print(f"✗ FAIL: Found {invalid_count} non-canonical channel values in attribution_events")
            print("  - Invalid channel values:")
            for row in invalid_values:
                print(f"    - '{row['channel']}': {row['event_count']} events")
            all_valid = False
            total_violations += invalid_count
        print()
        
        # Validation 2: attribution_allocations.channel_code integrity
        print("Validation 2: attribution_allocations.channel_code integrity")
        print("-" * 80)
        is_valid, invalid_count, invalid_values = validate_allocations_channel_integrity(conn)
        
        if is_valid:
            print("✓ PASS: All attribution_allocations.channel_code values are canonical")
            print(f"  - Invalid values: 0")
        else:
            print(f"✗ FAIL: Found {invalid_count} non-canonical channel_code values in attribution_allocations")
            print("  - Invalid channel_code values:")
            for row in invalid_values:
                print(f"    - '{row['channel_code']}': {row['allocation_count']} allocations")
            all_valid = False
            total_violations += invalid_count
        print()
        
        # Summary
        print("=" * 80)
        if all_valid:
            print("✓ All channel values are canonical")
            print("✓ Zero integrity violations detected")
            print("✓ Channel governance contract is upheld")
            return 0
        else:
            print(f"✗ Integrity violations detected: {total_violations} total")
            print("✗ Action required: Investigate and repair non-canonical channel values")
            print("✗ This indicates FK constraints may have been bypassed or misconfigured")
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









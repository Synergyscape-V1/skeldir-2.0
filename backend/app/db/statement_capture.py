"""
R2 Runtime Innocence Measurement: SQLAlchemy Statement Capture Hook

This module provides CI-only instrumentation for capturing SQL statements
during actual application execution. It proves runtime innocence by
demonstrating that production code paths never attempt destructive
operations on immutable tables.

AUTHORITATIVE PROOF: This is the PRIMARY blocker for R2 completion.
Static analysis cannot override runtime failure.

Activation:
    Set R2_STATEMENT_CAPTURE=1 to enable capture mode (CI-only).

Usage:
    from app.db.statement_capture import attach_capture_hook, get_captured_statements

    # Attach to engine before any operations
    attach_capture_hook(engine)

    # ... execute application code paths ...

    # Get captured statements for analysis
    statements = get_captured_statements()
"""

from __future__ import annotations

import os
import re
import threading
from typing import List, Set, Tuple
from dataclasses import dataclass, field

from sqlalchemy import event
from sqlalchemy.engine import Engine


# Immutable table closed set - authoritative definition
IMMUTABLE_TABLES: Set[str] = frozenset({
    "attribution_events",
    "revenue_ledger",
})

# Destructive verb closed set - operations that violate immutability
DESTRUCTIVE_VERBS: Set[str] = frozenset({
    "UPDATE",
    "DELETE",
    "TRUNCATE",
    "ALTER",
})


@dataclass
class CapturedStatement:
    """A captured SQL statement with metadata."""
    raw_sql: str
    normalized_sql: str
    parameters: dict
    is_destructive: bool
    affected_immutable_table: str | None

    def __str__(self) -> str:
        if self.is_destructive and self.affected_immutable_table:
            return f"[VIOLATION] {self.normalized_sql[:100]}... -> {self.affected_immutable_table}"
        return f"[OK] {self.normalized_sql[:80]}..."


class StatementCapture:
    """Thread-safe statement capture storage."""

    def __init__(self):
        self._lock = threading.Lock()
        self._statements: List[CapturedStatement] = []
        self._enabled: bool = False

    def enable(self):
        """Enable statement capture."""
        with self._lock:
            self._enabled = True
            self._statements.clear()

    def disable(self):
        """Disable statement capture."""
        with self._lock:
            self._enabled = False

    def is_enabled(self) -> bool:
        """Check if capture is enabled."""
        return self._enabled

    def add(self, statement: CapturedStatement):
        """Add a captured statement (thread-safe)."""
        with self._lock:
            if self._enabled:
                self._statements.append(statement)

    def get_all(self) -> List[CapturedStatement]:
        """Get all captured statements (thread-safe copy)."""
        with self._lock:
            return list(self._statements)

    def get_violations(self) -> List[CapturedStatement]:
        """Get only statements that violate immutability."""
        with self._lock:
            return [s for s in self._statements if s.is_destructive and s.affected_immutable_table]

    def clear(self):
        """Clear all captured statements."""
        with self._lock:
            self._statements.clear()


# Global capture instance
_capture = StatementCapture()


def normalize_sql(sql: str) -> str:
    """
    Normalize SQL for pattern matching.

    - Uppercase for verb detection
    - Collapse whitespace
    - Remove comments
    """
    # Remove SQL comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # Collapse whitespace
    sql = re.sub(r'\s+', ' ', sql).strip()
    return sql.upper()


def detect_destructive_on_immutable(normalized_sql: str) -> Tuple[bool, str | None]:
    """
    Detect if a SQL statement is destructive against an immutable table.

    Returns:
        Tuple of (is_destructive, affected_table_or_none)
    """
    # Pattern: VERB ... FROM/INTO/TABLE table_name
    # Also handles: DELETE FROM table, UPDATE table SET, ALTER TABLE table

    for verb in DESTRUCTIVE_VERBS:
        if not normalized_sql.startswith(verb):
            continue

        # Extract table name based on verb
        for table in IMMUTABLE_TABLES:
            table_upper = table.upper()
            # Check various patterns:
            # DELETE FROM attribution_events
            # UPDATE attribution_events SET
            # TRUNCATE TABLE attribution_events
            # ALTER TABLE attribution_events
            patterns = [
                rf'\b{verb}\s+FROM\s+{table_upper}\b',
                rf'\b{verb}\s+{table_upper}\s+',
                rf'\b{verb}\s+TABLE\s+{table_upper}\b',
                rf'\b{verb}\s+.*?\s+{table_upper}\b',
            ]
            for pattern in patterns:
                if re.search(pattern, normalized_sql):
                    return True, table

    return False, None


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """
    SQLAlchemy event listener for statement capture.

    This is attached to engine.before_cursor_execute and captures
    every SQL statement before execution.
    """
    if not _capture.is_enabled():
        return

    normalized = normalize_sql(statement)
    is_destructive, affected_table = detect_destructive_on_immutable(normalized)

    captured = CapturedStatement(
        raw_sql=statement,
        normalized_sql=normalized,
        parameters=dict(parameters) if parameters else {},
        is_destructive=is_destructive,
        affected_immutable_table=affected_table,
    )

    _capture.add(captured)

    # Print to stdout for CI log capture
    if is_destructive and affected_table:
        print(f"[R2_STATEMENT_VIOLATION] {normalized[:200]}")
    elif os.getenv("R2_STATEMENT_VERBOSE"):
        print(f"[R2_STATEMENT] {normalized[:100]}")


def attach_capture_hook(engine) -> bool:
    """
    Attach statement capture hook to SQLAlchemy engine.

    Only attaches if R2_STATEMENT_CAPTURE=1 environment variable is set.

    For async engines (AsyncEngine), attaches to the underlying sync_engine
    since SQLAlchemy doesn't support async event listeners directly.

    Returns:
        True if hook was attached, False otherwise.
    """
    if os.getenv("R2_STATEMENT_CAPTURE") != "1":
        return False

    # Handle async engines - attach to sync_engine
    target_engine = engine
    if hasattr(engine, 'sync_engine'):
        target_engine = engine.sync_engine
        print("[R2_STATEMENT_CAPTURE] Detected AsyncEngine, using sync_engine for events")

    event.listen(target_engine, "before_cursor_execute", _before_cursor_execute)
    _capture.enable()

    print("[R2_STATEMENT_CAPTURE] Hook attached to engine")
    print(f"[R2_STATEMENT_CAPTURE] IMMUTABLE_TABLES={','.join(sorted(IMMUTABLE_TABLES))}")
    print(f"[R2_STATEMENT_CAPTURE] DESTRUCTIVE_VERBS={','.join(sorted(DESTRUCTIVE_VERBS))}")

    return True


def detach_capture_hook(engine):
    """Detach statement capture hook from engine."""
    target_engine = engine
    if hasattr(engine, 'sync_engine'):
        target_engine = engine.sync_engine

    try:
        event.remove(target_engine, "before_cursor_execute", _before_cursor_execute)
    except Exception:
        pass  # Hook wasn't attached
    _capture.disable()


def get_captured_statements() -> List[CapturedStatement]:
    """Get all captured SQL statements."""
    return _capture.get_all()


def get_violations() -> List[CapturedStatement]:
    """Get statements that violate immutability constraints."""
    return _capture.get_violations()


def print_verdict():
    """
    Print the authoritative R2 runtime innocence verdict.

    This is the MANDATORY output block that determines R2 completion.
    """
    violations = get_violations()
    all_statements = get_captured_statements()

    print("\n" + "=" * 70)
    print("R2_RUNTIME_INNOCENCE_VERDICT")
    print("=" * 70)
    print(f"IMMUTABLE_TABLE_SET={','.join(sorted(IMMUTABLE_TABLES))}")
    print(f"DESTRUCTIVE_VERBS={','.join(sorted(DESTRUCTIVE_VERBS))}")
    print(f"TOTAL_STATEMENTS_CAPTURED={len(all_statements)}")
    print(f"MATCH_COUNT={len(violations)}")
    print("=" * 70)

    if violations:
        print("\n[FAIL] R2 RUNTIME INNOCENCE VIOLATED")
        print("The following destructive operations were attempted on immutable tables:")
        for v in violations:
            print(f"  - TABLE: {v.affected_immutable_table}")
            print(f"    SQL: {v.normalized_sql[:200]}")
        return False
    else:
        print("\n[PASS] R2 RUNTIME INNOCENCE PROVEN")
        print("No destructive operations attempted on immutable tables during execution.")
        return True


def clear_capture():
    """Clear all captured statements."""
    _capture.clear()

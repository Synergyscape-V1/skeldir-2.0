#!/usr/bin/env python3
"""
R2 DB Statement Capture (AUTHORITATIVE)

Parses Postgres logs (docker logs output) and produces a window-delimited,
per-scenario verdict:

Hard FAIL conditions:
  - Missing window markers
  - Missing per-scenario markers
  - Any scenario has 0 non-marker statements (theater window)
  - TOTAL_DB_STATEMENTS_CAPTURED_IN_WINDOW < (2*num_scenarios + 2)
  - Any destructive statement targeting immutable tables
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Tuple


IMMUTABLE_TABLES = ("attribution_events", "revenue_ledger")
DESTRUCTIVE_VERBS = ("UPDATE", "DELETE", "TRUNCATE", "ALTER")


STATEMENT_EVENT_RE = re.compile(
    r"""
    \bLOG:\s+
    (?:
      duration:\s+\d+(?:\.\d+)?\s+ms\s+
    )?
    (?:
      statement:\s+(?P<statement>.*)
      |
      execute\s+(?P<execname>[^:]+):\s+(?P<execute>.*)
    )
    """,
    re.VERBOSE,
)

# Some Postgres configurations emit the SQL under a separate "STATEMENT:" line
# (e.g., for errors). Capture those too for robustness.
ERROR_STATEMENT_RE = re.compile(r"\bSTATEMENT:\s+(?P<statement>.*)")

MARKER_ANY_RE = re.compile(r"R2_(?:WINDOW_(?:START|END)|S\d+_(?:START|END))::")


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().upper()


def _is_txn_noise(normalized_sql: str) -> bool:
    if normalized_sql in {"BEGIN", "COMMIT", "ROLLBACK"}:
        return True
    return normalized_sql.startswith("SAVEPOINT") or normalized_sql.startswith("RELEASE SAVEPOINT")


def _is_destructive_on_immutable(sql: str) -> bool:
    normalized = _normalize(sql)
    if not any(re.search(rf"\b{verb}\b", normalized) for verb in DESTRUCTIVE_VERBS):
        return False
    return any(re.search(rf"\b{table.upper()}\b", normalized) for table in IMMUTABLE_TABLES)


@dataclass(frozen=True)
class StatementEvent:
    line_no: int
    raw_line: str
    sql: str

    @property
    def normalized_sql(self) -> str:
        return _normalize(self.sql)

    @property
    def is_marker(self) -> bool:
        return MARKER_ANY_RE.search(self.sql) is not None

    @property
    def is_destructive_on_immutable(self) -> bool:
        return _is_destructive_on_immutable(self.sql)


def extract_statement_events(lines: Iterable[str]) -> List[StatementEvent]:
    events: List[StatementEvent] = []
    for idx, line in enumerate(lines, start=1):
        match = STATEMENT_EVENT_RE.search(line)
        if match:
            sql = match.group("statement") or match.group("execute") or ""
        else:
            match_err = ERROR_STATEMENT_RE.search(line)
            if not match_err:
                continue
            sql = match_err.group("statement") or ""
        sql = sql.strip()
        if not sql:
            continue
        events.append(StatementEvent(line_no=idx, raw_line=line.rstrip("\n"), sql=sql))
    return events


def _find_unique_event_index(events: List[StatementEvent], marker: str) -> int:
    indices = [i for i, e in enumerate(events) if marker in e.sql]
    if len(indices) != 1:
        raise ValueError(f"Expected exactly 1 occurrence of marker '{marker}', found {len(indices)}")
    return indices[0]


def _slice_inclusive(events: List[StatementEvent], start_idx: int, end_idx: int) -> List[StatementEvent]:
    if start_idx > end_idx:
        raise ValueError("start_idx must be <= end_idx")
    return events[start_idx : end_idx + 1]


def _count_non_marker(events: List[StatementEvent]) -> int:
    count = 0
    for e in events:
        if e.is_marker:
            continue
        if _is_txn_noise(e.normalized_sql):
            continue
        count += 1
    return count


@dataclass(frozen=True)
class ScenarioWindow:
    number: int
    start_idx: int
    end_idx: int
    non_marker_count: int


def audit(
    *,
    events: List[StatementEvent],
    candidate_sha: str,
    window_id: str,
    num_scenarios: int,
    enforce_forbidden: bool = True,
) -> Tuple[dict, int]:
    window_start = f"R2_WINDOW_START::{candidate_sha}::{window_id}"
    window_end = f"R2_WINDOW_END::{candidate_sha}::{window_id}"

    failures: List[str] = []

    try:
        start_idx = _find_unique_event_index(events, window_start)
        end_idx = _find_unique_event_index(events, window_end)
    except ValueError as exc:
        failures.append(str(exc))
        return (
            {
                "candidate_sha": candidate_sha,
                "window_id": window_id,
                "num_scenarios": num_scenarios,
                "window_found": False,
                "failures": failures,
            },
            1,
        )

    if start_idx >= end_idx:
        failures.append("Window markers out of order (start after end)")
        return (
            {
                "candidate_sha": candidate_sha,
                "window_id": window_id,
                "num_scenarios": num_scenarios,
                "window_found": True,
                "failures": failures,
            },
            1,
        )

    window_events = _slice_inclusive(events, start_idx, end_idx)
    total_in_window = len(window_events)
    min_expected = 2 * num_scenarios + 2
    if total_in_window < min_expected:
        failures.append(
            f"TOTAL_DB_STATEMENTS_CAPTURED_IN_WINDOW too small: {total_in_window} < {min_expected} (markers missing or parsing broken)"
        )

    scenario_windows: List[ScenarioWindow] = []
    scenarios_with_markers = 0
    scenarios_with_non_marker = 0

    for i in range(1, num_scenarios + 1):
        s_start = f"R2_S{i}_START::{candidate_sha}::{window_id}"
        s_end = f"R2_S{i}_END::{candidate_sha}::{window_id}"
        try:
            s_start_idx_rel = _find_unique_event_index(window_events, s_start)
            s_end_idx_rel = _find_unique_event_index(window_events, s_end)
        except ValueError as exc:
            failures.append(f"Scenario {i} marker failure: {exc}")
            continue

        scenarios_with_markers += 1
        if s_start_idx_rel >= s_end_idx_rel:
            failures.append(f"Scenario {i} markers out of order")
            continue

        slice_events = _slice_inclusive(window_events, s_start_idx_rel, s_end_idx_rel)
        non_marker = _count_non_marker(slice_events)
        if non_marker <= 0:
            failures.append(f"Scenario {i} has 0 non-marker DB statements (theater window)")
        else:
            scenarios_with_non_marker += 1

        scenario_windows.append(
            ScenarioWindow(
                number=i,
                start_idx=start_idx + s_start_idx_rel,
                end_idx=start_idx + s_end_idx_rel,
                non_marker_count=non_marker,
            )
        )

    destructive_matches = [e for e in window_events if e.is_destructive_on_immutable]
    if enforce_forbidden and destructive_matches:
        failures.append(
            f"Destructive statements on immutable tables detected: {len(destructive_matches)}"
        )

    verdict = {
        "candidate_sha": candidate_sha,
        "window_id": window_id,
        "num_scenarios": num_scenarios,
        "window_found": True,
        "window_start_event": asdict(events[start_idx]),
        "window_end_event": asdict(events[end_idx]),
        "total_statement_events_parsed": len(events),
        "total_db_statements_captured_in_window": total_in_window,
        "min_expected_in_window": min_expected,
        "scenarios_with_markers": scenarios_with_markers,
        "scenarios_with_non_marker": scenarios_with_non_marker,
        "scenario_windows": [asdict(w) for w in scenario_windows],
        "match_count_destructive_on_immutable": len(destructive_matches),
        "destructive_matches": [asdict(e) for e in destructive_matches[:25]],
        "failures": failures,
    }
    return verdict, (1 if failures else 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--window-id", required=True)
    parser.add_argument("--num-scenarios", type=int, default=6)
    parser.add_argument("--enforce-forbidden", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--artifact-json", required=False)
    args = parser.parse_args()

    log_path = Path(args.log_file)
    raw = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    events = extract_statement_events(raw)

    verdict, exit_code = audit(
        events=events,
        candidate_sha=args.candidate_sha,
        window_id=args.window_id,
        num_scenarios=args.num_scenarios,
        enforce_forbidden=args.enforce_forbidden,
    )

    print("R2_DB_RUNTIME_INNOCENCE_VERDICT")
    print("IMMUTABLE_TABLE_SET=attribution_events,revenue_ledger")
    print("DESTRUCTIVE_VERBS=ALTER,DELETE,TRUNCATE,UPDATE")
    print(f"CANDIDATE_SHA={args.candidate_sha}")
    print(f"WINDOW_ID={args.window_id}")
    print(f"STATEMENT_EVENT_REGEX={STATEMENT_EVENT_RE.pattern.strip()}")
    print(f"ERROR_STATEMENT_REGEX={ERROR_STATEMENT_RE.pattern.strip()}")
    print(f"TOTAL_STATEMENT_EVENTS_PARSED={verdict.get('total_statement_events_parsed', 0)}")
    print(f"TOTAL_DB_STATEMENTS_CAPTURED_IN_WINDOW={verdict.get('total_db_statements_captured_in_window', 0)}")
    for w in verdict.get("scenario_windows", []):
        print(f"S{w['number']}_NON_MARKER_DB_STATEMENTS_COUNT={w['non_marker_count']}")
    print(f"DB_FORBIDDEN_MATCH_COUNT={verdict.get('match_count_destructive_on_immutable', 0)}")
    if verdict.get("failures"):
        print("FAILURES=" + "; ".join(verdict["failures"]))
    print("END_VERDICT")

    if args.artifact_json:
        Path(args.artifact_json).write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

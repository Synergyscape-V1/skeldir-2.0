#!/usr/bin/env python3
"""Fail-closed execution assertion for B1.5-P7 Playwright browser proofs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _iter_specs(suites: list[dict[str, Any]]):
    for suite in suites:
        for spec in suite.get("specs", []):
            yield spec
        for nested in _iter_specs(suite.get("suites", [])):
            yield nested


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assert B1.5-P7 Playwright browser proofs executed and did not skip."
    )
    parser.add_argument("--report-json", required=True)
    parser.add_argument(
        "--expected-test",
        action="append",
        default=[],
        help="Expected Playwright spec title. Can be passed multiple times.",
    )
    args = parser.parse_args()

    report_path = Path(args.report_json)
    if not report_path.exists():
        print("b15_p7_playwright_execution_assertion")
        print("result=FAIL")
        print(f"missing_report:{report_path}")
        return 1

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    expected = list(dict.fromkeys(args.expected_test))
    if not expected:
        print("b15_p7_playwright_execution_assertion")
        print("result=FAIL")
        print("missing_expected_tests")
        return 1

    by_title: dict[str, list[dict[str, Any]]] = {}
    for spec in _iter_specs(payload.get("suites", [])):
        title = str(spec.get("title", "")).strip()
        if not title:
            continue
        tests = spec.get("tests", [])
        if not isinstance(tests, list):
            continue
        by_title.setdefault(title, []).extend(tests)

    violations: list[str] = []
    for title in expected:
        tests = by_title.get(title, [])
        if not tests:
            violations.append(f"missing_expected_test:{title}")
            continue

        saw_executed = False
        saw_pass = False
        saw_skipped = False
        for test in tests:
            status = str(test.get("status", "")).lower()
            expected_status = str(test.get("expectedStatus", "")).lower()
            if status == "skipped" or expected_status == "skipped":
                saw_skipped = True
            results = test.get("results", [])
            if not isinstance(results, list):
                continue
            for result in results:
                result_status = str(result.get("status", "")).lower()
                if result_status and result_status != "skipped":
                    saw_executed = True
                if result_status == "passed":
                    saw_pass = True

        if saw_skipped:
            violations.append(f"unexpected_skip:{title}")
        if not saw_executed:
            violations.append(f"not_executed:{title}")
        if not saw_pass:
            violations.append(f"not_passed:{title}")

    stats = payload.get("stats", {})
    if int(stats.get("skipped", 0)) > 0:
        violations.append(f"stats_skipped_non_zero:{int(stats.get('skipped', 0))}")

    print("b15_p7_playwright_execution_assertion")
    if violations:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return 1

    print("result=PASS")
    print(f"executed_expected_tests={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

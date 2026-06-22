#!/usr/bin/env python3
"""Validate B2.4-P11 execution-physical JUnit artifacts."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/ci/b24_p11_execution_manifest.yaml"
DEFAULT_SUMMARY = ROOT / "artifacts/b24_p11_ci_gate_matrix.json"
DEFAULT_OUTPUT = ROOT / "artifacts/b24_p11_execution_artifacts.json"


class ValidationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Case:
    classname: str
    name: str
    failed: bool
    errored: bool
    skipped: bool
    xfail: bool
    xpass: bool

    @property
    def base_name(self) -> str:
        return self.name.split("[", 1)[0]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing execution manifest: {path}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid execution manifest YAML: {exc}") from exc
    _require(isinstance(data, list), "execution manifest must be a YAML list")
    rows: list[dict[str, Any]] = []
    required = {
        "phase_id",
        "workflow_job",
        "required_status",
        "test_artifact_path",
        "expected_test_modules",
        "expected_test_cases",
        "minimum_test_count",
        "allowed_skips",
        "allowed_xfails",
        "required_markers",
        "execution_required",
        "non_overclaim_boundary",
    }
    for row in data:
        _require(isinstance(row, dict), "execution manifest row must be a mapping")
        missing = required - set(row)
        _require(not missing, f"manifest row missing fields:{row.get('phase_id')}:{sorted(missing)}")
        _require(row["execution_required"] is True, f"{row['phase_id']} must be execution_required")
        rows.append(row)
    return rows


def _case_text(element: ET.Element) -> str:
    parts = [element.attrib.get("name", ""), element.attrib.get("classname", "")]
    for child in list(element):
        parts.extend(str(value) for value in child.attrib.values())
        if child.text:
            parts.append(child.text)
    return " ".join(parts).lower()


def _parse_junit(path: Path) -> list[Case]:
    if not path.exists():
        raise ValidationError(f"missing JUnit execution artifact: {path.as_posix()}")
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValidationError(f"invalid JUnit XML artifact {path.as_posix()}: {exc}") from exc
    cases: list[Case] = []
    for element in root.iter("testcase"):
        text = _case_text(element)
        cases.append(
            Case(
                classname=element.attrib.get("classname", ""),
                name=element.attrib.get("name", ""),
                failed=element.find("failure") is not None,
                errored=element.find("error") is not None,
                skipped=element.find("skipped") is not None,
                xfail="xfail" in text or "expected failure" in text,
                xpass="xpass" in text or "unexpected pass" in text,
            )
        )
    return cases


def _expected_name(expected: str) -> str:
    return expected.rsplit("::", 1)[-1].split("[", 1)[0]


def _expected_module(expected: str) -> str | None:
    if "::" not in expected:
        return None
    module_path = expected.split("::", 1)[0]
    return Path(module_path).stem


def _matches(expected: str, case: Case) -> bool:
    if case.base_name != _expected_name(expected):
        return False
    module = _expected_module(expected)
    if module is None:
        return True
    return case.classname.endswith(module) or module in case.classname


def validate_artifacts(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    summary_path: Path | None = DEFAULT_SUMMARY,
) -> dict[str, Any]:
    rows = _load_manifest(manifest_path)
    results: list[dict[str, Any]] = []
    for row in rows:
        artifact_path = ROOT / str(row["test_artifact_path"])
        cases = _parse_junit(artifact_path)
        expected_cases = [str(item) for item in row["expected_test_cases"]]
        allowed_skips = {str(item) for item in row.get("allowed_skips", [])}
        allowed_xfails = {str(item) for item in row.get("allowed_xfails", [])}
        _require(cases, f"{row['workflow_job']} reported zero test cases")
        _require(
            len(cases) >= int(row["minimum_test_count"]),
            f"{row['workflow_job']} test count below minimum: {len(cases)} < {row['minimum_test_count']}",
        )
        missing = [
            expected
            for expected in expected_cases
            if not any(_matches(expected, case) for case in cases)
        ]
        _require(not missing, f"{row['workflow_job']} missing expected cases: {missing}")
        failed = [case.name for case in cases if case.failed or case.errored]
        _require(not failed, f"{row['workflow_job']} has failing/error cases: {failed}")
        skipped = [
            case.name
            for case in cases
            if case.skipped and not case.xfail and case.name not in allowed_skips
        ]
        _require(not skipped, f"{row['workflow_job']} has unauthorized skipped cases: {skipped}")
        xfailed = [
            case.name
            for case in cases
            if case.xfail and case.name not in allowed_xfails
        ]
        _require(not xfailed, f"{row['workflow_job']} has unauthorized xfail cases: {xfailed}")
        xpassed = [case.name for case in cases if case.xpass]
        _require(not xpassed, f"{row['workflow_job']} has unauthorized xpass cases: {xpassed}")
        duplicate_names = sorted(
            name for name in {case.name for case in cases} if sum(1 for case in cases if case.name == name) > 1
        )
        _require(not duplicate_names, f"{row['workflow_job']} has duplicate testcase names: {duplicate_names}")
        results.append(
            {
                "phase_id": row["phase_id"],
                "workflow_job": row["workflow_job"],
                "required_status": row["required_status"],
                "execution_artifact_path": row["test_artifact_path"],
                "expected_test_count": len(expected_cases),
                "actual_test_count": len(cases),
                "skipped_count": sum(1 for case in cases if case.skipped),
                "xfail_count": sum(1 for case in cases if case.xfail),
                "failed_count": sum(1 for case in cases if case.failed or case.errored),
                "missing_expected_cases": [],
                "artifact_verification_status": "pass",
            }
        )
    payload = {
        "schema_version": "b24-p11-execution-artifacts-v1",
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "timestamp": datetime.now(UTC).isoformat(),
        "positive_proof_status": "execution_artifacts_verified",
        "jobs": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if summary_path and summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["execution_artifact_status"] = "verified"
        for phase in summary.get("phases", []):
            workflow_jobs = set(str(item) for item in phase.get("workflow_job", []))
            telemetry_rows = [item for item in results if str(item["workflow_job"]) in workflow_jobs]
            if telemetry_rows:
                phase["execution_artifact_path"] = [
                    item["execution_artifact_path"] for item in telemetry_rows
                ]
                phase["expected_test_count"] = sum(
                    int(item["expected_test_count"]) for item in telemetry_rows
                )
                phase["actual_test_count"] = sum(
                    int(item["actual_test_count"]) for item in telemetry_rows
                )
                phase["skipped_count"] = sum(
                    int(item["skipped_count"]) for item in telemetry_rows
                )
                phase["xfail_count"] = sum(
                    int(item["xfail_count"]) for item in telemetry_rows
                )
                phase["failed_count"] = sum(
                    int(item["failed_count"]) for item in telemetry_rows
                )
                phase["missing_expected_cases"] = []
                phase["positive_proof_status"] = "execution_artifacts_verified"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def _write_xml(path: Path, cases: list[tuple[str, str, str | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    testsuite = ET.Element("testsuite", {"name": "negative", "tests": str(len(cases))})
    for classname, name, outcome in cases:
        case = ET.SubElement(testsuite, "testcase", {"classname": classname, "name": name})
        if outcome == "skip":
            ET.SubElement(case, "skipped", {"message": "skip"})
        elif outcome == "xfail":
            ET.SubElement(case, "skipped", {"message": "xfail"})
        elif outcome == "xpass":
            out = ET.SubElement(case, "system-out")
            out.text = "XPASS"
        elif outcome == "failure":
            ET.SubElement(case, "failure", {"message": "failed"})
    ET.ElementTree(testsuite).write(path, encoding="utf-8", xml_declaration=True)


def _manifest(path: Path, artifact: Path, expected: list[str], minimum: int = 1) -> None:
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "phase_id": "B2.4-PX",
                    "workflow_job": "negative-control",
                    "required_status": "negative-control",
                    "test_artifact_path": artifact.relative_to(ROOT).as_posix(),
                    "expected_test_modules": ["backend/tests/test_negative.py"],
                    "expected_test_cases": expected,
                    "minimum_test_count": minimum,
                    "allowed_skips": [],
                    "allowed_xfails": [],
                    "required_markers": [],
                    "execution_required": True,
                    "non_overclaim_boundary": "P11 proves merge-blocking CI enforcement, not production-topology trust closure.",
                }
            ],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _expect_failure(name: str, func: Any, expected: str) -> None:
    try:
        func()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temp:
        base = Path(temp)
        manifest = base / "manifest.yaml"
        xml = base / "junit.xml"
        expected = ["backend/tests/test_negative.py::test_required"]
        _write_xml(xml, [("backend.tests.test_negative", "test_required", None)])
        _manifest(manifest, xml, expected)
        validate_artifacts(manifest_path=manifest, output_path=base / "positive.json", summary_path=None)
        _expect_failure(
            "missing_artifact",
            lambda: (_manifest(manifest, base / "missing.xml", expected), validate_artifacts(manifest_path=manifest, output_path=base / "missing.json", summary_path=None)),
            "missing junit",
        )
        _write_xml(xml, [])
        _manifest(manifest, xml, expected)
        _expect_failure("zero_tests", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "zero.json", summary_path=None), "zero")
        _write_xml(xml, [("backend.tests.test_negative", "test_other", None)])
        _expect_failure("missing_expected", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "missing_case.json", summary_path=None), "missing expected")
        _write_xml(xml, [("backend.tests.test_negative", "test_required", "skip")])
        _expect_failure("skip", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "skip.json", summary_path=None), "skipped")
        _write_xml(xml, [("backend.tests.test_negative", "test_required", "xfail")])
        _expect_failure("xfail", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "xfail.json", summary_path=None), "xfail")
        _write_xml(xml, [("backend.tests.test_negative", "test_required", "xpass")])
        _expect_failure("xpass", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "xpass.json", summary_path=None), "xpass")
        _write_xml(xml, [("backend.tests.test_negative", "test_required", "failure")])
        _expect_failure("failure", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "failure.json", summary_path=None), "failing")
        _write_xml(xml, [("backend.tests.test_negative", "test_required", None)])
        _manifest(manifest, xml, expected, minimum=2)
        _expect_failure("below_minimum", lambda: validate_artifacts(manifest_path=manifest, output_path=base / "minimum.json", summary_path=None), "below minimum")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY))
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--negative-control-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.negative_control:
            run_negative_controls()
        if args.negative_control_only:
            print("B24_P11_EXECUTION_ARTIFACT_NEGATIVE_CONTROLS_PASS")
            return 0
        validate_artifacts(
            manifest_path=ROOT / args.manifest,
            output_path=ROOT / args.output,
            summary_path=ROOT / args.summary_path if args.summary_path else None,
        )
    except ValidationError as exc:
        print(f"B24_P11_EXECUTION_ARTIFACT_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P11_EXECUTION_ARTIFACT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Write a JUnit attestation for non-pytest B2.4 proof commands.

The file is intentionally small: it should only be called after the command
steps it attests have already succeeded. The P11 execution parser then treats
the emitted cases exactly like pytest JUnit cases.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET


def write_junit(*, output: Path, suite: str, cases: list[str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    testsuite = ET.Element(
        "testsuite",
        {
            "name": suite,
            "tests": str(len(cases)),
            "failures": "0",
            "errors": "0",
            "skipped": "0",
        },
    )
    for case in cases:
        ET.SubElement(
            testsuite,
            "testcase",
            {
                "classname": suite,
                "name": case,
                "time": "0",
            },
        )
    ET.ElementTree(testsuite).write(output, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--case", action="append", required=True)
    args = parser.parse_args()
    write_junit(output=Path(args.output), suite=args.suite, cases=args.case)
    print(f"B24_P11_COMMAND_JUNIT_WRITTEN: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

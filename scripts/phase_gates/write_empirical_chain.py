#!/usr/bin/env python3
"""
Generates docs/forensics/backend/validation/EMPIRICAL_CHAIN.md using recorded ACKs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def load_ack_files(ack_dir: Path) -> list[dict]:
    records = []
    if not ack_dir.exists():
        return records

    for ack_path in sorted(ack_dir.glob("*.json")):
        try:
            with open(ack_path, "r", encoding="utf-8") as fh:
                records.append(json.load(fh))
        except Exception as exc:  # pragma: no cover - defensive
            records.append(
                {
                    "phase": ack_path.stem,
                    "status": "error",
                    "message": f"Failed to read ack: {exc}",
                    "timestamp": "",
                }
            )
    return records


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    ack_dir = repo_root / "backend" / "validation" / "evidence" / "phase_ack"
    ack_dir.mkdir(parents=True, exist_ok=True)

    records = load_ack_files(ack_dir)
    output_dir = repo_root / "docs" / "forensics" / "backend" / "validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "EMPIRICAL_CHAIN.md"

    lines: list[str] = []
    lines.append("# Empirical Chain - Phase Gate Status")
    lines.append("")
    lines.append(f"Generated: {datetime.now(tz=timezone.utc).isoformat()}")
    lines.append("")
    if not records:
        lines.append("_No phase acknowledgements recorded yet._")
    else:
        lines.append("| Phase | Status | Timestamp | Message |")
        lines.append("|-------|--------|-----------|---------|")
        for record in records:
            lines.append(
                f"| {record.get('phase', '')} "
                f"| {record.get('status', '')} "
                f"| {record.get('timestamp', '')} "
                f"| {record.get('message', '')} |"
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote empirical chain to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

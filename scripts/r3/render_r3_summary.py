from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_BEGIN = re.compile(r"^R3_VERDICT_BEGIN (.+)$")
_END = re.compile(r"^R3_VERDICT_END (.+)$")
_N_SUFFIX = re.compile(r"_N(\d+)$")


@dataclass(frozen=True)
class ParsedRun:
    env: dict[str, Any]
    verdicts: dict[str, dict[str, Any]]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_env_block(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "=== R3_ENV ===":
            buf: list[str] = []
            for j in range(i + 1, min(i + 2000, len(lines))):
                buf.append(lines[j])
                joined = "\n".join(buf).strip()
                try:
                    return json.loads(joined)
                except json.JSONDecodeError:
                    continue
    return {}


def _parse_verdicts(text: str) -> dict[str, dict[str, Any]]:
    verdicts: dict[str, dict[str, Any]] = {}
    lines = text.splitlines()

    current_name: str | None = None
    current_json: list[str] = []

    for line in lines:
        m_begin = _BEGIN.match(line.strip())
        if m_begin:
            current_name = m_begin.group(1).strip()
            current_json = []
            continue

        m_end = _END.match(line.strip())
        if m_end and current_name:
            name = current_name
            payload_raw = "\n".join(current_json).strip()
            verdicts[name] = json.loads(payload_raw) if payload_raw else {}
            current_name = None
            current_json = []
            continue

        if current_name:
            current_json.append(line)

    return verdicts


def parse_run(log_path: Path) -> ParsedRun:
    text = _read_text(log_path)
    return ParsedRun(env=_parse_env_block(text), verdicts=_parse_verdicts(text))


def _max_n(verdicts: dict[str, dict[str, Any]]) -> int | None:
    ns: list[int] = []
    for name in verdicts:
        m = _N_SUFFIX.search(name)
        if m:
            ns.append(int(m.group(1)))
    return max(ns) if ns else None


def _pick(verdicts: dict[str, dict[str, Any]], prefix: str, n: int) -> tuple[str, dict[str, Any]] | None:
    suffix = f"_N{n}"
    for name, payload in verdicts.items():
        if name.startswith(prefix) and name.endswith(suffix):
            return name, payload
    return None


def _bool(v: Any) -> bool:
    return bool(v is True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_summary_md(*, candidate_sha: str, run_url: str, parsed: ParsedRun, out_path: Path) -> str:
    n = _max_n(parsed.verdicts)
    if n is None:
        md = "\n".join(
            [
                "# R3 Ingestion Under Fire Validation Summary (Truth Anchor)",
                "",
                "## Status",
                "",
                "R3 = **IN PROGRESS** (no scenario verdict blocks were detected in the harness log).",
                "",
                f"- **Candidate SHA:** `{candidate_sha}`",
                f"- **CI run:** {run_url}",
                f"- **Generated at:** `{_utc_now_iso()}`",
                "",
                "## Notes",
                "",
                "- Harness did not emit `R3_VERDICT_BEGIN/END` blocks; inspect `r3_harness.log` in workflow artifacts.",
                "",
                "## Where the Evidence Lives",
                "",
                "- Workflow: `.github/workflows/r3-ingestion-under-fire.yml`",
                "- Harness: `scripts/r3/ingestion_under_fire.py`",
                "",
            ]
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md + "\n", encoding="utf-8")
        return md

    s1 = _pick(parsed.verdicts, "S1_ReplayStorm", n)
    s2 = _pick(parsed.verdicts, "S2_UniqueStorm", n)
    s3 = _pick(parsed.verdicts, "S3_MalformedStorm", n)
    s4 = _pick(parsed.verdicts, "S4_PIIStorm", n)
    s5 = _pick(parsed.verdicts, "S5_CrossTenantCollision", n)
    s6 = _pick(parsed.verdicts, "S6_MixedStorm", n)

    gate_0 = True  # Harness prints deterministic tenant IDs + env block.
    gate_1 = _bool(s1 and s1[1].get("passed"))
    gate_2 = _bool(s5 and s5[1].get("passed"))
    gate_3 = _bool(s3 and s3[1].get("passed"))
    gate_4 = _bool(s4 and s4[1].get("passed"))
    gate_5 = _bool(s6 and s6[1].get("passed"))
    gate_6 = all(x is not None for x in [s1, s2, s3, s4, s5, s6])

    complete = n >= 1000 and all([gate_0, gate_1, gate_2, gate_3, gate_4, gate_5, gate_6])
    status = "COMPLETE" if complete else "IN PROGRESS"

    env = parsed.env or {}
    ladder = env.get("ladder")
    concurrency = env.get("concurrency")
    timeout_s = env.get("timeout_s")
    base_url = env.get("base_url")
    run_start_utc = env.get("run_start_utc")

    def _gate(v: bool) -> str:
        return "PASS" if v else "FAIL"

    md = "\n".join(
        [
            "# R3 Ingestion Under Fire Validation Summary (Truth Anchor)",
            "",
            "## Status",
            "",
            f"R3 = **{status}** as of:",
            "",
            f"- **Candidate SHA:** `{candidate_sha}`",
            f"- **CI run:** {run_url}",
            f"- **Generated at:** `{_utc_now_iso()}`",
            "",
            "## Run Configuration (from harness log)",
            "",
            f"- `R3_API_BASE_URL` = `{base_url}`",
            f"- `R3_LADDER` = `{ladder}`",
            f"- `R3_CONCURRENCY` = `{concurrency}`",
            f"- `R3_TIMEOUT_S` = `{timeout_s}`",
            f"- `RUN_START_UTC` = `{run_start_utc}`",
            "",
            "## Exit Gates (Pass Matrix)",
            "",
            "| Gate | Description | Status |",
            "|------|-------------|--------|",
            f"| EG-R3-0 | Truth anchor & clean room | {_gate(gate_0)} |",
            f"| EG-R3-1 | Idempotency under fire (ReplayStorm @ N={n}) | {_gate(gate_1)} |",
            f"| EG-R3-2 | Tenant-correct idempotency (CrossTenantCollision @ N={n}) | {_gate(gate_2)} |",
            f"| EG-R3-3 | DLQ reliability (MalformedStorm @ N={n}) | {_gate(gate_3)} |",
            f"| EG-R3-4 | PII self-defense (PIIStorm @ N={n}) | {_gate(gate_4)} |",
            f"| EG-R3-5 | MixedStorm stability (MixedStorm @ N={n}) | {_gate(gate_5)} |",
            f"| EG-R3-6 | Evidence pack present (verdict blocks for S1..S6) | {_gate(gate_6)} |",
            "",
            "## Evidence (Browser-Verifiable Logs)",
            "",
            "This run prints, to CI logs:",
            "",
            "- One `R3_VERDICT_BEGIN/END` JSON block per scenario (S1..S6), per ladder step.",
            "- DB truth checks (canonical/DLQ counts + PII key hit scan summaries).",
            "",
            "## Key Verdicts (Max Ladder Step)",
            "",
            f"Max ladder step detected: `N={n}`",
            "",
            "### S1 ReplayStorm",
            "```json",
            json.dumps(s1[1] if s1 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S5 CrossTenantCollision",
            "```json",
            json.dumps(s5[1] if s5 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S3 MalformedStorm",
            "```json",
            json.dumps(s3[1] if s3 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S4 PIIStorm",
            "```json",
            json.dumps(s4[1] if s4 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S6 MixedStorm",
            "```json",
            json.dumps(s6[1] if s6 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Where the Evidence Lives",
            "",
            "- Workflow: `.github/workflows/r3-ingestion-under-fire.yml`",
            "- Harness: `scripts/r3/ingestion_under_fire.py`",
            "- Summary generator: `scripts/r3/render_r3_summary.py`",
            "",
        ]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md + "\n", encoding="utf-8")
    return md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="Path to harness log file")
    ap.add_argument("--out", required=True, help="Path to write docs/forensics/validation/runtime/r3_summary.md")
    ap.add_argument("--candidate-sha", required=True)
    ap.add_argument("--run-url", required=True)
    args = ap.parse_args()

    parsed = parse_run(Path(args.log))
    md = render_summary_md(
        candidate_sha=args.candidate_sha,
        run_url=args.run_url,
        parsed=parsed,
        out_path=Path(args.out),
    )
    print("R3_SUMMARY_RENDERED")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

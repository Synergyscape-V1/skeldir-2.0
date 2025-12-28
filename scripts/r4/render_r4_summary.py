from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_BEGIN = re.compile(r"^R4_VERDICT_BEGIN (.+)$")
_END = re.compile(r"^R4_VERDICT_END (.+)$")


@dataclass(frozen=True)
class ParsedRun:
    env: dict[str, Any]
    verdicts: dict[str, dict[str, Any]]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_env_block(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "=== R4_ENV ===":
            buf: list[str] = []
            for j in range(i + 1, min(i + 4000, len(lines))):
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


def render_summary_md(*, candidate_sha: str, run_url: str, parsed: ParsedRun, out_path: Path) -> str:
    env = parsed.env or {}
    verdicts = parsed.verdicts or {}

    def _pick(name: str) -> dict[str, Any] | None:
        return verdicts.get(name)

    s1 = _pick("S1_PoisonPill_N10")
    s2 = _pick("S2_CrashAfterWritePreAck_N10")
    s3 = _pick("S3_RLSProbe_N1")
    s4 = _pick("S4_RunawayNoStarve_N10")
    s5 = _pick("S5_LeastPrivilege_N1")

    gate_0 = bool(env.get("candidate_sha") and env.get("tenants") and verdicts)
    gate_1 = bool(s1 and s1.get("passed") is True)
    gate_2 = bool(s2 and s2.get("passed") is True)
    gate_3 = bool(s3 and s3.get("passed") is True)
    gate_4 = bool(s4 and s4.get("passed") is True)
    gate_5 = bool(s5 and s5.get("passed") is True)
    gate_6 = all(x is not None for x in [s1, s2, s3, s4, s5])

    complete = all([gate_0, gate_1, gate_2, gate_3, gate_4, gate_5, gate_6])
    status = "COMPLETE" if complete else "IN PROGRESS"

    def _gate(v: bool) -> str:
        return "PASS" if v else "FAIL"

    md = "\n".join(
        [
            "# R4 Worker Failure Semantics Summary (Truth Anchor)",
            "",
            "## Status",
            "",
            f"R4 = **{status}** as of:",
            "",
            f"- **Candidate SHA:** `{candidate_sha}`",
            f"- **CI run:** {run_url}",
            f"- **Generated at:** `{_utc_now_iso()}`",
            "",
            "## Run Configuration (from harness log)",
            "",
            f"- `broker_url` = `{env.get('celery', {}).get('broker_url')}`",
            f"- `result_backend` = `{env.get('celery', {}).get('result_backend')}`",
            f"- `acks_late` = `{env.get('celery', {}).get('acks_late')}`",
            f"- `reject_on_worker_lost` = `{env.get('celery', {}).get('reject_on_worker_lost')}`",
            f"- `acks_on_failure_or_timeout` = `{env.get('celery', {}).get('acks_on_failure_or_timeout')}`",
            f"- `prefetch_multiplier` = `{env.get('celery', {}).get('prefetch_multiplier')}`",
            f"- `tenant_a` = `{env.get('tenants', {}).get('tenant_a')}`",
            f"- `tenant_b` = `{env.get('tenants', {}).get('tenant_b')}`",
            "",
            "## Exit Gates (Pass Matrix)",
            "",
            "| Gate | Description | Status |",
            "|------|-------------|--------|",
            f"| EG-R4-0 | Instrument & SHA binding | {_gate(gate_0)} |",
            f"| EG-R4-1 | Retry/DLQ physics (PoisonPill N=10) | {_gate(gate_1)} |",
            f"| EG-R4-2 | Idempotency under crash (CrashAfterWritePreAck N=10) | {_gate(gate_2)} |",
            f"| EG-R4-3 | Worker RLS enforcement (Cross-tenant probe) | {_gate(gate_3)} |",
            f"| EG-R4-4 | Timeouts & starvation resistance (Runaway + sentinels) | {_gate(gate_4)} |",
            f"| EG-R4-5 | Least privilege reality (probes fail) | {_gate(gate_5)} |",
            f"| EG-R4-6 | Evidence pack present (verdict blocks S1..S5) | {_gate(gate_6)} |",
            "",
            "## Evidence (Browser-Verifiable Logs)",
            "",
            "This run prints, to CI logs, one `R4_VERDICT_BEGIN/END` JSON block per scenario.",
            "",
            "Log step containing verdict blocks: `Run R4 harness` in `.github/workflows/r4-worker-failure-semantics.yml`.",
            "",
            "## Key Verdicts",
            "",
            "### S1 PoisonPill (N=10)",
            "```json",
            json.dumps(s1 or {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S2 CrashAfterWritePreAck (N=10)",
            "```json",
            json.dumps(s2 or {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S3 RLSProbe (N=1)",
            "```json",
            json.dumps(s3 or {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S4 RunawayNoStarve (sentinels N=10)",
            "```json",
            json.dumps(s4 or {}, indent=2, sort_keys=True),
            "```",
            "",
            "### S5 LeastPrivilege (N=1)",
            "```json",
            json.dumps(s5 or {}, indent=2, sort_keys=True),
            "```",
            "",
            "## Where the Evidence Lives",
            "",
            "- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`",
            "- Harness: `scripts/r4/worker_failure_semantics.py`",
            "- Summary generator: `scripts/r4/render_r4_summary.py`",
            "",
        ]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md + "\n", encoding="utf-8")
    return md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--candidate-sha", required=True)
    ap.add_argument("--run-url", required=True)
    args = ap.parse_args()

    parsed = parse_run(args.log)
    md = render_summary_md(
        candidate_sha=args.candidate_sha,
        run_url=args.run_url,
        parsed=parsed,
        out_path=args.out,
    )
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


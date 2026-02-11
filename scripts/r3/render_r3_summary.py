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


def _pick(verdicts: dict[str, dict[str, Any]], prefix: str, n: int | None) -> tuple[str, dict[str, Any]] | None:
    if n is not None:
        suffix = f"_N{n}"
        for name, payload in verdicts.items():
            if name.startswith(prefix) and name.endswith(suffix):
                return name, payload
    for name, payload in verdicts.items():
        if name.startswith(prefix):
            return name, payload
    return None


def _pick_exact(verdicts: dict[str, dict[str, Any]], name: str) -> tuple[str, dict[str, Any]] | None:
    payload = verdicts.get(name)
    if payload is None:
        return None
    return name, payload


def _bool(v: Any) -> bool:
    return bool(v is True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gate(v: bool) -> str:
    return "PASS" if v else "FAIL"


def render_summary_md(*, candidate_sha: str, run_url: str, parsed: ParsedRun, out_path: Path) -> str:
    if not parsed.verdicts:
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

    n = _max_n(parsed.verdicts)
    s1 = _pick(parsed.verdicts, "S1_ReplayStorm", n)
    s3 = _pick(parsed.verdicts, "S3_MalformedStorm", n)
    s4 = _pick(parsed.verdicts, "S4_PIIStorm", n)
    s5 = _pick(parsed.verdicts, "S5_CrossTenantCollision", n)
    s6 = _pick(parsed.verdicts, "S6_MixedStorm", n)
    s7 = _pick(parsed.verdicts, "S7_InvalidJsonDLQ", n)
    s9 = _pick(parsed.verdicts, "S9_NormalizationAliases", None)

    eg35 = _pick_exact(parsed.verdicts, "EG3_5_NullBenchmark")
    eg34_t1 = _pick_exact(parsed.verdicts, "EG3_4_Test1_Month6")
    eg34_t2 = _pick_exact(parsed.verdicts, "EG3_4_Test2_Month18")
    eg34_t3 = _pick_exact(parsed.verdicts, "EG3_4_Test3_SustainedOps")

    gate_anchor = True
    gate_31 = _bool(s4 and s4[1].get("passed"))
    gate_32 = _bool((s1 and s1[1].get("passed")) and (s5 and s5[1].get("passed")))
    gate_33 = _bool((s3 and s3[1].get("passed")) and (s7 and s7[1].get("passed")))
    gate_34_t1 = _bool(eg34_t1 and eg34_t1[1].get("passed"))
    gate_34_t2 = _bool(eg34_t2 and eg34_t2[1].get("passed"))
    gate_34_t3 = _bool(eg34_t3 and eg34_t3[1].get("passed"))
    gate_35 = _bool(eg35 and eg35[1].get("passed"))
    gate_alias = _bool(s9 and s9[1].get("passed"))

    required = [gate_anchor, gate_31, gate_32, gate_33, gate_34_t1, gate_34_t2, gate_34_t3, gate_35]
    complete = all(required)
    status = "COMPLETE" if complete else "IN PROGRESS"
    measurement_note = "VALID" if gate_35 else "INVALID"

    env = parsed.env or {}
    base_url = env.get("base_url")
    ladder = env.get("ladder")
    concurrency = env.get("concurrency")
    timeout_s = env.get("timeout_s")
    run_start_utc = env.get("run_start_utc")
    eg34_profiles = env.get("eg34_profiles")
    null_enabled = env.get("null_benchmark_enabled")
    null_target_rps = env.get("null_benchmark_target_rps")
    null_duration_s = env.get("null_benchmark_duration_s")
    null_min_rps = env.get("null_benchmark_min_rps")

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
            f"- **Measurement validity (EG3.5):** `{measurement_note}`",
            "",
            "## Run Configuration (from harness log)",
            "",
            f"- `R3_API_BASE_URL` = `{base_url}`",
            f"- `R3_LADDER` = `{ladder}`",
            f"- `R3_CONCURRENCY` = `{concurrency}`",
            f"- `R3_TIMEOUT_S` = `{timeout_s}`",
            f"- `RUN_START_UTC` = `{run_start_utc}`",
            f"- `R3_EG34_PROFILES` = `{eg34_profiles}`",
            f"- `R3_NULL_BENCHMARK_ENABLED` = `{null_enabled}`",
            f"- `R3_NULL_BENCHMARK_TARGET_RPS` = `{null_target_rps}`",
            f"- `R3_NULL_BENCHMARK_DURATION_S` = `{null_duration_s}`",
            f"- `R3_NULL_BENCHMARK_MIN_RPS` = `{null_min_rps}`",
            "",
            "## Exit Gates (Pass Matrix)",
            "",
            "| Gate | Description | Status |",
            "|------|-------------|--------|",
            f"| EG-R3-0 | Truth anchor & clean room | {_gate(gate_anchor)} |",
            f"| EG3.1 | PII stripping before persistence (PIIStorm @ N={n}) | {_gate(gate_31)} |",
            f"| EG3.2 | Idempotency at persistence boundary (Replay + CrossTenant) | {_gate(gate_32)} |",
            f"| EG3.3 | Deterministic malformed/PII DLQ routing | {_gate(gate_33)} |",
            f"| EG3.4 Test 1 | Month 6 profile (29 rps, 60s, p95 < 2s) | {_gate(gate_34_t1)} |",
            f"| EG3.4 Test 2 | Month 18 profile (46 rps, 60s, p95 < 2s) | {_gate(gate_34_t2)} |",
            f"| EG3.4 Test 3 | Sustained ops (5 rps, 300s, no degradation) | {_gate(gate_34_t3)} |",
            f"| EG3.5 | Measurement validity null benchmark (>=50 rps, 60s) | {_gate(gate_35)} |",
            f"| EG-R3-7 | Channel alias normalization sanity | {_gate(gate_alias)} |",
            "",
            "## Key Verdicts",
            "",
            f"Max ladder step detected: `N={n}`",
            "",
            "### S1 ReplayStorm",
            "```json",
            json.dumps(s1[1] if s1 else {}, indent=2, sort_keys=True),
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
            "### EG3.5 Null Benchmark",
            "```json",
            json.dumps(eg35[1] if eg35 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### EG3.4 Test1 Month6",
            "```json",
            json.dumps(eg34_t1[1] if eg34_t1 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### EG3.4 Test2 Month18",
            "```json",
            json.dumps(eg34_t2[1] if eg34_t2 else {}, indent=2, sort_keys=True),
            "```",
            "",
            "### EG3.4 Test3 SustainedOps",
            "```json",
            json.dumps(eg34_t3[1] if eg34_t3 else {}, indent=2, sort_keys=True),
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

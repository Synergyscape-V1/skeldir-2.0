"""Runner-wide CPU / starvation probe for the Phase 8 full-physics leg.

Ordered-plan step 3 instrumentation (observation only; no threshold reads
it). Samples, every interval while the R3 leg runs:

  - /proc/stat aggregate busy share,
  - /proc/pressure/cpu (PSI "some"/"full": the direct measure of
    runner-wide CPU starvation and lost work),
  - cgroup CPU throttling counters,
  - per-process CPU time deltas from /proc, classified into the composed
    topology roles (generator, api, auth_root, postgres, workers,
    conduit, queue probe, pack driver).

The summary artifact quantifies where the 4-vCPU runner's seconds went
during a failing leg versus a passing leg, so the next repair targets a
measured cause instead of a hypothesis.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _read_proc_stat_busy() -> tuple[int, int] | None:
    text = _read_text("/proc/stat")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("cpu "):
            fields = [int(part) for part in line.split()[1:]]
            if len(fields) < 5:
                return None
            total = sum(fields)
            idle = fields[3] + fields[4]
            return total, total - idle
    return None


def _read_psi_cpu() -> dict[str, dict[str, float]] | None:
    text = _read_text("/proc/pressure/cpu")
    if not text:
        return None
    out: dict[str, dict[str, float]] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        values: dict[str, float] = {}
        for part in parts[1:]:
            if "=" not in part:
                continue
            key, _, raw = part.partition("=")
            try:
                values[key] = float(raw)
            except ValueError:
                continue
        out[parts[0]] = values
    return out


def _read_cgroup_throttle() -> dict[str, int] | None:
    for path in ("/sys/fs/cgroup/cpu.stat", "/sys/fs/cgroup/cpu/cpu.stat"):
        text = _read_text(path)
        if not text:
            continue
        out: dict[str, int] = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2:
                try:
                    out[parts[0]] = int(parts[1])
                except ValueError:
                    continue
        if out:
            return out
    return None


def _read_loadavg() -> dict[str, float] | None:
    text = _read_text("/proc/loadavg")
    if not text:
        return None
    parts = text.split()
    if len(parts) < 3:
        return None
    try:
        return {"1m": float(parts[0]), "5m": float(parts[1]), "15m": float(parts[2])}
    except ValueError:
        return None


def _classify(cmdline: str, comm: str) -> str:
    candidate = cmdline or comm
    if "ingestion_under_fire" in candidate:
        return "generator"
    if "runner_cpu_probe" in candidate:
        return "probe_self"
    if "llm_background_load" in candidate:
        return "conduit"
    if "queue_liveness_probe" in candidate:
        return "queue_probe"
    if "run_phase8_closure_pack" in candidate:
        return "pack_driver"
    if "postgres" in candidate:
        return "postgres"
    if "celery" in candidate:
        if "bayesian" in candidate:
            return "worker_bayesian"
        if "b23_match_engine" in candidate:
            return "worker_b23"
        return "worker"
    if "uvicorn" in candidate and "app.main" in candidate:
        return "api"
    if "uvicorn" in candidate:
        return "api"
    if "auth_service" in candidate:
        return "auth_root"
    if "mock_platform" in candidate:
        return "mock_platform"
    return "other"


def _snapshot_processes() -> dict[int, tuple[str, str, int]]:
    snapshot: dict[int, tuple[str, str, int]] = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        stat_text = _read_text(f"/proc/{pid}/stat")
        if not stat_text:
            continue
        open_idx = stat_text.find("(")
        close_idx = stat_text.rfind(")")
        if open_idx < 0 or close_idx < 0:
            continue
        comm = stat_text[open_idx + 1 : close_idx]
        fields = stat_text[close_idx + 2 :].split()
        if len(fields) < 13:
            continue
        try:
            utime = int(fields[11])
            stime = int(fields[12])
        except ValueError:
            continue
        cmdline_text = _read_text(f"/proc/{pid}/cmdline") or ""
        cmdline = cmdline_text.replace("\x00", " ").strip()
        if not cmdline:
            continue
        snapshot[pid] = (_classify(cmdline, comm), comm[:40], utime + stime)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument("--interval-s", type=float, default=2.0)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--jsonl", type=Path, default=None)
    args = parser.parse_args()

    if args.duration_s <= 0 or args.interval_s <= 0:
        print("duration-s and interval-s must be > 0", file=sys.stderr)
        return 2

    jsonl_path = args.jsonl or args.artifact.with_suffix(".jsonl")
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = _now_utc()
    start_monotonic = time.monotonic()
    deadline = start_monotonic + args.duration_s

    class_cpu_ticks: dict[str, int] = {}
    class_cpu_max_pct: dict[str, float] = {}
    pid_cpu_ticks: dict[int, int] = {}
    pid_meta: dict[int, tuple[str, str]] = {}
    busy_pct_samples: list[float] = []
    psi_some_avg10_samples: list[float] = []
    psi_first: dict[str, float] = {}
    psi_last: dict[str, float] = {}
    throttle_first: dict[str, int] | None = None
    throttle_last: dict[str, int] | None = None
    sample_count = 0

    prev_stat = _read_proc_stat_busy()
    prev_procs = _snapshot_processes()
    prev_psi = _read_psi_cpu()
    last_monotonic = start_monotonic

    jsonl_handle = jsonl_path.open("w", encoding="utf-8")
    try:
        while time.monotonic() < deadline:
            time.sleep(args.interval_s)
            loop_now = time.monotonic()
            interval_s = max(0.001, loop_now - last_monotonic)
            last_monotonic = loop_now

            cur_stat = _read_proc_stat_busy()
            cur_procs = _snapshot_processes()
            cur_psi = _read_psi_cpu()
            cur_throttle = _read_cgroup_throttle()
            if throttle_first is None and cur_throttle is not None:
                throttle_first = dict(cur_throttle)
            if cur_throttle is not None:
                throttle_last = dict(cur_throttle)

            pid_delta_ticks: dict[int, int] = {}
            class_delta_ticks: dict[str, int] = {}
            for pid, (cls, comm, ticks) in cur_procs.items():
                prev_entry = prev_procs.get(pid)
                delta = max(0, ticks - prev_entry[2]) if prev_entry else 0
                if delta <= 0:
                    continue
                pid_delta_ticks[pid] = delta
                pid_meta[pid] = (cls, comm)
                pid_cpu_ticks[pid] = pid_cpu_ticks.get(pid, 0) + delta
                class_delta_ticks[cls] = class_delta_ticks.get(cls, 0) + delta

            if cur_stat and prev_stat:
                total_delta = max(1, cur_stat[0] - prev_stat[0])
                busy_delta = max(0, cur_stat[1] - prev_stat[1])
                total_busy_pct = 100.0 * busy_delta / total_delta
            else:
                total_busy_pct = 0.0
            busy_pct_samples.append(total_busy_pct)

            classes_pct: dict[str, float] = {}
            for cls, delta in class_delta_ticks.items():
                cpu_pct = 100.0 * (delta / _CLK_TCK) / interval_s
                classes_pct[cls] = round(cpu_pct, 3)
                class_cpu_ticks[cls] = class_cpu_ticks.get(cls, 0) + delta
                class_cpu_max_pct[cls] = max(class_cpu_max_pct.get(cls, 0.0), cpu_pct)

            psi_entry: dict[str, Any] = {}
            if cur_psi:
                for kind in ("some", "full"):
                    values = cur_psi.get(kind)
                    if not values:
                        continue
                    entry: dict[str, Any] = {"avg10": values.get("avg10")}
                    prev_values = (prev_psi or {}).get(kind) or {}
                    if "total" in values:
                        if kind not in psi_first:
                            psi_first[kind] = values["total"]
                        psi_last[kind] = values["total"]
                        if "total" in prev_values:
                            entry["stall_us_delta"] = round(
                                max(0.0, values["total"] - prev_values["total"]), 1
                            )
                    if kind == "some" and "avg10" in values:
                        psi_some_avg10_samples.append(values["avg10"])
                    psi_entry[kind] = entry

            top_interval = sorted(
                (
                    {
                        "pid": pid,
                        "class": pid_meta[pid][0],
                        "comm": pid_meta[pid][1],
                        "cpu_pct": round(100.0 * (delta / _CLK_TCK) / interval_s, 3),
                    }
                    for pid, delta in pid_delta_ticks.items()
                ),
                key=lambda item: item["cpu_pct"],
                reverse=True,
            )[:5]

            sample = {
                "ts": _now_utc(),
                "idx": sample_count,
                "total_busy_pct": round(total_busy_pct, 3),
                "classes_cpu_pct": classes_pct,
                "psi": psi_entry,
                "loadavg": _read_loadavg(),
                "top": top_interval,
            }
            jsonl_handle.write(json.dumps(sample) + "\n")
            jsonl_handle.flush()
            sample_count += 1

            prev_stat = cur_stat
            prev_procs = cur_procs
            prev_psi = cur_psi
    finally:
        jsonl_handle.close()

    finished_at = _now_utc()
    runtime_s = round(time.monotonic() - start_monotonic, 3)
    classes: dict[str, Any] = {}
    for cls, ticks in sorted(class_cpu_ticks.items()):
        classes[cls] = {
            "cpu_s_total": round(ticks / _CLK_TCK, 3),
            "cpu_pct_avg": round(100.0 * (ticks / _CLK_TCK) / runtime_s, 3)
            if runtime_s > 0
            else 0.0,
            "cpu_pct_max": round(class_cpu_max_pct.get(cls, 0.0), 3),
        }
    top_processes = sorted(
        (
            {
                "pid": pid,
                "class": pid_meta[pid][0],
                "comm": pid_meta[pid][1],
                "cpu_s_total": round(ticks / _CLK_TCK, 3),
            }
            for pid, ticks in pid_cpu_ticks.items()
            if pid in pid_meta
        ),
        key=lambda item: item["cpu_s_total"],
        reverse=True,
    )[:12]

    throttle_delta: dict[str, int] | None = None
    if throttle_first is not None and throttle_last is not None:
        throttle_delta = {
            key: max(0, value - throttle_first.get(key, value))
            for key, value in throttle_last.items()
            if key in ("nr_periods", "nr_throttled", "throttled_usec")
        }

    status = "ok" if sample_count >= 2 else "failed"
    summary = {
        "status": status,
        "error": None if status == "ok" else "insufficient samples",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": args.duration_s,
        "runtime_s": runtime_s,
        "interval_s": args.interval_s,
        "sample_count": sample_count,
        "cpu_count": os.cpu_count(),
        "total_busy_pct_avg": round(sum(busy_pct_samples) / len(busy_pct_samples), 3)
        if busy_pct_samples
        else None,
        "total_busy_pct_max": round(max(busy_pct_samples), 3)
        if busy_pct_samples
        else None,
        # PSI "some.total" is the cumulative microseconds during which at
        # least one runnable task was stalled on CPU; the delta across
        # the leg is the runner's measured starvation budget.
        "psi_cpu_some_stall_us_total": (
            round(max(0.0, psi_last.get("some", 0.0) - psi_first.get("some", 0.0)), 1)
            if "some" in psi_first and "some" in psi_last
            else None
        ),
        "psi_cpu_some_avg10_max": max(psi_some_avg10_samples)
        if psi_some_avg10_samples
        else None,
        "throttle_delta": throttle_delta,
        "loadavg_end": _read_loadavg(),
        "classes": classes,
        "top_processes": top_processes,
    }

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "status",
                    "sample_count",
                    "total_busy_pct_avg",
                    "psi_cpu_some_stall_us_total",
                    "classes",
                )
            },
            indent=2,
        )
    )
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

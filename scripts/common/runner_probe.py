"""
Runner Physics Probe
Collects runtime environment metrics to validate runner capacity.
"""
import json
import multiprocessing
import os
import platform
import subprocess
import sys
from pathlib import Path

def _get_cpu_info():
    info = {
        "count": multiprocessing.cpu_count(),
        "model": "unknown",
        "arch": platform.machine(),
    }
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        info["model"] = line.split(":", 1)[1].strip()
                        break
        elif platform.system() == "Darwin":
             info["model"] = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
    except Exception:
        pass
    return info

def _get_memory_info():
    info = {"total_gb": 0, "available_gb": 0}
    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo", "r") as f:
                mem_total = 0
                mem_available = 0
                for line in f:
                    if "MemTotal" in line:
                        mem_total = int(line.split()[1])
                    if "MemAvailable" in line:
                        mem_available = int(line.split()[1])
                info["total_gb"] = round(mem_total / 1024 / 1024, 2)
                info["available_gb"] = round(mem_available / 1024 / 1024, 2)
    except Exception:
        pass
    return info

def _get_cgroup_limits():
    limits = {"cpu_quota": None, "memory_limit_bytes": None}
    try:
        if os.path.exists("/sys/fs/cgroup/cpu.max"):
             with open("/sys/fs/cgroup/cpu.max", "r") as f:
                content = f.read().strip()
                limits["cpu_quota"] = content
        if os.path.exists("/sys/fs/cgroup/memory.max"):
             with open("/sys/fs/cgroup/memory.max", "r") as f:
                 content = f.read().strip()
                 limits["memory_limit_bytes"] = content
    except Exception:
        pass
    return limits

import datetime

def main():
    probe_data = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "container_limits": _get_cgroup_limits(),
        "env": {
            "GITHUB_ACTION": os.getenv("GITHUB_ACTION"),
            "GITHUB_RUN_ID": os.getenv("GITHUB_RUN_ID"),
            "RUNNER_NAME": os.getenv("RUNNER_NAME"),
        }
    }
    
    # Default to printing to stdout, but if an artifact path is provided via env, write there too
    print(json.dumps(probe_data, indent=2))
    
    artifact_dir = os.getenv("B07_P8_ARTIFACT_DIR")
    if artifact_dir:
        out_path = Path(artifact_dir) / "runner_physics_probe.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(probe_data, indent=2), encoding="utf-8")
        print(f"\nWritten to {out_path}")

if __name__ == "__main__":
    main()

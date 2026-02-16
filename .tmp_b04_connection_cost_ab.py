import asyncio
import os
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(r"c:\Users\ayewhy\II SKELDIR II")
BACKEND = ROOT / "backend"
BASE = "http://127.0.0.1:8030"

async def wait_ready(timeout_s: int = 90):
    async with httpx.AsyncClient() as c:
        start=time.perf_counter()
        while time.perf_counter()-start < timeout_s:
            try:
                r=await c.get(BASE+"/health/live", timeout=2)
                if r.status_code==200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
    raise RuntimeError("not ready")

async def run_case(label: str, n: int, conc: int, keepalive: int):
    sem=asyncio.Semaphore(conc)
    limits=httpx.Limits(max_connections=conc, max_keepalive_connections=keepalive)
    lat=[]
    timeout_count = 0
    request_error_count = 0
    async with httpx.AsyncClient(limits=limits) as c:
        async def one(i:int):
            nonlocal timeout_count, request_error_count
            async with sem:
                headers={"Connection":"close"} if keepalive==0 else {}
                t=time.perf_counter()
                try:
                    r=await c.get(BASE+"/health/live", headers=headers, timeout=30)
                    lat.append((time.perf_counter()-t)*1000)
                    return r.status_code
                except httpx.TimeoutException:
                    timeout_count += 1
                    return "timeout"
                except httpx.RequestError:
                    request_error_count += 1
                    return "request_error"
        t0=time.perf_counter()
        codes=await asyncio.gather(*[one(i) for i in range(n)])
        dt=time.perf_counter()-t0
    q=statistics.quantiles(lat, n=100) if len(lat) >= 100 else [0]*99
    ok = sum(1 for c in codes if isinstance(c, int) and c == 200)
    non200 = sum(1 for c in codes if isinstance(c, int) and c != 200)
    return {
        "label":label,
        "n":n,
        "conc":conc,
        "keepalive":keepalive,
        "seconds":round(dt,4),
        "rps_effective_ok":round(ok/dt,2),
        "ok_200": ok,
        "non200": non200,
        "timeouts": timeout_count,
        "request_errors": request_error_count,
        "lat_ms_p50":round(q[49],2) if q[49] else 0.0,
        "lat_ms_p95":round(q[94],2) if q[94] else 0.0,
        "lat_ms_p99":round(q[98],2) if q[98] else 0.0,
    }


def main():
    env=os.environ.copy()
    env.update({
        "PYTHONPATH":"backend",
        "DATABASE_URL":"postgresql://app_user:app_user@127.0.0.1:5432/r3_b04_phase3",
        "MIGRATION_DATABASE_URL":"postgresql://postgres:postgres@127.0.0.1:5432/r3_b04_phase3",
        "DATABASE_POOL_SIZE":"20",
        "DATABASE_MAX_OVERFLOW":"0",
        "DATABASE_POOL_TIMEOUT_SECONDS":"3",
        "DATABASE_POOL_TOTAL_CAP":"30",
        "INGESTION_FOLLOWUP_TASKS_ENABLED":"false",
    })

    cmd=[sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8030","--workers","2","--no-access-log"]
    proc=subprocess.Popen(cmd, cwd=str(BACKEND), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        asyncio.run(wait_ready())
        ka=asyncio.run(run_case("keepalive", n=2000, conc=200, keepalive=200))
        cl=asyncio.run(run_case("connection_close", n=2000, conc=200, keepalive=0))
        out={"keepalive":ka,"connection_close":cl,
             "delta":{
                "seconds_diff_close_minus_keepalive":round(cl["seconds"]-ka["seconds"],4),
                "rps_effective_ok_diff_keepalive_minus_close":round(ka["rps_effective_ok"]-cl["rps_effective_ok"],2),
                "p50_ms_diff_close_minus_keepalive":round(cl["lat_ms_p50"]-ka["lat_ms_p50"],2),
                "p95_ms_diff_close_minus_keepalive":round(cl["lat_ms_p95"]-ka["lat_ms_p95"],2),
                "p99_ms_diff_close_minus_keepalive":round(cl["lat_ms_p99"]-ka["lat_ms_p99"],2),
                "timeouts_diff_close_minus_keepalive":cl["timeouts"]-ka["timeouts"],
                "request_errors_diff_close_minus_keepalive":cl["request_errors"]-ka["request_errors"],
             }}
        print("CONNECTION_COST_AB_BEGIN")
        import json
        print(json.dumps(out, indent=2))
        print("CONNECTION_COST_AB_END")
    finally:
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

if __name__=="__main__":
    main()

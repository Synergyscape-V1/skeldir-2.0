"""
CI helper: verify /health/worker data-plane probe and persist output.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    return parser.parse_args()


def _write_log(log_path: Path, attempt: int, status_code: int, body_text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"ATTEMPT={attempt}\n")
        handle.write(f"HTTP_CODE={status_code}\n")
        handle.write(body_text + "\n")


def _parse_body(body_text: str) -> dict[str, Any]:
    try:
        return json.loads(body_text)
    except json.JSONDecodeError:
        return {"raw": body_text}


def main() -> int:
    args = _parse_args()
    log_path = Path(args.log_path)
    last_status = 0
    last_body: dict[str, Any] = {}
    for attempt in range(1, args.attempts + 1):
        resp = requests.get(args.url, timeout=20)
        last_status = resp.status_code
        last_body = _parse_body(resp.text)
        print(f"health_worker_probe_attempt_{attempt}_response_begin", flush=True)
        print(resp.status_code, flush=True)
        print(resp.text, flush=True)
        print(f"health_worker_probe_attempt_{attempt}_response_end", flush=True)
        _write_log(log_path, attempt, resp.status_code, resp.text)
        if resp.status_code == 200:
            break
        time.sleep(args.delay_seconds)

    if last_status != 200 or last_body.get("worker") != "ok" or last_body.get("broker") != "ok":
        print(
            f"health_worker_probe_failed code={last_status} body={last_body}",
            flush=True,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

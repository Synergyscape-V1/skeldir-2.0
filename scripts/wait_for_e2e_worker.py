import os
import time
from urllib.parse import urljoin

import httpx

API_BASE_URL = os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT_S = int(os.getenv("E2E_WAIT_TIMEOUT_S", "60"))


def wait_for_worker_probe() -> None:
    deadline = time.time() + TIMEOUT_S
    last_error = None
    url = urljoin(API_BASE_URL.rstrip("/") + "/", "/health/worker".lstrip("/"))
    while time.time() < deadline:
        try:
            res = httpx.get(url, timeout=5.0)
            if res.status_code == 200:
                try:
                    body = res.json()
                except ValueError as exc:
                    last_error = f"invalid_json: {exc}"
                else:
                    if body.get("worker") == "ok":
                        return
            last_error = f"status={res.status_code} body={res.text[:300]}"
        except httpx.RequestError as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Worker probe not ok after {TIMEOUT_S}s: {url} ({last_error})")


def main() -> None:
    wait_for_worker_probe()


if __name__ == "__main__":
    main()

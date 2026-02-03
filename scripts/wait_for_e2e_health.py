import os
import time
from urllib.parse import urljoin

import httpx
import psycopg2

API_BASE_URL = os.getenv("E2E_API_BASE_URL", "http://127.0.0.1:8000")
MOCK_BASE_URL = os.getenv("E2E_MOCK_BASE_URL", "http://127.0.0.1:8080")
DB_URL = os.getenv("E2E_DB_URL", "postgresql://skeldir:skeldir_e2e@127.0.0.1:5432/skeldir_e2e")
TIMEOUT_S = int(os.getenv("E2E_WAIT_TIMEOUT_S", "60"))


def wait_for_db() -> None:
    deadline = time.time() + TIMEOUT_S
    last_error = None
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(DB_URL)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return
            finally:
                conn.close()
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"DB not ready after {TIMEOUT_S}s: {last_error}")


def wait_for_http(base_url: str, path: str) -> None:
    deadline = time.time() + TIMEOUT_S
    last_error = None
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    while time.time() < deadline:
        try:
            res = httpx.get(url, timeout=2.0)
            if res.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"HTTP not ready after {TIMEOUT_S}s: {url} ({last_error})")


def main() -> None:
    wait_for_db()
    wait_for_http(API_BASE_URL, "/health/ready")
    wait_for_http(MOCK_BASE_URL, "/health/ready")


if __name__ == "__main__":
    main()

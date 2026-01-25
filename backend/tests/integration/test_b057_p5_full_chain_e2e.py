import base64
import hashlib
import hmac
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import create_engine, text


@dataclass(frozen=True)
class _TenantFixture:
    tenant_id: UUID
    tenant_key: str
    api_key_hash: str
    shopify_secret: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required for B0.5.7-P5 integration tests")
    return value


def _runtime_sync_db_url() -> str:
    explicit = os.getenv("B057_P5_RUNTIME_DATABASE_URL")
    if explicit:
        return explicit
    runtime_url = _require_env("DATABASE_URL")
    if runtime_url.startswith("postgresql+asyncpg://"):
        return runtime_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return runtime_url


def _runtime_async_db_url(runtime_sync: str) -> str:
    if runtime_sync.startswith("postgresql+asyncpg://"):
        return runtime_sync
    return runtime_sync.replace("postgresql://", "postgresql+asyncpg://", 1)


def _artifact_dir() -> Path:
    explicit = os.getenv("B057_P5_ARTIFACT_DIR")
    if explicit:
        path = Path(explicit)
    else:
        path = _repo_root() / "artifacts" / "b057-p5"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ready(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            res = httpx.get(f"{base_url}/health/ready", timeout=1.0)
            if res.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - best-effort polling
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"API never became ready; last_error={last_error}")


def _wait_http_200(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            res = httpx.get(url, timeout=2.0)
            if res.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for 200 from {url}: {last_error}")


def _wait_for_output(lines: list[str], substring: str, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if any(substring in line for line in lines):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for worker output containing {substring!r}")


def _start_worker(env: dict, log_path: Path) -> tuple[subprocess.Popen[str], list[str]]:
    backend_dir = _repo_root() / "backend"
    prom_dir = Path(tempfile.mkdtemp(prefix="b057_p5_prom_"))
    env = dict(env)
    env.setdefault("PROMETHEUS_MULTIPROC_DIR", str(prom_dir))
    cmd = [
        "celery",
        "-A",
        "app.celery_app.celery_app",
        "worker",
        "-P",
        "solo",
        "-Q",
        "attribution,maintenance",
        "-l",
        "INFO",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    log_fp = log_path.open("w", encoding="utf-8")

    def _reader() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            clean = line.rstrip()
            lines.append(clean)
            log_fp.write(clean + "\n")
            log_fp.flush()
        log_fp.close()

    threading.Thread(target=_reader, name="b057-p5-worker-reader", daemon=True).start()
    _wait_for_output(lines, "ready.", timeout_s=60)
    return proc, lines


def _start_exporter(env: dict, log_path: Path) -> tuple[subprocess.Popen[str], str]:
    backend_dir = _repo_root() / "backend"
    port = _free_port()
    exporter_env = dict(env)
    exporter_env["WORKER_METRICS_EXPORTER_HOST"] = "127.0.0.1"
    exporter_env["WORKER_METRICS_EXPORTER_PORT"] = str(port)
    proc = subprocess.Popen(
        [sys.executable, "-m", "app.observability.worker_metrics_exporter"],
        cwd=str(backend_dir),
        env=exporter_env,
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    exporter_url = f"http://127.0.0.1:{port}"
    _wait_http_200(f"{exporter_url}/metrics", timeout_s=30.0)
    return proc, exporter_url


def _stop_process(proc: subprocess.Popen[str]) -> None:
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:  # pragma: no cover
        proc.kill()
        proc.wait(timeout=10)


def _start_api(env: dict, log_path: Path) -> tuple[subprocess.Popen[str], str]:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    backend_dir = _repo_root() / "backend"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(backend_dir),
        env=env,
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_ready(base_url)
    return proc, base_url


def _seed_tenant(admin_db_url: str, label: str, include_shopify_secret: bool) -> _TenantFixture:
    tenant_id = uuid4()
    tenant_key = f"b057_p5_tenant_key_{label}_{tenant_id.hex[:8]}"
    api_key_hash = hashlib.sha256(tenant_key.encode("utf-8")).hexdigest()
    shopify_secret = f"b057-p5-shopify-{label}"
    notification_email = f"b057-p5-{label}-{tenant_id.hex[:8]}@example.invalid"

    engine = create_engine(admin_db_url)
    with engine.begin() as conn:
        # RAW_SQL_ALLOWLIST: test-only tenant seed for P5 end-to-end chain.
        conn.execute(
            text(
                """
                INSERT INTO public.tenants (
                  id,
                  name,
                  api_key_hash,
                  notification_email,
                  shopify_webhook_secret
                )
                VALUES (
                  :id,
                  :name,
                  :api_key_hash,
                  :notification_email,
                  :shopify_webhook_secret
                )
                """
            ),
            {
                "id": str(tenant_id),
                "name": f"B057 P5 Tenant {label}",
                "api_key_hash": api_key_hash,
                "notification_email": notification_email,
                "shopify_webhook_secret": shopify_secret if include_shopify_secret else None,
            },
        )

    return _TenantFixture(
        tenant_id=tenant_id,
        tenant_key=tenant_key,
        api_key_hash=api_key_hash,
        shopify_secret=shopify_secret,
    )


def _sign_shopify(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def _compute_window(event_ts: datetime) -> tuple[datetime, datetime]:
    window_start = event_ts.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=1)
    return window_start, window_end


def _with_engine(runtime_db_url: str):
    return create_engine(runtime_db_url)


def _count_events(runtime_db_url: str, tenant_id: Optional[UUID], event_id: UUID) -> int:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        if tenant_id:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.attribution_events WHERE id = :event_id"),
            {"event_id": str(event_id)},
        ).scalar_one()
        return int(count)


def _count_allocations(runtime_db_url: str, tenant_id: Optional[UUID], event_id: UUID) -> int:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        if tenant_id:
            conn.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_id)},
            )
        count = conn.execute(
            text("SELECT COUNT(*) FROM public.attribution_allocations WHERE event_id = :event_id"),
            {"event_id": str(event_id)},
        ).scalar_one()
        return int(count)


def _fetch_recompute_job(
    runtime_db_url: str,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
) -> Optional[dict[str, Any]]:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        row = conn.execute(
            text(
                """
                SELECT id, status, run_count, window_start, window_end, model_version
                FROM public.attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                  AND window_start = :window_start
                  AND window_end = :window_end
                  AND model_version = '1.0.0'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "window_start": window_start,
                "window_end": window_end,
            },
        ).mappings().first()
        return dict(row) if row else None


def _probe_recompute_job_succeeded(
    runtime_db_url: str,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    artifact_dir: Path,
    event_id: UUID,
) -> Optional[dict[str, Any]]:
    row = _fetch_recompute_job(runtime_db_url, tenant_id, window_start, window_end)
    if not row:
        return None
    status = row.get("status")
    if status == "failed":
        _collect_diagnostics(
            runtime_db_url,
            tenant_id,
            event_id,
            artifact_dir,
            "recompute_job_failed",
        )
        raise AssertionError("Attribution recompute job failed")
    if status == "succeeded":
        return row
    return None


def _fetch_matview_row(
    runtime_db_url: str,
    tenant_id: UUID,
    event_id: UUID,
) -> Optional[dict[str, Any]]:
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        row = conn.execute(
            text(
                """
                SELECT tenant_id, event_id, model_version, total_allocated_cents,
                       event_revenue_cents, is_balanced, drift_cents
                FROM public.mv_allocation_summary
                WHERE tenant_id = :tenant_id
                  AND event_id = :event_id
                  AND model_version = '1.0.0'
                """
            ),
            {"tenant_id": str(tenant_id), "event_id": str(event_id)},
        ).mappings().first()
        return dict(row) if row else None


def _poll_until(
    *,
    description: str,
    timeout_s: float,
    interval_s: float,
    probe: Callable[[], Optional[Any]],
    on_timeout: Callable[[], None],
) -> Any:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(interval_s)
    on_timeout()
    raise AssertionError(f"Timeout while waiting for {description}")


def _collect_diagnostics(
    runtime_db_url: str,
    tenant_id: UUID,
    event_id: UUID,
    artifact_dir: Path,
    reason: str,
) -> None:
    snapshot: dict[str, Any] = {
        "reason": reason,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "tenant_id": str(tenant_id),
        "event_id": str(event_id),
    }
    engine = _with_engine(runtime_db_url)
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, false)"),
            {"tenant_id": str(tenant_id)},
        )
        snapshot["attribution_events"] = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT id, event_type, revenue_cents, occurred_at, idempotency_key
                    FROM public.attribution_events
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    LIMIT 5
                    """
                ),
                {"tenant_id": str(tenant_id)},
            ).mappings().all()
        ]
        snapshot["attribution_allocations"] = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT event_id, channel_code, allocated_revenue_cents, model_version
                    FROM public.attribution_allocations
                    WHERE tenant_id = :tenant_id
                    ORDER BY created_at DESC
                    LIMIT 10
                    """
                ),
                {"tenant_id": str(tenant_id)},
            ).mappings().all()
        ]
        snapshot["recompute_jobs"] = [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    SELECT id, status, run_count, window_start, window_end, model_version
                    FROM public.attribution_recompute_jobs
                    WHERE tenant_id = :tenant_id
                    ORDER BY updated_at DESC
                    LIMIT 5
                    """
                ),
                {"tenant_id": str(tenant_id)},
            ).mappings().all()
        ]

    with engine.begin() as conn:
        snapshot["kombu_tables"] = {
            "kombu_queue_exists": bool(
                conn.execute(text("SELECT to_regclass('public.kombu_queue')")).scalar_one()
            ),
            "kombu_message_exists": bool(
                conn.execute(text("SELECT to_regclass('public.kombu_message')")).scalar_one()
            ),
        }
        if snapshot["kombu_tables"]["kombu_queue_exists"] and snapshot["kombu_tables"]["kombu_message_exists"]:
            snapshot["kombu_queue_depths"] = [
                dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT q.name, COUNT(m.id) AS depth
                        FROM public.kombu_queue q
                        LEFT JOIN public.kombu_message m ON m.queue_id = q.id
                        GROUP BY q.name
                        ORDER BY q.name
                        """
                    )
                ).mappings().all()
            ]
        celery_taskmeta_exists = bool(
            conn.execute(text("SELECT to_regclass('public.celery_taskmeta')")).scalar_one()
        )
        snapshot["celery_taskmeta_exists"] = celery_taskmeta_exists
        if celery_taskmeta_exists:
            snapshot["celery_taskmeta"] = [
                dict(row)
                for row in conn.execute(
                    text(
                        """
                        SELECT task_id, status, date_done
                        FROM public.celery_taskmeta
                        ORDER BY date_done DESC
                        LIMIT 10
                        """
                    )
                ).mappings().all()
            ]

    path = artifact_dir / "timeout_diagnostics.json"
    path.write_text(json.dumps(snapshot, default=str, indent=2), encoding="utf-8")


def _write_db_probe(
    runtime_db_url: str,
    tenant_id: UUID,
    event_id: UUID,
    job_row: dict[str, Any],
    matview_row: dict[str, Any],
    artifact_dir: Path,
) -> None:
    snapshot = {
        "tenant_id": str(tenant_id),
        "event_id": str(event_id),
        "job_row": job_row,
        "matview_row": matview_row,
        "event_count_tenant": _count_events(runtime_db_url, tenant_id, event_id),
        "allocation_count_tenant": _count_allocations(runtime_db_url, tenant_id, event_id),
        "event_count_no_tenant": _count_events(runtime_db_url, None, event_id),
        "allocation_count_no_tenant": _count_allocations(runtime_db_url, None, event_id),
    }
    path = artifact_dir / "db_probe.json"
    path.write_text(json.dumps(snapshot, default=str, indent=2), encoding="utf-8")


def _scrape_metrics(url: str) -> str:
    res = httpx.get(url, timeout=5.0)
    if res.status_code != 200:
        raise AssertionError(f"Expected 200 from {url}, got {res.status_code}")
    return res.text


def _parse_metric_value(text: str, name: str, labels: Optional[dict[str, str]] = None) -> float:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith(name):
            continue
        if " " not in line:
            continue
        metric_part, value_part = line.split(" ", 1)
        if not metric_part.startswith(name):
            continue
        if labels is None:
            if "{" in metric_part:
                continue
        else:
            if "{" not in metric_part:
                continue
            label_block = metric_part.split("{", 1)[1].rsplit("}", 1)[0]
            parsed: dict[str, str] = {}
            for key, val in _parse_label_pairs(label_block):
                parsed[key] = val
            if any(parsed.get(k) != v for k, v in labels.items()):
                continue
        try:
            return float(value_part.strip())
        except ValueError:
            continue
    return 0.0


def _parse_label_pairs(label_block: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for part in label_block.split(","):
        if "=" not in part:
            continue
        key, raw_val = part.split("=", 1)
        key = key.strip()
        val = raw_val.strip().strip('"')
        pairs.append((key, val))
    return pairs


def _metrics_lint(text: str) -> dict[str, Any]:
    from app.observability.metrics_policy import ALLOWED_LABEL_KEYS

    application_prefixes = (
        "events_",
        "celery_task_",
        "celery_queue_",
        "matview_refresh_",
        "ingestion_",
        "multiproc_",
    )
    forbidden_keys = {"tenant_id", "correlation_id", "request_id", "session_id", "user_id"}
    violations: list[str] = []
    label_keys: set[str] = set()
    uuid_hits: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "{" not in line:
            continue
        if " " not in line:
            continue
        metric_part = line.split(" ", 1)[0]
        metric_name = metric_part.split("{", 1)[0]
        if not metric_name.startswith(application_prefixes):
            continue
        if "{" not in metric_part or "}" not in metric_part:
            continue
        label_block = metric_part.split("{", 1)[1].rsplit("}", 1)[0]
        for key, val in _parse_label_pairs(label_block):
            label_keys.add(key)
            if key in forbidden_keys:
                violations.append(f"forbidden_label_key:{key}")
            if _looks_like_uuid(val):
                uuid_hits.append(val)

    unknown_keys = sorted(label_keys - set(ALLOWED_LABEL_KEYS) - {"le", "quantile"})
    if unknown_keys:
        violations.append(f"unknown_label_keys:{','.join(unknown_keys)}")
    if uuid_hits:
        violations.append("uuid_like_values_detected")

    return {
        "label_keys": sorted(label_keys),
        "uuid_like_values": uuid_hits[:5],
        "violations": violations,
    }


def _looks_like_uuid(value: str) -> bool:
    if len(value) != 36:
        return False
    parts = value.split("-")
    if len(parts) != 5:
        return False
    try:
        int("".join(parts), 16)
    except ValueError:
        return False
    return True


def _assert_log_contains(path: Path, patterns: list[str]) -> None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    missing = [p for p in patterns if p not in content]
    if missing:
        raise AssertionError(f"Missing log markers in {path.name}: {missing}")


def _assert_log_contains_any(path: Path, patterns: list[str]) -> None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    if any(p in content for p in patterns):
        return
    raise AssertionError(f"Missing any log markers in {path.name}: {patterns}")


def test_b057_p5_full_chain_webhook_to_matview():
    admin_db_url = _require_env("B057_P5_ADMIN_DATABASE_URL")
    runtime_db_url = _runtime_sync_db_url()
    artifact_dir = _artifact_dir()

    tenant_a = _seed_tenant(admin_db_url, "A", include_shopify_secret=True)
    tenant_b = _seed_tenant(admin_db_url, "B", include_shopify_secret=False)

    runtime_async = _runtime_async_db_url(runtime_db_url)
    env = os.environ.copy()
    env["DATABASE_URL"] = runtime_async
    env["CELERY_BROKER_URL"] = f"sqla+{runtime_db_url}"
    env["CELERY_RESULT_BACKEND"] = f"db+{runtime_db_url}"
    env.setdefault("ENVIRONMENT", "test")
    env["B057_P5_ARTIFACT_DIR"] = str(artifact_dir)
    multiproc_dir = Path(tempfile.mkdtemp(prefix="b057_p5_prom_"))
    env["PROMETHEUS_MULTIPROC_DIR"] = str(multiproc_dir)

    worker_log = artifact_dir / "worker.log"
    api_log = artifact_dir / "api.log"
    exporter_log = artifact_dir / "exporter.log"

    worker_proc = None
    api_proc = None
    exporter_proc = None
    base_url = None
    exporter_url = None

    try:
        worker_proc, _ = _start_worker(env, worker_log)
        exporter_proc, exporter_url = _start_exporter(env, exporter_log)
        api_proc, base_url = _start_api(env, api_log)

        metrics_api_before = _scrape_metrics(f"{base_url}/metrics")
        metrics_worker_before = _scrape_metrics(f"{exporter_url}/metrics")
        (artifact_dir / "metrics_api_before.txt").write_text(metrics_api_before, encoding="utf-8")
        (artifact_dir / "metrics_worker_before.txt").write_text(metrics_worker_before, encoding="utf-8")

        event_ts = datetime(2026, 1, 25, 12, 34, 56, tzinfo=timezone.utc)
        window_start, window_end = _compute_window(event_ts)
        payload = {
            "id": 424242,
            "total_price": "10.50",
            "currency": "USD",
            "created_at": event_ts.isoformat().replace("+00:00", "Z"),
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = _sign_shopify(body, tenant_a.shopify_secret)

        res = httpx.post(
            f"{base_url}/api/webhooks/shopify/order_create",
            headers={
                "Content-Type": "application/json",
                "X-Skeldir-Tenant-Key": tenant_a.tenant_key,
                "X-Shopify-Hmac-Sha256": signature,
            },
            content=body,
            timeout=10.0,
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data.get("status") == "success"
        event_id = UUID(data["event_id"])

        assert _count_events(runtime_db_url, tenant_a.tenant_id, event_id) == 1

        job_row = _poll_until(
            description="attribution recompute job success",
            timeout_s=60.0,
            interval_s=1.0,
            probe=lambda: _probe_recompute_job_succeeded(
                runtime_db_url,
                tenant_a.tenant_id,
                window_start,
                window_end,
                artifact_dir,
                event_id,
            ),
            on_timeout=lambda: _collect_diagnostics(
                runtime_db_url,
                tenant_a.tenant_id,
                event_id,
                artifact_dir,
                "recompute_job_timeout",
            ),
        )
        assert job_row["status"] == "succeeded"

        allocation_count = _poll_until(
            description="allocation rows for event",
            timeout_s=60.0,
            interval_s=1.0,
            probe=lambda: _count_allocations(runtime_db_url, tenant_a.tenant_id, event_id),
            on_timeout=lambda: _collect_diagnostics(
                runtime_db_url,
                tenant_a.tenant_id,
                event_id,
                artifact_dir,
                "allocation_timeout",
            ),
        )
        assert allocation_count > 0

        matview_row = _poll_until(
            description="mv_allocation_summary refresh",
            timeout_s=60.0,
            interval_s=1.0,
            probe=lambda: _fetch_matview_row(runtime_db_url, tenant_a.tenant_id, event_id),
            on_timeout=lambda: _collect_diagnostics(
                runtime_db_url,
                tenant_a.tenant_id,
                event_id,
                artifact_dir,
                "matview_timeout",
            ),
        )
        assert int(matview_row["total_allocated_cents"]) == 1050
        assert int(matview_row["event_revenue_cents"]) == 1050
        assert bool(matview_row["is_balanced"]) is True

        assert _count_events(runtime_db_url, tenant_b.tenant_id, event_id) == 0
        assert _count_allocations(runtime_db_url, tenant_b.tenant_id, event_id) == 0
        assert _count_events(runtime_db_url, None, event_id) == 0
        assert _count_allocations(runtime_db_url, None, event_id) == 0

        metrics_api_after = _scrape_metrics(f"{base_url}/metrics")
        metrics_worker_after = _scrape_metrics(f"{exporter_url}/metrics")
        (artifact_dir / "metrics_api_after.txt").write_text(metrics_api_after, encoding="utf-8")
        (artifact_dir / "metrics_worker_after.txt").write_text(metrics_worker_after, encoding="utf-8")

        events_ingested_before = _parse_metric_value(metrics_api_before, "events_ingested_total")
        events_ingested_after = _parse_metric_value(metrics_api_after, "events_ingested_total")
        task_success_recompute_before = _parse_metric_value(
            metrics_worker_before,
            "celery_task_success_total",
            {"task_name": "app.tasks.attribution.recompute_window"},
        )
        task_success_recompute_after = _parse_metric_value(
            metrics_worker_after,
            "celery_task_success_total",
            {"task_name": "app.tasks.attribution.recompute_window"},
        )
        task_success_matview_before = _parse_metric_value(
            metrics_worker_before,
            "celery_task_success_total",
            {"task_name": "app.tasks.matviews.refresh_all_for_tenant"},
        )
        task_success_matview_after = _parse_metric_value(
            metrics_worker_after,
            "celery_task_success_total",
            {"task_name": "app.tasks.matviews.refresh_all_for_tenant"},
        )
        matview_refresh_before = _parse_metric_value(
            metrics_worker_before,
            "matview_refresh_total",
            {"view_name": "mv_allocation_summary", "outcome": "success"},
        )
        matview_refresh_after = _parse_metric_value(
            metrics_worker_after,
            "matview_refresh_total",
            {"view_name": "mv_allocation_summary", "outcome": "success"},
        )

        deltas = {
            "events_ingested_total": events_ingested_after - events_ingested_before,
            "celery_task_success_total_recompute_window": task_success_recompute_after
            - task_success_recompute_before,
            "celery_task_success_total_matview_refresh_all_for_tenant": task_success_matview_after
            - task_success_matview_before,
            "matview_refresh_total_mv_allocation_summary_success": matview_refresh_after
            - matview_refresh_before,
            "api_metrics_url": f"{base_url}/metrics",
            "worker_metrics_url": f"{exporter_url}/metrics",
        }
        (artifact_dir / "metrics_delta.json").write_text(
            json.dumps(deltas, default=str, indent=2), encoding="utf-8"
        )

        assert deltas["events_ingested_total"] >= 1
        assert deltas["celery_task_success_total_recompute_window"] >= 1
        assert deltas["celery_task_success_total_matview_refresh_all_for_tenant"] >= 1
        assert deltas["matview_refresh_total_mv_allocation_summary_success"] >= 1

        assert "celery_task_success_total" not in metrics_api_after
        assert "celery_task_success_total" in metrics_worker_after

        lint_api = _metrics_lint(metrics_api_after)
        lint_worker = _metrics_lint(metrics_worker_after)
        lint_report = {
            "api": lint_api,
            "worker": lint_worker,
        }
        (artifact_dir / "metrics_lint.json").write_text(
            json.dumps(lint_report, default=str, indent=2), encoding="utf-8"
        )
        assert not lint_api["violations"], f"API metrics lint failed: {lint_api['violations']}"
        assert not lint_worker["violations"], f"Worker metrics lint failed: {lint_worker['violations']}"

        _assert_log_contains(
            api_log,
            [
                "ingestion_followup_tasks_enqueued",
                str(tenant_a.tenant_id),
            ],
        )
        _assert_log_contains_any(
            worker_log,
            [
                '"task_name": "app.tasks.attribution.recompute_window"',
                '"task_name":"app.tasks.attribution.recompute_window"',
            ],
        )
        _assert_log_contains_any(
            worker_log,
            [
                '"task_name": "app.tasks.matviews.refresh_all_for_tenant"',
                '"task_name":"app.tasks.matviews.refresh_all_for_tenant"',
            ],
        )
        _assert_log_contains_any(
            worker_log,
            [
                '"status": "success"',
                '"status":"success"',
            ],
        )
        _assert_log_contains(
            worker_log,
            [
                str(tenant_a.tenant_id),
            ],
        )
        _assert_log_contains_any(
            worker_log,
            [
                "matview_refresh_all_task_start",
                "matview_refresh_view_completed",
                "matview_refresh_task_completed",
            ],
        )

        _write_db_probe(runtime_db_url, tenant_a.tenant_id, event_id, job_row, matview_row, artifact_dir)
    finally:
        if api_proc is not None:
            _stop_process(api_proc)
        if exporter_proc is not None:
            _stop_process(exporter_proc)
        if worker_proc is not None:
            _stop_process(worker_proc)

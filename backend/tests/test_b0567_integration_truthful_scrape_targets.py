"""
B0.5.6.7: Integration Tests — Truthful Scrape Targets + No Split-Brain Assumptions

Runtime topology truth encoded in CI:
- Worker emits task metrics via PROMETHEUS_MULTIPROC_DIR shards (no HTTP listener).
- Exporter is the only HTTP scrape surface for worker task metrics (/metrics).
- API /metrics exposes API + broker-truth queue gauges only (no worker task metrics).
"""

from __future__ import annotations

import math
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from app.celery_app import celery_app
from app.observability.metrics_policy import normalize_queue
from tests.metrics_topology_harness import ensure_worker_running, start_metrics_topology, stop_metrics_topology, terminate_process


PING_TASK_NAME = "app.tasks.housekeeping.ping"


def _scrape_text(url: str) -> str:
    with urlopen(url, timeout=5) as resp:  # noqa: S310 - local test server only
        assert resp.status == 200
        return resp.read().decode("utf-8", errors="replace")


def _http_get_text(url: str) -> tuple[int, str]:
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310 - local test server only
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if getattr(exc, "fp", None) is not None else ""
        return int(exc.code), body


def _wait_for_http_status(url: str, expected_status: int, *, timeout_s: float) -> str:
    deadline = time.time() + timeout_s
    last_status: int | None = None
    last_body: str = ""
    while time.time() < deadline:
        status_code, body = _http_get_text(url)
        last_status = status_code
        last_body = body
        if status_code == expected_status:
            return body
        time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for HTTP {expected_status} from {url}; last={last_status} body={last_body[:500]!r}")


_SAMPLE_RE = re.compile(
    r'^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[0-9.eE+-]+|NaN|[+-]Inf)\s*$'
)
_LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')


def _get_sample_value(text_body: str, *, metric_name: str, labels: dict[str, str]) -> float:
    for line in text_body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE_RE.match(line)
        if not m:
            continue
        if m.group("name") != metric_name:
            continue
        line_labels = dict(_LABEL_RE.findall(m.group("labels") or ""))
        if line_labels != labels:
            continue
        raw = m.group("value")
        try:
            return float(raw)
        except Exception:
            return math.nan
    return 0.0


@dataclass(frozen=True)
class BrokerTruthNormalized:
    visible_counts: dict[str, int]
    max_age_seconds: dict[str, float]


def _sync_dsn_from_celery_broker_url() -> str:
    broker_url = os.environ.get("CELERY_BROKER_URL") or ""
    if not broker_url.startswith("sqla+"):
        raise RuntimeError(f"CELERY_BROKER_URL must start with sqla+: got {broker_url!r}")
    return broker_url.removeprefix("sqla+")


def _fetch_broker_truth_normalized() -> BrokerTruthNormalized:
    dsn = _sync_dsn_from_celery_broker_url()
    engine = create_engine(dsn, pool_pre_ping=True)

    sql = text(
        """
        SELECT
            q.name AS queue_name,
            COALESCE(SUM(CASE WHEN m.visible THEN 1 ELSE 0 END), 0) AS visible_count,
            COALESCE(
                EXTRACT(EPOCH FROM (NOW() - (MIN(m.timestamp) FILTER (WHERE m.visible)))),
                0
            ) AS max_age_seconds
        FROM kombu_queue q
        LEFT JOIN kombu_message m ON m.queue_id = q.id
        WHERE q.name NOT LIKE :pidbox_like
        GROUP BY q.name
        """
    )

    visible: dict[str, int] = {}
    max_age: dict[str, float] = {}

    with engine.begin() as conn:
        res = conn.execute(sql, {"pidbox_like": "%.reply.celery.pidbox"})
        for row in res.fetchall():
            raw_queue = str(row.queue_name) if row.queue_name is not None else "unknown"
            bounded_queue = normalize_queue(raw_queue)
            visible[bounded_queue] = int(visible.get(bounded_queue, 0)) + int(row.visible_count or 0)
            max_age[bounded_queue] = max(float(max_age.get(bounded_queue, 0.0)), float(row.max_age_seconds or 0.0))

    return BrokerTruthNormalized(visible_counts=visible, max_age_seconds=max_age)


@pytest.fixture(scope="module")
def metrics_topology(tmp_path_factory):
    tmp_path: Path = tmp_path_factory.mktemp("b0567_metrics_topology")
    topology = start_metrics_topology(
        tmp_path=tmp_path,
        worker_queue="b0567_runtime",
        api_env_overrides={
            # Disable /health/worker caching so worker-down assertions don't get
            # false positives from the probe cache.
            "WORKER_PROBE_CACHE_TTL_SECONDS": "0",
            # Keep worker-down probes bounded; tests use retries to handle races.
            "WORKER_PROBE_TIMEOUT_SECONDS": "2",
        },
    )
    try:
        yield topology
    finally:
        stop_metrics_topology(topology)


def test_t71_task_metrics_delta_on_exporter(metrics_topology):
    before = _scrape_text(f"{metrics_topology.exporter_url}/metrics")

    labels = {"task_name": PING_TASK_NAME}
    before_success = _get_sample_value(before, metric_name="celery_task_success_total", labels=labels)
    before_failure = _get_sample_value(before, metric_name="celery_task_failure_total", labels=labels)
    before_duration_count = _get_sample_value(before, metric_name="celery_task_duration_seconds_count", labels=labels)

    ok = celery_app.send_task(
        PING_TASK_NAME,
        queue=metrics_topology.worker_queue,
        routing_key=f"{metrics_topology.worker_queue}.task",
        kwargs={"fail": False},
    )
    ok.get(timeout=60)

    fail = celery_app.send_task(
        PING_TASK_NAME,
        queue=metrics_topology.worker_queue,
        routing_key=f"{metrics_topology.worker_queue}.task",
        kwargs={"fail": True},
    )
    with pytest.raises(Exception):
        fail.get(timeout=60, propagate=True)

    after = _scrape_text(f"{metrics_topology.exporter_url}/metrics")
    after_success = _get_sample_value(after, metric_name="celery_task_success_total", labels=labels)
    after_failure = _get_sample_value(after, metric_name="celery_task_failure_total", labels=labels)
    after_duration_count = _get_sample_value(after, metric_name="celery_task_duration_seconds_count", labels=labels)

    assert after_success - before_success >= 1.0
    assert after_failure - before_failure >= 1.0
    assert after_duration_count - before_duration_count >= 2.0


def test_t72_api_queue_gauges_match_broker_truth(metrics_topology):
    queue_name = f"b0567_queue_stats_{uuid4().hex[:8]}"
    task_count = 3

    for _ in range(task_count):
        celery_app.send_task(
            PING_TASK_NAME,
            queue=queue_name,
            routing_key=f"{queue_name}.task",
            kwargs={"fail": False},
        )

    dsn = _sync_dsn_from_celery_broker_url()
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:
        res = conn.execute(text("SELECT id FROM kombu_queue WHERE name = :name"), {"name": queue_name}).first()
        assert res is not None, "queue row missing in kombu_queue"
        queue_id = int(res.id)
        conn.execute(
            text(
                """
                UPDATE kombu_message
                SET "timestamp" = (NOW() - make_interval(secs => 30))
                WHERE queue_id = :queue_id AND visible = true
                """
            ),
            {"queue_id": queue_id},
        )

    time.sleep(0.2)
    truth = _fetch_broker_truth_normalized()

    api_text = _scrape_text(f"{metrics_topology.api_url}/metrics")

    expected_visible_unknown = float(truth.visible_counts.get("unknown", 0))
    expected_max_age_unknown = float(truth.max_age_seconds.get("unknown", 0.0))

    scraped_visible_unknown = _get_sample_value(
        api_text,
        metric_name="celery_queue_messages",
        labels={"queue": "unknown", "state": "visible"},
    )
    scraped_max_age_unknown = _get_sample_value(
        api_text,
        metric_name="celery_queue_max_age_seconds",
        labels={"queue": "unknown"},
    )

    assert scraped_visible_unknown == expected_visible_unknown
    assert abs(scraped_max_age_unknown - expected_max_age_unknown) <= 5.0

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM kombu_message WHERE queue_id = :queue_id"), {"queue_id": queue_id})
        conn.execute(text("DELETE FROM kombu_queue WHERE id = :queue_id"), {"queue_id": queue_id})


def test_t73_api_metrics_do_not_include_worker_task_metrics(metrics_topology):
    api_text = _scrape_text(f"{metrics_topology.api_url}/metrics")
    assert "celery_task_success_total" not in api_text
    assert "celery_task_failure_total" not in api_text
    assert "celery_task_duration_seconds" not in api_text


def test_t74_forbidden_labels_absent_on_both_scrape_surfaces(metrics_topology):
    api_text = _scrape_text(f"{metrics_topology.api_url}/metrics")
    exporter_text = _scrape_text(f"{metrics_topology.exporter_url}/metrics")

    for text_body in (api_text, exporter_text):
        assert "tenant_id" not in text_body


def test_t75_health_semantics_live_ready_worker_capability(metrics_topology):
    api_url = metrics_topology.api_url

    # Baseline (worker running): live OK, ready OK, worker capability OK.
    assert _wait_for_http_status(f"{api_url}/health/live", 200, timeout_s=10.0)
    assert _wait_for_http_status(f"{api_url}/health/ready", 200, timeout_s=30.0)

    worker_ok_body = _wait_for_http_status(f"{api_url}/health/worker", 200, timeout_s=30.0)
    worker_ok = json.loads(worker_ok_body) if worker_ok_body else {}
    assert worker_ok.get("status") == "ok"
    assert worker_ok.get("worker") == "ok"

    try:
        # Failure mode (worker terminated): live remains OK, ready remains OK,
        # but worker capability must fail truthfully.
        terminate_process(metrics_topology.worker.proc, timeout_s=30.0)
        assert metrics_topology.worker.proc.poll() is not None

        assert _wait_for_http_status(f"{api_url}/health/live", 200, timeout_s=10.0)
        assert _wait_for_http_status(f"{api_url}/health/ready", 200, timeout_s=30.0)

        worker_bad_body = _wait_for_http_status(f"{api_url}/health/worker", 503, timeout_s=30.0)
        worker_bad = json.loads(worker_bad_body) if worker_bad_body else {}
        assert worker_bad.get("status") == "unhealthy"
        assert worker_bad.get("worker") == "error"
    finally:
        # Avoid cascading failures in subsequent Phase 7 tests by bringing the
        # worker back if this test stopped it.
        ensure_worker_running(metrics_topology)

"""
B0.5.6.3: Metrics Hardening CI Gate Tests

These tests enforce:
- EG3.1: No tenant_id in exposition
- EG3.2: Closed-set label enforcement (queue, task_name, outcome, view_name)
- EG3.3: Series budget within threshold
- EG3.4: No UUID-like values in exposition

These are drift-prevention tests. They must fail even if the app otherwise works.

Note: This test module must NOT hardcode or default `DATABASE_URL`. CI and local
dev DSNs are governed by `backend/tests/conftest.py` (Gate C).
"""
import re

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.observability.metrics_policy import (
    ALLOWED_LABEL_KEYS,
    ALLOWED_OUTCOMES,
    ALLOWED_QUEUES,
    ALLOWED_QUEUE_STATES,
    ALLOWED_TASK_NAMES,
    ALLOWED_VIEW_NAMES,
    SERIES_BUDGET_THRESHOLD,
    compute_series_budget,
)

def _iter_application_metric_definitions():
    """
    Yield prometheus_client metric wrapper objects defined in app.observability.metrics.

    This is a definition-time enforcement boundary: it catches drift even if a metric
    family has no samples yet (i.e., labels were defined but never observed).
    """
    from prometheus_client.metrics import MetricWrapperBase
    from app.observability import metrics as metrics_module

    for value in vars(metrics_module).values():
        if isinstance(value, MetricWrapperBase):
            yield value


# UUID regex pattern (standard 8-4-4-4-12 format)
UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}',
    re.IGNORECASE
)

# Prometheus metric line pattern: metric_name{labels} value
METRIC_LINE_PATTERN = re.compile(
    r'^(?P<metric_name>[a-zA-Z_:][a-zA-Z0-9_:]*)'
    r'(?:\{(?P<labels>[^}]*)\})?'
    r'\s+(?P<value>[0-9.eE+-]+|NaN|[+-]Inf)$'
)

# Label key=value pattern
LABEL_PATTERN = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')

# Prometheus internal label keys (exempt from policy enforcement)
PROMETHEUS_INTERNAL_LABELS = frozenset({"le", "quantile"})

# Application metric prefixes (vs. Python runtime metrics)
APPLICATION_METRIC_PREFIXES = (
    "events_",
    "celery_task_",
    "celery_queue_",
    "matview_refresh_",
    "ingestion_",
)


def _parse_metrics_exposition(text: str) -> list[dict]:
    """
    Parse Prometheus exposition format into structured data.
    
    Returns list of dicts with keys: metric_name, labels (dict), value
    """
    results = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = METRIC_LINE_PATTERN.match(line)
        if match:
            metric_name = match.group("metric_name")
            labels_str = match.group("labels") or ""
            labels = dict(LABEL_PATTERN.findall(labels_str))
            results.append({
                "metric_name": metric_name,
                "labels": labels,
                "value": match.group("value"),
            })
    return results


def _is_application_metric(metric_name: str) -> bool:
    """Check if metric is an application metric (vs. Python runtime)."""
    return any(metric_name.startswith(prefix) for prefix in APPLICATION_METRIC_PREFIXES)


@pytest_asyncio.fixture
async def metrics_text() -> str:
    """Fetch /metrics exposition from the API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    assert resp.status_code == 200
    return resp.text


# =============================================================================
# EG3.1: No tenant_id in exposition
# =============================================================================

def test_eg31_no_tenant_id_in_metric_definitions():
    """
    EG3.1 (definition-time): No metric definition includes tenant_id as a label key.

    This is stronger than scraping /metrics alone because Prometheus exposition
    may omit labelnames until a labelled child is observed.
    """
    for metric in _iter_application_metric_definitions():
        labelnames = set(getattr(metric, "_labelnames", ()) or ())
        assert "tenant_id" not in labelnames, (
            f"EG3.1 FAILED: tenant_id label defined on metric {metric._name}: {sorted(labelnames)}"
        )


@pytest.mark.asyncio
async def test_eg31_no_tenant_id_in_metrics(metrics_text: str):
    """
    EG3.1: Scraping /metrics yields zero tenant_id labels.
    
    Exact string check: 'tenant_id=' must not appear anywhere.
    """
    assert "tenant_id=" not in metrics_text, (
        "EG3.1 FAILED: tenant_id label found in /metrics exposition"
    )


# =============================================================================
# EG3.4: No UUID-like values in exposition
# =============================================================================

@pytest.mark.asyncio
async def test_eg34_no_uuid_values_in_metrics(metrics_text: str):
    """
    EG3.4: Scraping /metrics yields no UUID-like label values.
    
    Regex scan for UUID pattern across the entire exposition.
    """
    # Parse all label values and check for UUIDs
    parsed = _parse_metrics_exposition(metrics_text)
    uuid_violations = []
    
    for metric in parsed:
        for label_key, label_value in metric["labels"].items():
            if UUID_PATTERN.search(label_value):
                uuid_violations.append({
                    "metric": metric["metric_name"],
                    "label": label_key,
                    "value": label_value,
                })
    
    assert not uuid_violations, (
        f"EG3.4 FAILED: UUID-like values found in /metrics:\n"
        f"{uuid_violations}"
    )


# =============================================================================
# EG3.2: Closed-set label enforcement
# =============================================================================

def test_eg32_metric_label_keys_are_allowlisted():
    """
    EG3.2 (definition-time): All metric label keys are within ALLOWED_LABEL_KEYS.

    This prevents drift such as reintroducing vendor/event_type/error_type/strategy labels.
    """
    for metric in _iter_application_metric_definitions():
        labelnames = set(getattr(metric, "_labelnames", ()) or ())
        assert labelnames <= set(ALLOWED_LABEL_KEYS), (
            f"EG3.2 FAILED: disallowed label keys on {metric._name}: "
            f"{sorted(labelnames - set(ALLOWED_LABEL_KEYS))} (all={sorted(labelnames)})"
        )


@pytest.mark.asyncio
async def test_eg32_closed_set_label_keys(metrics_text: str):
    """
    EG3.2: Application metrics only use allowed label keys.
    
    Validates that every label key (except Prometheus internals) is in ALLOWED_LABEL_KEYS.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []
    
    for metric in parsed:
        if not _is_application_metric(metric["metric_name"]):
            continue
        
        for label_key in metric["labels"].keys():
            if label_key in PROMETHEUS_INTERNAL_LABELS:
                continue
            if label_key not in ALLOWED_LABEL_KEYS:
                violations.append({
                    "metric": metric["metric_name"],
                    "label_key": label_key,
                })
    
    assert not violations, (
        f"EG3.2 FAILED: Disallowed label keys found:\n"
        f"Allowed: {ALLOWED_LABEL_KEYS}\n"
        f"Violations: {violations}"
    )


@pytest.mark.asyncio
async def test_eg32_task_name_values_bounded(metrics_text: str):
    """
    EG3.2: task_name label values are bounded to ALLOWED_TASK_NAMES or 'unknown'.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []
    allowed_with_unknown = ALLOWED_TASK_NAMES | {"unknown"}
    
    for metric in parsed:
        task_name = metric["labels"].get("task_name")
        if task_name is not None and task_name not in allowed_with_unknown:
            violations.append({
                "metric": metric["metric_name"],
                "task_name": task_name,
            })
    
    assert not violations, (
        f"EG3.2 FAILED: Unbounded task_name values found:\n"
        f"Violations: {violations}"
    )


@pytest.mark.asyncio
async def test_eg32_queue_values_bounded(metrics_text: str):
    """
    EG3.2: queue label values are bounded to ALLOWED_QUEUES or 'unknown'.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []
    allowed_with_unknown = ALLOWED_QUEUES | {"unknown"}
    
    for metric in parsed:
        queue = metric["labels"].get("queue")
        if queue is not None and queue not in allowed_with_unknown:
            violations.append({
                "metric": metric["metric_name"],
                "queue": queue,
            })
    
    assert not violations, (
        f"EG3.2 FAILED: Unbounded queue values found:\n"
        f"Violations: {violations}"
    )


@pytest.mark.asyncio
async def test_eg32_state_values_bounded(metrics_text: str):
    """
    EG3.2: state label values are bounded to ALLOWED_QUEUE_STATES.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []

    for metric in parsed:
        state = metric["labels"].get("state")
        if state is not None and state not in ALLOWED_QUEUE_STATES:
            violations.append({
                "metric": metric["metric_name"],
                "state": state,
            })

    assert not violations, (
        f"EG3.2 FAILED: Unbounded state values found:\n"
        f"Allowed: {ALLOWED_QUEUE_STATES}\n"
        f"Violations: {violations}"
    )


@pytest.mark.asyncio
async def test_eg32_outcome_values_bounded(metrics_text: str):
    """
    EG3.2: outcome label values are bounded to ALLOWED_OUTCOMES.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []
    
    for metric in parsed:
        outcome = metric["labels"].get("outcome")
        if outcome is not None and outcome not in ALLOWED_OUTCOMES:
            violations.append({
                "metric": metric["metric_name"],
                "outcome": outcome,
            })
    
    assert not violations, (
        f"EG3.2 FAILED: Unbounded outcome values found:\n"
        f"Allowed: {ALLOWED_OUTCOMES}\n"
        f"Violations: {violations}"
    )


@pytest.mark.asyncio
async def test_eg32_view_name_values_bounded(metrics_text: str):
    """
    EG3.2: view_name label values are bounded to ALLOWED_VIEW_NAMES or 'unknown'.
    """
    parsed = _parse_metrics_exposition(metrics_text)
    violations = []
    allowed_with_unknown = ALLOWED_VIEW_NAMES | {"unknown"}
    
    for metric in parsed:
        view_name = metric["labels"].get("view_name")
        if view_name is not None and view_name not in allowed_with_unknown:
            violations.append({
                "metric": metric["metric_name"],
                "view_name": view_name,
            })
    
    assert not violations, (
        f"EG3.2 FAILED: Unbounded view_name values found:\n"
        f"Violations: {violations}"
    )


# =============================================================================
# EG3.3: Series budget
# =============================================================================

def test_eg33_series_budget_computed():
    """
    EG3.3: Series budget is computed from closed-set dimensions.
    
    Verifies the computation returns expected structure.
    """
    budget = compute_series_budget()
    
    assert "dimension_sizes" in budget
    assert "metric_families" in budget
    assert "total_upper_bound" in budget
    assert isinstance(budget["total_upper_bound"], int)


def test_eg33_series_budget_within_threshold():
    """
    EG3.3: Computed series budget is within the defined threshold.
    
    This test fails if any label dimension becomes unbounded or
    the computed bound exceeds SERIES_BUDGET_THRESHOLD.
    """
    budget = compute_series_budget()
    total = budget["total_upper_bound"]
    
    assert total <= SERIES_BUDGET_THRESHOLD, (
        f"EG3.3 FAILED: Series budget {total} exceeds threshold {SERIES_BUDGET_THRESHOLD}\n"
        f"Budget breakdown: {budget}"
    )


def test_eg33_all_dimensions_are_closed_sets():
    """
    EG3.3: All label dimensions are defined as closed frozensets.
    
    This test fails if any dimension constant is not a frozenset.
    """
    dimensions = {
        "ALLOWED_QUEUES": ALLOWED_QUEUES,
        "ALLOWED_QUEUE_STATES": ALLOWED_QUEUE_STATES,
        "ALLOWED_TASK_NAMES": ALLOWED_TASK_NAMES,
        "ALLOWED_OUTCOMES": ALLOWED_OUTCOMES,
        "ALLOWED_VIEW_NAMES": ALLOWED_VIEW_NAMES,
        "ALLOWED_LABEL_KEYS": ALLOWED_LABEL_KEYS,
    }
    
    for name, value in dimensions.items():
        assert isinstance(value, frozenset), (
            f"EG3.3 FAILED: {name} is not a frozenset (unbounded dimension risk)"
        )
        assert len(value) > 0, (
            f"EG3.3 FAILED: {name} is empty (no valid values)"
        )


# =============================================================================
# Metrics endpoint availability
# =============================================================================

@pytest.mark.asyncio
async def test_metrics_endpoint_returns_200():
    """Verify /metrics endpoint is available and returns 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
    
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_metrics_contains_expected_families(metrics_text: str):
    """Verify expected metric families are present in exposition."""
    expected_families = [
        "events_ingested_total",
        "events_duplicate_total",
        "events_dlq_total",
        "ingestion_duration_seconds",
        "celery_task_started_total",
        "celery_task_success_total",
        "celery_task_failure_total",
        "celery_task_duration_seconds",
        "celery_queue_messages",
        "celery_queue_max_age_seconds",
        "celery_queue_stats_last_refresh_timestamp_seconds",
        "celery_queue_stats_refresh_errors_total",
        "matview_refresh_total",
        "matview_refresh_duration_seconds",
        "matview_refresh_failures_total",
    ]
    
    for family in expected_families:
        assert family in metrics_text, f"Missing metric family: {family}"


# =============================================================================
# Multiprocess Mode Verification (B0.5.6.3)
# =============================================================================

def test_multiprocess_mode_detection():
    """
    Verify _get_metrics_data() correctly detects multiprocess mode.
    
    When PROMETHEUS_MULTIPROC_DIR is not set, should use standard generate_latest().
    """
    import os
    from app.api.health import _get_metrics_data
    
    # Ensure we're in single-process mode for this test
    original = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if original:
        del os.environ["PROMETHEUS_MULTIPROC_DIR"]
    
    try:
        data = _get_metrics_data()
        assert isinstance(data, bytes)
        assert b"events_ingested_total" in data or b"python_gc" in data
    finally:
        if original:
            os.environ["PROMETHEUS_MULTIPROC_DIR"] = original


def test_multiprocess_mode_env_documented():
    """
    Verify multiprocess mode is documented in the metrics module.
    
    This is a documentation-as-code test to ensure the setup instructions
    are present in the module docstring.
    """
    from app.observability import metrics
    
    docstring = metrics.__doc__ or ""
    assert "PROMETHEUS_MULTIPROC_DIR" in docstring, (
        "Multiprocess mode setup instructions missing from metrics module docstring"
    )
    assert "MultiProcessCollector" in docstring or "multiprocess" in docstring.lower(), (
        "Multiprocess aggregation not documented in metrics module"
    )

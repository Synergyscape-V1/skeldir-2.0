"""
Celery Beat schedule definitions.

The schedule is isolated here to avoid circular imports between the Celery app
and task modules. An optional env var allows CI to shrink the refresh interval
so beat dispatch evidence appears within short CI timeboxes.
"""

import os
from typing import Dict, Any

from celery.schedules import crontab

from app.core.queues import QUEUE_BAYESIAN


def _refresh_interval_seconds() -> float:
    """
    Return the refresh interval for matview refresh.

    CI can override via ZG_BEAT_TEST_INTERVAL_SECONDS to force fast dispatch
    for evidence capture. Defaults to 300s for production parity.
    """
    override = os.getenv("ZG_BEAT_TEST_INTERVAL_SECONDS")
    if override:
        try:
            value = int(override)
            if value > 0:
                return float(value)
        except ValueError:
            pass
    return 300.0


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _bayesian_recovery_interval_seconds() -> float:
    return float(_positive_int_env("B24_P9_RECOVERY_RECONCILE_INTERVAL_SECONDS", 60))


def _bayesian_planner_interval_seconds() -> float:
    return float(_positive_int_env("B24_FIT_PLANNER_INTERVAL_SECONDS", 60))


def build_beat_schedule() -> Dict[str, Dict[str, Any]]:
    interval = _refresh_interval_seconds()
    recovery_interval = _bayesian_recovery_interval_seconds()
    planner_interval = _bayesian_planner_interval_seconds()
    schedule: Dict[str, Dict[str, Any]] = {
        "refresh-matviews-every-5-min": {
            "task": "app.tasks.matviews.pulse_matviews_global",
            "schedule": interval,
            "options": {"expires": max(int(interval), 1) * 2},
            "kwargs": {"schedule_class": "minute"},
        },
        "provider-oauth-refresh-orchestration": {
            "task": "app.tasks.maintenance.schedule_provider_oauth_refresh_all_tenants",
            "schedule": crontab(minute="*/10"),
            "options": {"expires": 600},
        },
        "pii-audit-scanner": {
            "task": "app.tasks.maintenance.scan_for_pii_contamination_all_tenants",
            "schedule": crontab(hour=4, minute=0),
            "options": {"expires": 3600},
        },
        "enforce-data-retention": {
            "task": "app.tasks.maintenance.enforce_data_retention_all_tenants",
            "schedule": crontab(hour=3, minute=0),
            "options": {"expires": 3600},
        },
        "b23-p3-pending-to-unmatched-transition": {
            "task": "app.tasks.revenue_verification.transition_stale_pending_to_unmatched_all_tenants",
            "schedule": crontab(minute="*/5"),
            "options": {"expires": 600},
        },
        "b23-p3-provisional-to-confirmed-transition": {
            "task": "app.tasks.revenue_verification.transition_stale_provisional_to_confirmed_all_tenants",
            "schedule": crontab(minute="*/5"),
            "options": {"expires": 600},
        },
    }
    if os.getenv("SKELDIR_B24_DISABLE_FIT_PLANNER_JOB") != "1":
        schedule["b24-fit-planner"] = {
            "task": "app.tasks.bayesian.plan_due_fit_intents",
            "schedule": planner_interval,
            "options": {
                "expires": max(int(planner_interval), 1) * 2,
                "queue": QUEUE_BAYESIAN,
                "routing_key": f"{QUEUE_BAYESIAN}.task",
            },
            "kwargs": {
                "tenant_batch_size": _positive_int_env(
                    "B24_FIT_PLANNER_TENANT_BATCH_SIZE", 25
                ),
                "candidate_limit": _positive_int_env(
                    "B24_FIT_PLANNER_CANDIDATE_LIMIT", 25
                ),
            },
        }
    if os.getenv("SKELDIR_B24_P9_DISABLE_RECOVERY_RECONCILER_JOB") != "1":
        schedule["b24-p9-bayesian-recovery-reconciler"] = {
            "task": "app.tasks.bayesian.reconcile_fit_recovery_wakeups",
            "schedule": recovery_interval,
            "options": {
                "expires": max(int(recovery_interval), 1) * 2,
                "queue": QUEUE_BAYESIAN,
                "routing_key": f"{QUEUE_BAYESIAN}.task",
            },
            "kwargs": {
                "batch_size": _positive_int_env("B24_P9_RECOVERY_BATCH_SIZE", 25),
                "stale_publishing_seconds": _positive_int_env(
                    "B24_P9_RECOVERY_STALE_PUBLISHING_SECONDS",
                    300,
                ),
            },
        }
    if os.getenv("SKELDIR_B12_P5_DISABLE_DENYLIST_GC_JOB") != "1":
        schedule["auth-denylist-gc"] = {
            "task": "app.tasks.maintenance.gc_expired_access_token_denylist",
            "schedule": crontab(minute="*/10"),
            "options": {"expires": 600},
        }
    if os.getenv("SKELDIR_B14_P3_DISABLE_EPHEMERAL_RESOLUTION_GC_JOB") != "1":
        schedule["b14-p3-ephemeral-resolution-gc"] = {
            "task": "app.tasks.maintenance.gc_expired_ephemeral_resolution",
            "schedule": crontab(minute="*/10"),
            "options": {"expires": 600},
        }
    if os.getenv("SKELDIR_B14_P4_DISABLE_RAW_EVENT_PAYLOAD_GC_JOB") != "1":
        schedule["b14-p4-raw-event-payload-gc"] = {
            "task": "app.tasks.maintenance.gc_expired_raw_event_payloads_all_tenants",
            "schedule": crontab(hour=3, minute=15),
            "options": {"expires": 3600},
        }
    return schedule


# Export for Celery configuration
BEAT_SCHEDULE = build_beat_schedule()

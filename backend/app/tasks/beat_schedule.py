"""
Celery Beat schedule definitions.

The schedule is isolated here to avoid circular imports between the Celery app
and task modules. An optional env var allows CI to shrink the refresh interval
so beat dispatch evidence appears within short CI timeboxes.
"""

import os
from typing import Dict, Any

from celery.schedules import crontab


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


def build_beat_schedule() -> Dict[str, Dict[str, Any]]:
    interval = _refresh_interval_seconds()
    schedule: Dict[str, Dict[str, Any]] = {
        "refresh-matviews-every-5-min": {
            "task": "app.tasks.matviews.pulse_matviews_global",
            "schedule": interval,
            "options": {"expires": max(int(interval), 1) * 2},
            "kwargs": {"schedule_class": "minute"},
        },
        "pii-audit-scanner": {
            "task": "app.tasks.maintenance.scan_for_pii_contamination",
            "schedule": crontab(hour=4, minute=0),
            "options": {"expires": 3600},
        },
        "enforce-data-retention": {
            "task": "app.tasks.maintenance.enforce_data_retention",
            "schedule": crontab(hour=3, minute=0),
            "options": {"expires": 3600},
        },
    }
    if os.getenv("SKELDIR_B12_P5_DISABLE_DENYLIST_GC_JOB") != "1":
        schedule["auth-denylist-gc"] = {
            "task": "app.tasks.maintenance.gc_expired_access_token_denylist",
            "schedule": crontab(minute="*/10"),
            "options": {"expires": 600},
        }
    return schedule


# Export for Celery configuration
BEAT_SCHEDULE = build_beat_schedule()

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
    return {
        "refresh-matviews-every-5-min": {
            "task": "app.tasks.maintenance.refresh_all_matviews_global_legacy",
            "schedule": interval,
            "options": {"expires": max(int(interval), 1) * 2},
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


# Export for Celery configuration
BEAT_SCHEDULE = build_beat_schedule()

"""B2.3 timing authority constants locked in Pre-P1 and consumed from P1 onward."""

from __future__ import annotations

from datetime import timedelta
from typing import Final


WEBHOOK_ARRIVAL_WINDOW: Final[timedelta] = timedelta(minutes=30)
PROVISIONAL_MATCH_WINDOW: Final[timedelta] = timedelta(hours=24)
REFUND_REOPENING_WINDOW: Final[timedelta] = timedelta(days=30)


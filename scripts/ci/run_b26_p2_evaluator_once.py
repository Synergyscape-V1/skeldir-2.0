#!/usr/bin/env python3
"""Run one B2.6-P2 operational-health evaluation and print JSON.

Deploys the evaluator exactly as production does (relay credential via
DATABASE_URL); used by the X assurance battery so the in-process test
engine (API credential) never masquerades as the relay consumer.
"""

from __future__ import annotations

import asyncio
import json
import sys


async def main() -> int:
    from app.tasks.b26_p2_health import (  # noqa: PLC0415
        evaluate_operational_health,
    )

    try:
        result = await evaluate_operational_health()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "evaluation_crashed", "error": str(exc)[:300]}))
        return 2
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Bounded child-to-parent result contract for B2.4-P6."""

from __future__ import annotations

import math
from typing import Any


RESULT_CONTRACT_VERSION = "b24-p6-child-result-v1"
MAX_RESULT_SUMMARY_BYTES = 32 * 1024


def _walk_numbers(value: Any):
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_numbers(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _walk_numbers(item)


def validate_result_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != RESULT_CONTRACT_VERSION:
        raise ValueError("unknown P6 result schema")
    forbidden = {"posterior", "trace", "inference_data", "idata", "draws"}
    if forbidden & set(payload):
        raise ValueError("full posterior trace is forbidden in P6 result summary")
    for number in _walk_numbers(payload):
        if not math.isfinite(float(number)):
            raise ValueError("non-finite number in P6 result summary")
    return payload

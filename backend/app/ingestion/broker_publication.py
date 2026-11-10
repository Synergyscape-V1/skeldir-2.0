"""Await synchronous broker publication without blocking the async event loop."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from starlette.concurrency import run_in_threadpool

_T = TypeVar("_T")


async def await_broker_call(
    func: Callable[..., _T], /, *args: Any, **kwargs: Any
) -> _T:
    """Run the existing synchronous broker callable off the event loop.

    The supplied callable, positional arguments and keyword arguments are
    passed through unchanged.  The framework's existing bounded thread pool
    executes the call; its return value is returned exactly and its exceptions
    propagate unchanged.  Publication policy remains at the call sites.
    """
    return await run_in_threadpool(func, *args, **kwargs)

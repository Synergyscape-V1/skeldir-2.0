"""Focused behavior for the awaited synchronous broker-publication boundary."""

from __future__ import annotations

import asyncio
import contextvars
import threading

import pytest
from celery import Celery, chain, current_app

from app.ingestion.broker_publication import await_broker_call

pytestmark = pytest.mark.asyncio


async def _wait_started(started: threading.Event, timeout_s: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while not started.is_set():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("publisher never started")
        await asyncio.sleep(0.01)


async def test_waiting_publisher_keeps_loop_responsive() -> None:
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def publisher() -> str:
        started.set()
        release.wait(2.0)
        finished.set()
        return "published"

    task = asyncio.create_task(await_broker_call(publisher))
    try:
        await _wait_started(started)
        progressed = asyncio.Event()

        async def other_work() -> None:
            progressed.set()

        await asyncio.wait_for(other_work(), timeout=1.0)
        assert progressed.is_set()
        assert not finished.is_set()
    finally:
        release.set()

    assert await asyncio.wait_for(task, timeout=2.0) == "published"
    assert finished.is_set()


async def test_publication_is_awaited_before_success() -> None:
    started = threading.Event()
    release = threading.Event()
    release_timer = threading.Timer(2.0, release.set)
    release_timer.start()

    def publisher() -> str:
        started.set()
        release.wait(5.0)
        return "completed"

    task = asyncio.create_task(await_broker_call(publisher))
    try:
        await _wait_started(started)
        assert not task.done()
    finally:
        release.set()
        release_timer.cancel()

    assert await task == "completed"


async def test_context_and_payload_are_preserved() -> None:
    original_app = current_app._get_current_object()
    actor = contextvars.ContextVar("actor", default="unset")
    app = Celery(
        "b26-p2-publication-binding-test",
        broker="memory://",
        backend="cache+memory://",
        set_as_current=False,
    )
    try:
        app.conf.update(
            task_default_queue="b26-p2-publication-binding",
            task_always_eager=False,
        )

        @app.task(name="b26.p2.publication.binding.first")
        def first(*args, **kwargs):  # noqa: ANN002, ANN003 - Celery payload passthrough
            return None

        @app.task(name="b26.p2.publication.binding.second")
        def second(*args, **kwargs):  # noqa: ANN002, ANN003 - Celery payload passthrough
            return None

        app.finalize()

        def publish() -> dict[str, object]:
            first_sig = first.s("payload", 7).set(headers={"actor": actor.get()})
            second_sig = second.si("payload").set(headers={"actor": actor.get()})
            plan = chain(first_sig, second_sig)
            result = plan.apply_async()
            return {
                "plan_app": plan.app.main,
                "signature_apps": [first_sig.app.main, second_sig.app.main],
                "result_app": result.app.main,
                "transport": app.connection_for_write().transport.driver_type,
                "context": actor.get(),
                "args": first_sig.args,
                "kwargs": first_sig.kwargs,
                "headers": first_sig.options.get("headers"),
                "result_task_id": result.id,
                "ambient_app": current_app.main,
            }

        actor.set("context-canary")
        observed = await await_broker_call(publish)

        assert observed["plan_app"] == app.main
        assert observed["signature_apps"] == [app.main, app.main]
        assert observed["result_app"] == app.main
        assert observed["transport"] == "memory"
        assert observed["context"] == "context-canary"
        assert observed["args"] == ("payload", 7)
        assert observed["kwargs"] == {}
        assert observed["headers"] == {"actor": "context-canary"}
        assert isinstance(observed["result_task_id"], str) and observed["result_task_id"]
    finally:
        app.close()

    assert current_app._get_current_object() is original_app


async def test_broker_exception_is_preserved() -> None:
    class BrokerBoom(RuntimeError):
        pass

    error = BrokerBoom("broker unavailable")

    def publish() -> None:
        raise error

    with pytest.raises(BrokerBoom) as observed:
        await await_broker_call(publish)
    assert observed.value is error


async def test_cancellation_does_not_report_publication_success() -> None:
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def publisher() -> str:
        started.set()
        release.wait(2.0)
        finished.set()
        return "published"

    task = asyncio.create_task(await_broker_call(publisher))
    try:
        await _wait_started(started)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not finished.is_set()
    finally:
        release.set()

    assert await asyncio.to_thread(finished.wait, 2.0)

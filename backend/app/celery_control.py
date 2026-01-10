"""
Celery remote control customization.

Celery's default Control uses a fanout exchange for pidbox, but the SQLAlchemy
transport only supports direct/topic exchanges. This override wires pidbox to
use the configured exchange type so inspect/ping can function with Postgres.
"""
from __future__ import annotations

from celery.app.control import Control as BaseControl, Inspect as BaseInspect, _after_fork_cleanup_control
from celery.exceptions import ImproperlyConfigured
from functools import cached_property
from kombu.pidbox import Mailbox
from kombu.utils.compat import register_after_fork
from kombu.utils.functional import lazy


class SkeldirInspect(BaseInspect):
    def _request(self, command, **kwargs):
        if command == "ping":
            timeout = self.timeout or 10.0
            result = self.app.send_task(
                "app.tasks.housekeeping.ping",
                queue="housekeeping",
                kwargs={},
            )
            payload = result.get(timeout=timeout)
            destination = self.destination
            if isinstance(destination, (list, tuple)):
                destination = destination[0] if destination else None
            node = destination or payload.get("worker") or "unknown"
            reply = {node: {"ok": "pong"}}
            if self.callback:
                self.callback(reply)
            return reply
        return super()._request(command, **kwargs)


class SkeldirControl(BaseControl):
    Mailbox = Mailbox

    def __init__(self, app=None):
        self.app = app
        if (app.conf.control_queue_durable and app.conf.control_queue_exclusive):
            raise ImproperlyConfigured(
                "control_queue_durable and control_queue_exclusive cannot both be True "
                "(exclusive queues are automatically deleted and cannot be durable).",
            )

        exchange_type = app.conf.control_exchange_type or "fanout"
        self.mailbox = self.Mailbox(
            app.conf.control_exchange,
            type=exchange_type,
            accept=app.conf.accept_content,
            serializer=app.conf.task_serializer,
            producer_pool=lazy(lambda: self.app.amqp.producer_pool),
            queue_ttl=app.conf.control_queue_ttl,
            reply_queue_ttl=app.conf.control_queue_ttl,
            queue_expires=app.conf.control_queue_expires,
            queue_exclusive=app.conf.control_queue_exclusive,
            queue_durable=app.conf.control_queue_durable,
            reply_queue_expires=app.conf.control_queue_expires,
        )
        register_after_fork(self, _after_fork_cleanup_control)

    @cached_property
    def inspect(self):
        return self.app.subclass_with_self(SkeldirInspect, reverse="control.inspect")

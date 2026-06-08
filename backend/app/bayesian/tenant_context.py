"""Task-scoped tenant DB context helpers for Bayesian workers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


TENANT_GUC_NAME = "app.current_tenant_id"


@dataclass(frozen=True)
class TenantConnectionCleanState:
    """Payload-free assertion result for a checked-out SQLAlchemy connection."""

    tenant_guc: str | None
    in_transaction: bool

    @property
    def is_clean(self) -> bool:
        return self.tenant_guc in {None, ""} and not self.in_transaction


def bind_transaction_local_tenant(conn: Connection, *, tenant_id: UUID) -> None:
    """Bind tenant authority to the current transaction using SET LOCAL semantics."""

    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


def current_tenant_guc(conn: Connection) -> str | None:
    """Return the current tenant GUC without throwing when it is absent."""

    value = conn.execute(
        text("SELECT current_setting('app.current_tenant_id', true)")
    ).scalar_one()
    return None if value in {None, ""} else str(value)


def assert_bound_tenant(conn: Connection, *, tenant_id: UUID) -> None:
    """Fail closed if a transaction did not bind the expected tenant."""

    actual = current_tenant_guc(conn)
    if actual != str(tenant_id):
        raise RuntimeError("bayesian_tenant_context_not_bound")


@contextmanager
def tenant_transaction(engine: Engine, *, tenant_id: UUID):
    """Open one transaction, bind tenant GUC locally, and close on every path."""

    with engine.begin() as conn:
        bind_transaction_local_tenant(conn, tenant_id=tenant_id)
        assert_bound_tenant(conn, tenant_id=tenant_id)
        yield conn


def checked_out_connection_state(conn: Connection) -> TenantConnectionCleanState:
    """Inspect clean-return state on a fresh checkout before tenant binding."""

    in_transaction = bool(conn.in_transaction())
    tenant_guc = current_tenant_guc(conn)
    return TenantConnectionCleanState(
        tenant_guc=tenant_guc,
        in_transaction=in_transaction,
    )


def assert_fresh_checkout_is_clean(engine: Engine) -> TenantConnectionCleanState:
    """Verify a fresh connection has no stale tenant GUC or open transaction."""

    with engine.connect() as conn:
        state = checked_out_connection_state(conn)
    if not state.is_clean:
        raise RuntimeError("bayesian_connection_returned_dirty")
    return state

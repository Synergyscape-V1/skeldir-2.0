"""
Request-scoped observability context (correlation IDs, tenant ID) using contextvars.
"""
from contextvars import ContextVar
from typing import Optional
from uuid import UUID

correlation_id_request_var: ContextVar[Optional[str]] = ContextVar("correlation_id_request", default=None)
correlation_id_business_var: ContextVar[Optional[str]] = ContextVar("correlation_id_business", default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


def set_request_correlation_id(value: Optional[str]) -> None:
    correlation_id_request_var.set(value)


def get_request_correlation_id() -> Optional[str]:
    return correlation_id_request_var.get()


def set_business_correlation_id(value: Optional[str]) -> None:
    correlation_id_business_var.set(value)


def get_business_correlation_id() -> Optional[str]:
    return correlation_id_business_var.get()


def set_tenant_id(value: Optional[UUID]) -> None:
    tenant_id_var.set(str(value) if value else None)


def get_tenant_id() -> Optional[str]:
    return tenant_id_var.get()


def set_user_id(value: Optional[UUID]) -> None:
    user_id_var.set(str(value) if value else None)


def get_user_id() -> Optional[str]:
    return user_id_var.get()


def log_context() -> dict:
    """Return a dict suitable for logger extra=... with correlation and tenant context."""
    return {
        "correlation_id_request": get_request_correlation_id(),
        "correlation_id_business": get_business_correlation_id(),
        "tenant_id": get_tenant_id(),
        "user_id": get_user_id(),
    }

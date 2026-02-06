"""Shared pytest configuration for top-level `tests/` suites."""

import logging


def pytest_configure() -> None:
    """Prevent known httpx/httpcore INFO-format logging incompatibility in pytest capture."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


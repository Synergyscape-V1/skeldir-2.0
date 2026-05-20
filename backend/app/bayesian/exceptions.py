"""B2.4 authority package exceptions."""

from __future__ import annotations


class BayesianAuthorityError(RuntimeError):
    """Base class for B2.4 authority-layer failures."""


class BayesianFitNotFoundError(BayesianAuthorityError):
    """Raised when a tenant-scoped fit authority row is not found."""


class BayesianArtifactNotFoundError(BayesianAuthorityError):
    """Raised when a tenant-scoped artifact authority row is not found."""

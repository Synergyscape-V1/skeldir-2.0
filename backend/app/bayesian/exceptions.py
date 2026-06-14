"""B2.4 authority package exceptions."""

from __future__ import annotations


class BayesianAuthorityError(RuntimeError):
    """Base class for B2.4 authority-layer failures."""


class BayesianFitNotFoundError(BayesianAuthorityError):
    """Raised when a tenant-scoped fit authority row is not found."""


class BayesianArtifactNotFoundError(BayesianAuthorityError):
    """Raised when a tenant-scoped artifact authority row is not found."""


class BayesianArtifactPolicyError(BayesianAuthorityError):
    """Raised when an artifact violates bounded P8 storage policy."""


class BayesianArtifactQuotaExceededError(BayesianArtifactPolicyError):
    """Raised when a tenant or fit artifact write exceeds quota."""


class BayesianSourceSnapshotError(BayesianAuthorityError):
    """Raised when a deterministic source snapshot cannot be constructed."""


class BayesianEligibilityError(BayesianAuthorityError):
    """Raised when source eligibility cannot be classified safely."""


class BayesianTenantContextError(BayesianAuthorityError):
    """Raised when P2 source reads are attempted without tenant context."""

"""Pydantic schemas for B2.4 authority surfaces."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


SHA256_HEX_PATTERN = r"^[a-f0-9]{64}$"
ARTIFACT_REF_PATTERN = r"^b24://[a-z0-9][a-z0-9._/-]{1,240}$"


class BayesianModelFitAuthority(BaseModel):
    """Serialized view of a fit authority row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    model_type: str = Field(min_length=2, max_length=64)
    model_version: str = Field(min_length=1, max_length=64)
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    status: str
    eligibility_status: str
    data_completeness_status: str
    fallback_applied: bool
    fallback_reason: str | None = None
    artifact_ref: str | None = Field(default=None, pattern=ARTIFACT_REF_PATTERN)
    artifact_hash: str | None = Field(default=None, pattern=SHA256_HEX_PATTERN)
    created_at: datetime
    updated_at: datetime


class BayesianArtifactAuthority(BaseModel):
    """Serialized view of an artifact authority row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    fit_id: UUID
    artifact_ref: str = Field(pattern=ARTIFACT_REF_PATTERN)
    artifact_hash: str = Field(pattern=SHA256_HEX_PATTERN)
    artifact_type: str
    storage_backend: str
    artifact_uri_internal: str = Field(min_length=1, max_length=1024)
    artifact_size_bytes: int = Field(ge=0)
    compression: str | None = None
    retention_class: str
    expires_at: datetime | None = None
    pruned_at: datetime | None = None
    created_at: datetime

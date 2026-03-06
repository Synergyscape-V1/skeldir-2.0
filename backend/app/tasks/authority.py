"""
Authority envelope contracts for tenant-scoped Celery tasks.

P7 introduces a polymorphic envelope:
- session: tenant + user + jti + iat (revocation enforced)
- system: tenant-only authority for non-session producers (webhooks/beat fanout)
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

AUTHORITY_ENVELOPE_HEADER = "skeldir_authority_envelope"


class SessionAuthorityEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_type: Literal["session"] = "session"
    tenant_id: UUID
    user_id: UUID
    jti: UUID
    iat: int


class SystemAuthorityEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_type: Literal["system"] = "system"
    tenant_id: UUID


AuthorityEnvelope = Annotated[
    Union[SessionAuthorityEnvelope, SystemAuthorityEnvelope],
    Field(discriminator="context_type"),
]

_AUTHORITY_ENVELOPE_ADAPTER = TypeAdapter(AuthorityEnvelope)


def parse_authority_envelope(value: Any) -> AuthorityEnvelope:
    return _AUTHORITY_ENVELOPE_ADAPTER.validate_python(value)


def authority_envelope_payload(value: AuthorityEnvelope) -> dict[str, Any]:
    return value.model_dump(mode="json")

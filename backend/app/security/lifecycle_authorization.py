from __future__ import annotations

"""Reusable authorization primitives for provider lifecycle boundaries."""

from typing import Annotated

from fastapi import Security

from app.security.auth import AuthContext, get_auth_context


async def require_lifecycle_read_access(
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
) -> AuthContext:
    return auth_context


async def require_lifecycle_mutation_access(
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["manager"])],
) -> AuthContext:
    return auth_context


from __future__ import annotations

import os
from typing import AsyncGenerator

from fastapi import Request, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session
from app.security.auth import AuthContext, get_auth_context


async def get_db_session(
    request: Request,
    auth_context: AuthContext = Security(get_auth_context, scopes=["viewer"]),
) -> AsyncGenerator[AsyncSession, None]:
    if os.getenv("CONTRACT_TESTING") == "1":
        request.state.db_session = object()
        yield request.state.db_session
        return
    async with db_session.get_session(
        auth_context.tenant_id,
        user_id=auth_context.user_id,
    ) as session:
        request.state.db_session = session
        yield session

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings

settings = get_settings()
_basic = HTTPBasic(auto_error=False)


async def auth_dependency(credentials: HTTPBasicCredentials | None = Depends(_basic)):
    if not settings.api_auth_enabled:
        return None
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    user_ok = secrets.compare_digest(credentials.username, settings.api_username)
    pass_ok = secrets.compare_digest(credentials.password, settings.api_password)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    return credentials
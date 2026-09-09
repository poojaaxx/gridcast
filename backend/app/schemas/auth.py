from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class UserOut(BaseModel):
    """Never includes password_hash - this is the only shape a user is ever
    returned to a client in."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    is_active: bool
    created_at: dt.datetime
    last_login_at: dt.datetime | None

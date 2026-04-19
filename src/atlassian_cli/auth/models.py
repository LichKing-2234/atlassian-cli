from enum import StrEnum

from pydantic import BaseModel


class AuthMode(StrEnum):
    BASIC = "basic"
    BEARER = "bearer"
    PAT = "pat"


class ResolvedAuth(BaseModel):
    mode: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None

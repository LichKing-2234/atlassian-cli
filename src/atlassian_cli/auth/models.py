from pydantic import BaseModel, Field

from atlassian_cli.compat import StrEnum


class AuthMode(StrEnum):
    BASIC = "basic"
    BEARER = "bearer"
    PAT = "pat"


class ResolvedAuth(BaseModel):
    mode: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)

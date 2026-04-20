from enum import StrEnum

from pydantic import BaseModel, Field

from atlassian_cli.auth.models import AuthMode


class Product(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"
    BITBUCKET = "bitbucket"


class Deployment(StrEnum):
    SERVER = "server"
    DC = "dc"
    CLOUD = "cloud"


class ProfileConfig(BaseModel):
    name: str
    product: Product
    deployment: Deployment
    url: str
    auth: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None


class RuntimeOverrides(BaseModel):
    profile: str | None = None
    product: Product | None = None
    deployment: Deployment | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    token: str | None = None
    auth: AuthMode | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    output: str = Field(default="table")

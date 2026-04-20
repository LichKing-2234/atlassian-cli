from enum import StrEnum

from pydantic import BaseModel, Field, StrictStr

from atlassian_cli.auth.models import AuthMode
from atlassian_cli.core.errors import ConfigError


class Product(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"
    BITBUCKET = "bitbucket"


class Deployment(StrEnum):
    SERVER = "server"
    DC = "dc"
    CLOUD = "cloud"


class ProductConfig(BaseModel):
    deployment: Deployment | None = None
    url: StrictStr | None = None
    auth: AuthMode | None = None
    username: StrictStr | None = None
    password: StrictStr | None = None
    token: StrictStr | None = None
    headers: dict[str, StrictStr] = Field(default_factory=dict)

    def to_profile_config(self, *, product: Product, name: str) -> "ProfileConfig":
        missing = [
            field
            for field in ("deployment", "url", "auth")
            if getattr(self, field) is None
        ]
        if missing:
            raise ConfigError(
                f"Product config [{product.value}] is missing required fields: {', '.join(missing)}"
            )
        return ProfileConfig(
            name=name,
            product=product,
            deployment=self.deployment,
            url=self.url,
            auth=self.auth,
            username=self.username,
            password=self.password,
            token=self.token,
            headers=self.headers,
        )


class ProfileConfig(BaseModel):
    name: str
    product: Product
    deployment: Deployment
    url: str
    auth: AuthMode
    username: str | None = None
    password: str | None = None
    token: str | None = None
    headers: dict[str, StrictStr] = Field(default_factory=dict)


class LoadedConfig(BaseModel):
    headers: dict[str, StrictStr] = Field(default_factory=dict)
    jira: ProductConfig | None = None
    confluence: ProductConfig | None = None
    bitbucket: ProductConfig | None = None
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)

    def product_config(self, product: Product) -> ProductConfig | None:
        if product is Product.JIRA:
            return self.jira
        if product is Product.CONFLUENCE:
            return self.confluence
        return self.bitbucket


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

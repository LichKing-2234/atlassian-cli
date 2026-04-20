from pydantic import BaseModel

from atlassian_cli.auth.models import ResolvedAuth
from atlassian_cli.config.models import Deployment, Product


class ExecutionContext(BaseModel):
    profile: str | None
    product: Product
    deployment: Deployment
    url: str
    output: str
    auth: ResolvedAuth

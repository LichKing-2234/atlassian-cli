from collections.abc import Callable
from typing import Any

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


class LazyExecutionContext:
    def __init__(self, factory: Callable[[], ExecutionContext]) -> None:
        self._factory = factory
        self._context: ExecutionContext | None = None

    def resolve(self) -> ExecutionContext:
        if self._context is None:
            self._context = self._factory()
        return self._context

    def __getattr__(self, name: str) -> Any:
        return getattr(self.resolve(), name)

from datetime import datetime
from functools import wraps
from typing import Any, TypeVar

from pydantic import BaseModel

from atlassian_cli.core.errors import TransportError

T = TypeVar("T", bound="ApiModel")


def require_api_response_object(value: object, *, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    raise TransportError(
        f"{label} was not a JSON object. "
        "The server returned a non-JSON response; check authentication headers."
    )


class ApiModel(BaseModel):
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        raw_method = cls.__dict__.get("from_api_response")
        if not isinstance(raw_method, classmethod):
            return
        method = raw_method.__func__
        if getattr(method, "_validates_api_response_object", False):
            return

        @wraps(method)
        def wrapped(model_cls: type[T], data: object, **method_kwargs: Any) -> T:
            payload = require_api_response_object(
                data,
                label=f"{model_cls.__name__} response",
            )
            return method(model_cls, payload, **method_kwargs)

        wrapped._validates_api_response_object = True  # type: ignore[attr-defined]
        cls.from_api_response = classmethod(wrapped)  # type: ignore[method-assign]

    @classmethod
    def from_api_response(cls: type[T], data: dict[str, Any] | None, **kwargs: Any) -> T:
        raise NotImplementedError

    def to_simplified_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class TimestampMixin:
    @staticmethod
    def format_timestamp(value: str | None) -> str | None:
        if not value:
            return None

        candidate = value.replace("Z", "+00:00")
        if "+" in candidate and ":" not in candidate[-5:]:
            pos = candidate.rfind("+")
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3 :]}"
        elif "-" in candidate[10:] and ":" not in candidate[-5:]:
            pos = candidate.rfind("-")
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3 :]}"

        try:
            return datetime.fromisoformat(candidate).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound="ApiModel")


class ApiModel(BaseModel):
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
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3:]}"
        elif "-" in candidate[10:] and ":" not in candidate[-5:]:
            pos = candidate.rfind("-")
            candidate = f"{candidate[: pos + 3]}:{candidate[pos + 3:]}"

        try:
            return datetime.fromisoformat(candidate).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return value

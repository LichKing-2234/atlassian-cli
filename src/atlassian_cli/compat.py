from __future__ import annotations

from datetime import timezone
from enum import Enum

try:
    from enum import StrEnum
except ImportError:

    class StrEnum(str, Enum):
        pass


try:
    import tomllib
except ImportError:
    import tomli as tomllib

UTC = timezone.utc

__all__ = ["StrEnum", "UTC", "tomllib"]

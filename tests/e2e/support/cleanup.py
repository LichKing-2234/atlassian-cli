from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CleanupRegistry:
    callbacks: list[tuple[str, Callable[[], None]]] = field(default_factory=list)

    def add(self, label: str, callback: Callable[[], None]) -> None:
        self.callbacks.append((label, callback))

    def run(self) -> None:
        errors: list[str] = []
        while self.callbacks:
            label, callback = self.callbacks.pop()
            try:
                callback()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        if errors:
            raise AssertionError("cleanup failed\n" + "\n".join(errors))

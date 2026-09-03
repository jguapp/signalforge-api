from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    """Tiny process-local counters used by the HTTP boundary."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = defaultdict(int)
        self._lock = Lock()

    def increment(self, name: str, **labels: str) -> None:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                self._format(name, labels): value
                for (name, labels), value in sorted(self._counters.items())
            }

    @staticmethod
    def _format(name: str, labels: tuple[tuple[str, str], ...]) -> str:
        suffix = ",".join(f"{key}={value}" for key, value in labels)
        return f"{name}{{{suffix}}}" if suffix else name


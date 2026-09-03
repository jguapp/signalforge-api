from __future__ import annotations

from collections.abc import Sequence

from .models import Comparator, MetricPoint, Monitor


def point_breaches(monitor: Monitor, point: MetricPoint) -> bool:
    comparisons = {
        Comparator.ABOVE: point.value > monitor.threshold,
        Comparator.AT_OR_ABOVE: point.value >= monitor.threshold,
        Comparator.BELOW: point.value < monitor.threshold,
        Comparator.AT_OR_BELOW: point.value <= monitor.threshold,
    }
    return comparisons[monitor.comparator]


def window_is_breaching(monitor: Monitor, points: Sequence[MetricPoint]) -> bool:
    """A monitor fires only when its complete recent window is breaching."""
    if len(points) < monitor.window_size:
        return False
    window = points[-monitor.window_size :]
    return all(point_breaches(monitor, point) for point in window)


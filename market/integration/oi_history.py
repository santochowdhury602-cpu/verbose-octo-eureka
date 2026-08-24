from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OIState:
    event_time: float | None
    open_interest: float | None
    change_pct: float | None
    stale: bool


class OIHistory:
    """Chronological, duplicate-safe OI observations for replay and live feeds."""

    def __init__(self, stale_after: float = 120.0) -> None:
        if stale_after <= 0:
            raise ValueError("stale_after must be positive")
        self.stale_after = stale_after
        self._observations: dict[float, float] = {}

    def ingest(self, event_time: float, open_interest: float) -> OIState:
        event_time = float(event_time)
        open_interest = float(open_interest)
        if event_time < 0 or open_interest < 0:
            raise ValueError("OI event time and value must be non-negative")
        self._observations.setdefault(event_time, open_interest)
        return self.state(as_of=event_time)

    def state(self, as_of: float, stale_after: float | None = None) -> OIState:
        visible = sorted(
            (timestamp, value)
            for timestamp, value in self._observations.items()
            if timestamp <= as_of
        )
        if not visible:
            return OIState(None, None, None, True)
        timestamp, current = visible[-1]
        previous = visible[-2][1] if len(visible) > 1 else None
        change = None if previous in (None, 0) else (current - previous) / abs(previous) * 100
        threshold = self.stale_after if stale_after is None else stale_after
        return OIState(timestamp, current, change, as_of - timestamp > threshold)
from __future__ import annotations

from dataclasses import dataclass

from market.integration.context_adapter import LiveSnapshotContextAdapter
from market.integration.live_snapshot import LiveMarketSnapshot


@dataclass(frozen=True)
class ReplayEvent:
    event_time: float
    kind: str
    payload: dict


class ReplayHarness:
    """Replay an ordered event stream without consulting wall-clock time."""

    def __init__(self, events, context_factory) -> None:
        self.events = tuple(events)
        self.context_factory = context_factory
        if any(current.event_time < previous.event_time for previous, current in zip(self.events, self.events[1:])):
            raise ValueError("Replay events must be chronological")

    def run(self, pipeline):
        results = []
        seen = []
        for event in self.events:
            seen.append(event)
            context = self.context_factory(tuple(seen), event.event_time)
            results.append(pipeline.run(context))
        return results


@dataclass(frozen=True)
class RawBybitEvent:
    event_time: float
    received_time: float
    message: dict


@dataclass
class RawReplayResult:
    pipeline_result: object

    def to_dict(self):
        result = self.pipeline_result
        return {
            "context": result.context.to_dict(),
            "decision": result.decision.to_dict(),
            "risk": result.risk.to_dict(),
            "intent": result.intent.to_dict() if result.intent else None,
        }


class RawBybitReplayHarness:
    """Replay raw Bybit messages through the production feed parser and pipeline."""

    def __init__(self, events, symbol="BTCUSDT", timeframe_metadata=None):
        self.events = tuple(
            event if isinstance(event, RawBybitEvent) else RawBybitEvent(**event)
            for event in events
        )
        if any(current.event_time < previous.event_time for previous, current in zip(self.events, self.events[1:])):
            raise ValueError("Raw replay events must be chronological")
        self.symbol = symbol
        self.timeframe_metadata = timeframe_metadata or {}

    def run(self, pipeline):
        snapshot = LiveMarketSnapshot(self.symbol)
        for event in self.events:
            snapshot.feed._process_message(
                event.message,
                received_time=event.received_time,
            )
        adapter = LiveSnapshotContextAdapter(snapshot)
        calculation_time = self.events[-1].received_time if self.events else 0.0
        context = adapter.build(calculation_time=calculation_time)
        if context is None:
            raise ValueError("Raw replay produced no price-bearing market context")
        context.metadata["timeframe_metadata"] = self.timeframe_metadata
        return RawReplayResult(pipeline.run(context))
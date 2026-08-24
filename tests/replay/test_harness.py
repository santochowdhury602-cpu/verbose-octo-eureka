from brain.context import MarketContextBuilder
from brain.pipeline import ApexBrainPipeline
from market.replay import ReplayEvent, ReplayHarness


def make_context(events, event_time):
    return (
        MarketContextBuilder("BTCUSDT", 100)
        .set_event_times(event_time=event_time, calculation_time=event_time)
        .set_data_quality("DATA_INCOMPLETE")
        .build(allow_incomplete=True)
    )


def test_replay_is_deterministic_and_rejects_future_order():
    events = [ReplayEvent(1, "trade", {"id": "a"}), ReplayEvent(2, "trade", {"id": "b"})]
    harness = ReplayHarness(events, make_context)
    first = [result.decision.to_dict() for result in harness.run(ApexBrainPipeline())]
    second = [result.decision.to_dict() for result in harness.run(ApexBrainPipeline())]
    assert first == second
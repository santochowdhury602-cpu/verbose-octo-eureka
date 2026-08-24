from brain.pipeline import ApexBrainPipeline
from brain.risk import RiskConfig, RiskGate
from market.replay import RawBybitEvent, RawBybitReplayHarness


def event(time, topic, data, kind="delta"):
    message = {"topic": topic, "type": kind, "data": data, "ts": int(time * 1000)}
    return RawBybitEvent(time, time, message)


def raw_fixture(direction="LONG", include_oi=True, include_funding=True):
    values = (
        [(10, 5, 8), (12, 6, 11), (9, 4, 7), (13, 7, 12), (11, 6, 10), (15, 8, 14), (14, 9, 13), (16, 10, 16)]
        if direction == "LONG"
        else [(15, 10, 15), (13, 8, 13), (14, 9, 14), (11, 6, 11), (12, 7, 12), (9, 4, 9), (3, 2, 3)]
    )
    events = [event(1, "orderbook.50.BTCUSDT", {"u": 1, "b": [[99, 2]], "a": [[101, 2]]}, "snapshot")]
    for index, (high, low, close) in enumerate(values, 2):
        events.append(event(index, "kline.1.BTCUSDT", [{"start": index * 1000, "open": close, "high": high, "low": low, "close": close, "volume": 10}]))
    events.append(event(20, "publicTrade.BTCUSDT", [{"i": "trade-1", "T": 20000, "p": values[-1][2], "v": 20, "S": "Buy" if direction == "LONG" else "Sell"}]))
    ticker = {}
    if include_oi:
        ticker["openInterest"] = "100"
    if include_funding:
        ticker["fundingRate"] = "0.001"
    events.append(event(21, "tickers.BTCUSDT", ticker))
    return events


def pipeline():
    result = ApexBrainPipeline(RiskGate(RiskConfig(minimum_confidence=20)))
    result.decision.minimum_confidence = 20
    return result


def test_raw_replay_is_deterministic():
    events = raw_fixture()
    first = RawBybitReplayHarness(events).run(pipeline()).to_dict()
    second = RawBybitReplayHarness(events).run(pipeline()).to_dict()
    assert first == second
    assert first["context"]["exchange"] == "BYBIT"


def test_raw_replay_negative_events_never_trade():
    cases = [
        raw_fixture()[:-1] + [event(21, "tickers.BTCUSDT", {"openInterest": "100"})],
        raw_fixture(include_oi=False),
        raw_fixture(include_funding=False),
        raw_fixture()[:1] + [event(2, "orderbook.50.BTCUSDT", {"u": 2, "b": [[102, 3]], "a": [[101, 3]]})],
        raw_fixture()[:1] + [event(2, "orderbook.50.BTCUSDT", {"u": 2, "b": [["bad", 3]], "a": [[101, 3]]})],
        raw_fixture() + [event(22, "publicTrade.BTCUSDT", [{"i": "trade-0", "T": 19000, "p": 100, "v": 1, "S": "Buy"}])],
        raw_fixture()[:1] + [event(2, "kline.1.BTCUSDT", [{"start": 2000, "open": 100, "high": 99, "low": 101, "close": 100, "volume": 1}])],
    ]
    for events in cases:
        result = RawBybitReplayHarness(events).run(pipeline())
        assert result.pipeline_result.decision.action == "WAIT"
    duplicate = raw_fixture() + [event(21, "publicTrade.BTCUSDT", [{"i": "trade-1", "T": 20000, "p": 100, "v": 1, "S": "Buy"}])]
    assert RawBybitReplayHarness(duplicate).run(pipeline()).to_dict() == RawBybitReplayHarness(raw_fixture()).run(pipeline()).to_dict()


def test_raw_replay_can_produce_both_directional_decisions():
    long_result = RawBybitReplayHarness(raw_fixture("LONG")).run(pipeline())
    short_result = RawBybitReplayHarness(raw_fixture("SHORT")).run(pipeline())
    assert long_result.pipeline_result.decision.action == "LONG"
    assert short_result.pipeline_result.decision.action == "SHORT"


def test_raw_replay_matches_direct_canonical_pipeline_result():
    replayed = RawBybitReplayHarness(raw_fixture()).run(pipeline())
    direct = pipeline().run(replayed.pipeline_result.context).to_dict()
    assert direct == replayed.to_dict()


def test_raw_replay_stale_timeframe_is_not_actionable():
    result = RawBybitReplayHarness(
        raw_fixture(),
        timeframe_metadata={
            "1m": {
                "latest_event_time": 1,
                "expected_interval": 1,
                "stale_threshold": 2,
            }
        },
    ).run(pipeline())
    assert result.pipeline_result.decision.action == "WAIT"
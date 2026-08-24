from brain.structure import MarketStructureEngine


def candle(event_time, high, low):
    close = (high + low) / 2
    return {
        "event_time": event_time,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
    }


def test_future_candles_are_not_used_before_pivot_confirmation():
    candles = [
        candle(1, 10, 8),
        candle(2, 12, 9),
        candle(3, 20, 10),
        candle(4, 13, 9),
        candle(5, 11, 8),
    ]
    engine = MarketStructureEngine(swing_strength=1)

    before_confirmation = engine.analyze(candles, as_of=3)
    after_confirmation = engine.analyze(candles, as_of=4)

    assert before_confirmation.last_high is None
    assert after_confirmation.last_high == 20
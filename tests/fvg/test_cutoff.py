from brain.fvg import FVGEngine


def candle(event_time, open_, high, low, close):
    return {
        "event_time": event_time,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
    }


def test_fvg_fill_is_not_known_before_later_candle():
    candles = [
        candle(1, 99, 100, 98, 99),
        candle(2, 101, 105, 101, 104),
        candle(3, 106, 110, 106, 109),
        candle(4, 100, 102, 99, 100),
    ]
    engine = FVGEngine()

    before_fill = engine.analyze(candles, as_of=3)
    after_fill = engine.analyze(candles, as_of=4)

    assert before_fill.latest_fvg is not None
    assert before_fill.latest_fvg.filled is False
    assert after_fill.latest_fvg.filled is True

from brain.liquidity import LiquidityEngine

def candle(

    high: float,

    low: float,

    close: float,

    open_: float | None = None,

):

    if open_ is None:

        open_ = close

    return {

        "open": open_,

        "high": high,

        "low": low,

        "close": close,

    }

def test_equal_high_creates_buy_side_pool():

    candles = [

        candle(100, 95, 98),

        candle(105, 97, 103),

        candle(100, 94, 97),

        candle(105, 96, 102),

    ]

    engine = LiquidityEngine(

        tolerance_pct=0.001,

        min_touches=2,

    )

    result = engine.analyze(candles)

    assert len(result.buy_side_pools) >= 1

    pool = result.buy_side_pools[0]

    assert pool.kind == "BUY_SIDE"

    assert pool.touches >= 2

def test_equal_low_creates_sell_side_pool():

    candles = [

        candle(105, 100, 103),

        candle(104, 95, 98),

        candle(103, 100, 102),

        candle(106, 95, 101),

    ]

    engine = LiquidityEngine(

        tolerance_pct=0.001,

        min_touches=2,

    )

    result = engine.analyze(candles)

    assert len(result.sell_side_pools) >= 1

    pool = result.sell_side_pools[0]

    assert pool.kind == "SELL_SIDE"

    assert pool.touches >= 2

def test_bullish_sell_side_sweep():

    candles = [

        candle(105, 100, 103),

        candle(104, 95, 98),

        candle(103, 100, 102),

        candle(106, 95, 101),

        candle(108, 94, 103),

        candle(110, 99, 109),

    ]

    engine = LiquidityEngine(

        tolerance_pct=0.001,

        min_touches=2,

        displacement_pct=0.001,

    )

    result = engine.analyze(candles)

    assert result.latest_sweep is not None

    assert result.latest_sweep.direction == "BULLISH"

    assert result.latest_sweep.pool_kind == "SELL_SIDE"

    assert result.bias == "LONG"

def test_bearish_buy_side_sweep():

    candles = [

        candle(100, 95, 98),

        candle(105, 97, 103),

        candle(100, 94, 97),

        candle(105, 96, 102),

        candle(107, 98, 103),

        candle(106, 100, 101),

    ]

    engine = LiquidityEngine(

        tolerance_pct=0.001,

        min_touches=2,

        displacement_pct=0.001,

    )

    result = engine.analyze(candles)

    assert result.latest_sweep is not None

    assert result.latest_sweep.direction == "BEARISH"

    assert result.latest_sweep.pool_kind == "BUY_SIDE"

    assert result.bias == "SHORT"

def test_no_liquidity_means_wait():

    candles = [

        candle(100, 95, 98),

        candle(103, 97, 101),

        candle(106, 99, 104),

    ]

    engine = LiquidityEngine()

    result = engine.analyze(candles)

    assert result.latest_sweep is None

    assert result.bias == "WAIT"

    assert result.confidence == 0.0

def test_bullish_displacement():

    candles = [
        # Equal lows = SELL-SIDE liquidity at 100
        candle(105, 100, 103),
        candle(104, 95, 98),
        candle(103, 100, 102),
        candle(106, 101, 104),

        # Sweep below 100 and reclaim
        candle(105, 99, 102),

        # Strong bullish displacement AFTER sweep
        candle(112, 101, 110),
    ]

    engine = LiquidityEngine(
        tolerance_pct=0.001,
        min_touches=2,
        displacement_pct=0.001,
    )

    result = engine.analyze(candles)

    assert result.latest_sweep is not None
    assert result.latest_sweep.direction == "BULLISH"
    assert result.latest_sweep.displacement is True
    assert result.confidence == 90.0

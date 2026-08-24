from market.bybit.public_ws import BybitPublicFeed


def test_kline_and_oi_parsers_preserve_unavailable_change():
    feed = BybitPublicFeed()
    feed._process_message({
        "topic": "kline.1.BTCUSDT",
        "data": [{"start": "1000", "open": "100", "high": "102", "low": "99", "close": "101", "volume": "4"}],
    })
    feed._process_message({"topic": "tickers.BTCUSDT", "ts": 1000, "data": {"openInterest": "10", "fundingRate": "0.001"}})
    assert feed.data.candles[0]["close"] == 101
    assert feed.data.open_interest == 10
    assert feed.data.oi_change_pct is None
    feed._process_message({"topic": "tickers.BTCUSDT", "ts": 2000, "data": {"openInterest": "11"}})
    assert feed.data.oi_change_pct == 10
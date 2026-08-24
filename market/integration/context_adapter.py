from __future__ import annotations

from brain.context import MarketContext, MarketContextBuilder, OrderBook, Trade
from brain.context import Candle


class LiveSnapshotContextAdapter:
    """Convert one live snapshot into the canonical market context."""

    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot

    def build(self, calculation_time: float | None = None) -> MarketContext | None:
        state = self.snapshot.build(calculation_time=calculation_time)
        if state is None:
            return None

        data = self.snapshot.feed.data
        quality, quality_reason = data.quality(now=calculation_time)
        if quality == "OK" and data.open_interest is None:
            quality = "DATA_INCOMPLETE"
            quality_reason = "Open interest is unavailable"
        if quality == "OK" and data.funding_rate is None:
            quality = "DATA_INCOMPLETE"
            quality_reason = "Funding is unavailable"
        order_book = None
        if data.bids or data.asks:
            try:
                order_book = OrderBook(
                    bids=tuple(data.snapshot_bids(50)),
                    asks=tuple(data.snapshot_asks(50)),
                )
            except ValueError:
                order_book = None

        trades = tuple(
            Trade(
                trade_id=str(item["id"]),
                event_time=float(item["timestamp"]) / 1000,
                price=float(item["price"]),
                quantity=float(item["quantity"]),
                side=str(item["side"]),
            )
            for item in data.trades
            if item.get("id") is not None
        )
        flow = state.order_flow
        return (
            MarketContextBuilder(state.symbol, state.price, state.timeframe)
            .set_exchange("BYBIT")
            .set_price(state.price, volume=data.volume)
            .set_market_data(
                candles=tuple(Candle(**candle) for candle in data.candles),
                order_book=order_book,
                trades=trades,
                delta=flow.get("delta"),
                cvd=flow.get("cumulative_delta"),
                open_interest=data.open_interest,
                oi_change=data.oi_change_pct,
                funding=data.funding_rate,
            )
            .set_event_times(
                event_time=data.last_event_time,
                received_time=data.last_update,
                calculation_time=calculation_time,
            )
            .set_data_quality(quality, quality_reason)
            .build(allow_incomplete=True)
        )
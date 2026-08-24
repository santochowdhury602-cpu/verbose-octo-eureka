import asyncio
import json
import time
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from market.integration.oi_history import OIHistory

try:
    import websockets
except ImportError:  # pragma: no cover - exercised in dependency-free installs
    websockets = None


BYBIT_PUBLIC_WS = "wss://stream.bybit.com/v5/public/linear"


@dataclass
class BybitMarketData:

    symbol: str

    price: float | None = None

    # Local reconstructed order book.
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)

    trades: list[dict[str, Any]] = field(
        default_factory=list
    )

    last_trade_id: str | None = None
    trade_ids: set[str] = field(default_factory=set)
    last_trade_event_time: float | None = None
    last_update: float = 0.0
    last_event_time: float | None = None
    last_sequence: int | None = None
    data_quality: str = "DATA_INCOMPLETE"
    quality_reason: str = "Waiting for a valid order-book snapshot"
    candles: list[dict[str, Any]] = field(default_factory=list)
    open_interest: float | None = None
    previous_open_interest: float | None = None
    oi_change_pct: float | None = None
    funding_rate: float | None = None
    volume: float | None = None
    volatility: float | None = None

    def _clean_book(self) -> None:

        self.bids = {
            price: qty
            for price, qty in self.bids.items()
            if qty > 0
        }

        self.asks = {
            price: qty
            for price, qty in self.asks.items()
            if qty > 0
        }

    def quality(self, max_age: float = 10.0, now: float | None = None) -> tuple[str, str]:
        if self.data_quality != "OK":
            return self.data_quality, self.quality_reason
        current_time = time.time() if now is None else now
        if self.last_update <= 0 or current_time - self.last_update > max_age:
            return "DATA_STALE", "Market data is older than the allowed age"
        return "OK", ""

    def sorted_bids(self, depth: int = 50):
        return sorted(
            self.bids.items(),
            key=lambda x: x[0],
            reverse=True,
        )[:depth]

    def sorted_asks(self, depth: int = 50):
        return sorted(
            self.asks.items(),
            key=lambda x: x[0],
        )[:depth]

    def orderbook_imbalance(
        self,
        depth: int = 20,
    ) -> float:

        bids = self.sorted_bids(depth)
        asks = self.sorted_asks(depth)

        bid_volume = sum(
            price * quantity
            for price, quantity in bids
        )

        ask_volume = sum(
            price * quantity
            for price, quantity in asks
        )

        total = bid_volume + ask_volume

        if total <= 0:
            return 0.0

        imbalance = (
            bid_volume - ask_volume
        ) / total

        # Numerical safety.
        return max(
            -1.0,
            min(1.0, imbalance),
        )

    def snapshot_bids(self, depth: int = 50):
        return [
            [price, quantity]
            for price, quantity
            in self.sorted_bids(depth)
        ]

    def snapshot_asks(self, depth: int = 50):
        return [
            [price, quantity]
            for price, quantity
            in self.sorted_asks(depth)
        ]


class BybitPublicFeed:

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        orderbook_depth: int = 50,
    ):

        self.symbol = symbol.upper()

        self.orderbook_depth = orderbook_depth

        self.data = BybitMarketData(
            symbol=self.symbol
        )

        self.running = False

        self._trade_sequence = 0
        self.oi_history = OIHistory()

    def _reset_state(self) -> None:
        self.data.bids.clear()
        self.data.asks.clear()
        self.data.trades.clear()
        self.data.price = None
        self.data.last_trade_id = None
        self.data.trade_ids.clear()
        self.data.last_trade_event_time = None
        self.data.last_update = 0.0
        self.data.last_event_time = None
        self.data.last_sequence = None
        self.data.data_quality = "DATA_INCOMPLETE"
        self.data.quality_reason = "Waiting for a valid order-book snapshot"
        self.data.candles.clear()
        self.data.open_interest = None
        self.data.previous_open_interest = None
        self.data.oi_change_pct = None
        self.data.funding_rate = None
        self.data.volume = None
        self.data.volatility = None
        self.oi_history = OIHistory()

    def _invalid(self, reason: str) -> None:
        self.data.data_quality = "DATA_INVALID"
        self.data.quality_reason = reason

    def _subscription_message(self):

        return {
            "op": "subscribe",
            "args": [
                f"orderbook.{self.orderbook_depth}.{self.symbol}",
                f"publicTrade.{self.symbol}",
                f"kline.1.{self.symbol}",
                f"tickers.{self.symbol}",
            ],
        }

    def _apply_orderbook(
        self,
        message: dict[str, Any],
        received_time: float | None = None,
    ) -> None:

        data = message.get("data")

        if not data:
            self._invalid("Missing WebSocket data payload")
            return

        sequence = data.get("u")
        if sequence is not None:
            try:
                sequence = int(sequence)
            except (TypeError, ValueError):
                self._invalid("Invalid order-book sequence")
                return
            if self.data.last_sequence is not None and sequence <= self.data.last_sequence:
                self._invalid("Out-of-order order-book update")
                return

        def levels(key: str) -> list[tuple[float, float]] | None:
            result = []
            for level in data.get(key, []):
                if not isinstance(level, (list, tuple)) or len(level) != 2:
                    return None
                try:
                    price = float(level[0])
                    quantity = float(level[1])
                except (TypeError, ValueError):
                    return None
                if not isfinite(price) or not isfinite(quantity) or price <= 0 or quantity < 0:
                    return None
                result.append((price, quantity))
            return result

        bids = levels("b")
        asks = levels("a")
        if bids is None or asks is None:
            self._invalid("Malformed or invalid order-book level")
            return

        # -----------------------------------------
        # INITIAL SNAPSHOT
        # -----------------------------------------

        if message.get("type") == "snapshot":

            self.data.bids.clear()
            self.data.asks.clear()

            for price, quantity in bids:

                if quantity > 0:
                    self.data.bids[
                        price
                    ] = quantity

            for price, quantity in asks:

                if quantity > 0:
                    self.data.asks[
                        price
                    ] = quantity

        # -----------------------------------------
        # DELTA UPDATE
        # -----------------------------------------

        else:

            for price, quantity in bids:

                if quantity == 0:
                    self.data.bids.pop(
                        price,
                        None,
                    )
                else:
                    self.data.bids[
                        price
                    ] = quantity

            for price, quantity in asks:

                if quantity == 0:
                    self.data.asks.pop(
                        price,
                        None,
                    )
                else:
                    self.data.asks[
                        price
                    ] = quantity

        self.data._clean_book()

        if self.data.bids and self.data.asks:
            if max(self.data.bids) >= min(self.data.asks):
                self._invalid("Order book is crossed")
                return

        if sequence is not None:
            self.data.last_sequence = sequence

        best_bid = self.data.sorted_bids(1)

        if best_bid:
            self.data.price = best_bid[0][0]

        self.data.last_update = time.time() if received_time is None else received_time
        self.data.last_event_time = float(message.get("ts", self.data.last_update * 1000)) / 1000
        self.data.data_quality = "OK"
        self.data.quality_reason = ""

    def _process_trade(
        self,
        trade: dict[str, Any],
        received_time: float | None = None,
    ) -> None:

        trade_id = str(
            trade.get(
                "i",
                f"{trade.get('T')}-{self._trade_sequence}",
            )
        )

        self._trade_sequence += 1

        # Avoid duplicate trade IDs.
        if trade_id in self.data.trade_ids:
            return

        timestamp_ms = int(
            trade.get(
                "T",
                time.time() * 1000,
            )
        )
        event_time = timestamp_ms / 1000
        if self.data.last_trade_event_time is not None and event_time < self.data.last_trade_event_time:
            self._invalid("Out-of-order trade event")
            return

        record = {
            "id": trade_id,
            "timestamp": timestamp_ms,
            "price": float(trade["p"]),
            "quantity": float(trade["v"]),
            "side": str(
                trade["S"]
            ).upper(),
        }

        if record["price"] <= 0 or record["quantity"] <= 0:
            self._invalid("Invalid trade price or quantity")
            return

        self.data.price = record["price"]
        self.data.last_trade_id = trade_id
        self.data.trade_ids.add(trade_id)
        self.data.last_trade_event_time = event_time

        self.data.trades.append(record)

        # Keep bounded memory.
        self.data.trades = self.data.trades[-5000:]

        self.data.last_update = time.time() if received_time is None else received_time
        self.data.last_event_time = event_time

    def _process_message(
        self,
        message: dict[str, Any],
        received_time: float | None = None,
    ) -> None:

        topic = message.get(
            "topic",
            "",
        )

        data = message.get("data")

        if not data:
            self._invalid("Missing WebSocket data payload")
            return

        if topic.startswith(
            "orderbook."
        ):

            self._apply_orderbook(
                message,
                received_time=received_time,
            )

        elif topic.startswith(
            "publicTrade."
        ):

            if isinstance(data, list):

                for trade in data:
                    try:
                        self._process_trade(trade, received_time=received_time)
                    except (KeyError, TypeError, ValueError):
                        self._invalid("Malformed trade payload")

        elif topic.startswith("kline."):
            if not isinstance(data, list):
                self._invalid("Malformed kline payload")
                return
            for item in data:
                try:
                    candle = {
                        "event_time": float(item["start"]) / 1000,
                        "open": float(item["open"]),
                        "high": float(item["high"]),
                        "low": float(item["low"]),
                        "close": float(item["close"]),
                        "volume": float(item["volume"]),
                    }
                    if candle["low"] > min(candle["open"], candle["close"]) or candle["high"] < max(candle["open"], candle["close"]):
                        raise ValueError
                    self.data.candles = [old for old in self.data.candles if old["event_time"] != candle["event_time"]][-499:]
                    self.data.candles.append(candle)
                    self.data.volume = candle["volume"]
                    self.data.last_event_time = candle["event_time"]
                    self.data.last_update = time.time() if received_time is None else received_time
                except (KeyError, TypeError, ValueError):
                    self._invalid("Malformed kline payload")

        elif topic.startswith("tickers."):
            if not isinstance(data, dict):
                self._invalid("Malformed ticker payload")
                return
            try:
                if data.get("openInterest") is not None:
                    event_time = float(message.get("ts", 0)) / 1000
                    state = self.oi_history.ingest(
                        event_time,
                        float(data["openInterest"]),
                    )
                    self.data.open_interest = state.open_interest
                    self.data.oi_change_pct = state.change_pct
                if data.get("fundingRate") is not None:
                    self.data.funding_rate = float(data["fundingRate"])
                if data.get("volume24h") is not None:
                    self.data.volume = float(data["volume24h"])
                self.data.last_update = time.time() if received_time is None else received_time
                if message.get("ts") is not None:
                    self.data.last_event_time = float(message["ts"]) / 1000
                values = (self.data.open_interest, self.data.funding_rate, self.data.volume)
                if any(value is not None and not isfinite(value) for value in values):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                self._invalid("Malformed ticker payload")

    async def run(self) -> None:

        if websockets is None:
            raise RuntimeError(
                "The optional 'websockets' dependency is required for live feeds"
            )

        self.running = True

        print(
            "Connecting to Bybit public WebSocket..."
        )

        print(
            f"Symbol: {self.symbol}"
        )

        while self.running:

            try:

                async with websockets.connect(
                    BYBIT_PUBLIC_WS,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:

                    self._reset_state()

                    await websocket.send(
                        json.dumps(
                            self._subscription_message()
                        )
                    )

                    print(
                        "Connected to Bybit."
                    )

                    print(
                        "Order book + trades subscribed."
                    )

                    async for raw_message in websocket:

                        if not self.running:
                            break

                        message = json.loads(
                            raw_message
                        )

                        self._process_message(
                            message
                        )

            except asyncio.CancelledError:

                raise

            except Exception as exc:

                if not self.running:
                    break

                print()
                print(
                    f"WebSocket error: {exc}"
                )

                print(
                    "Reconnecting in 3 seconds..."
                )

                await asyncio.sleep(3)

    def stop(self):
        self.running = False


async def main():

    feed = BybitPublicFeed(
        symbol="BTCUSDT",
        orderbook_depth=50,
    )

    try:

        await feed.run()

    except KeyboardInterrupt:

        print()
        print(
            "Market feed stopped."
        )

        feed.stop()


if __name__ == "__main__":
    asyncio.run(main())

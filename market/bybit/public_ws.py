import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import websockets


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
    last_update: float = 0.0

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

    def _subscription_message(self):

        return {
            "op": "subscribe",
            "args": [
                f"orderbook.{self.orderbook_depth}.{self.symbol}",
                f"publicTrade.{self.symbol}",
            ],
        }

    def _apply_orderbook(
        self,
        message: dict[str, Any],
    ) -> None:

        data = message.get("data")

        if not data:
            return

        # -----------------------------------------
        # INITIAL SNAPSHOT
        # -----------------------------------------

        if message.get("type") == "snapshot":

            self.data.bids.clear()
            self.data.asks.clear()

            for price, quantity in data.get(
                "b",
                [],
            ):

                price = float(price)
                quantity = float(quantity)

                if quantity > 0:
                    self.data.bids[
                        price
                    ] = quantity

            for price, quantity in data.get(
                "a",
                [],
            ):

                price = float(price)
                quantity = float(quantity)

                if quantity > 0:
                    self.data.asks[
                        price
                    ] = quantity

        # -----------------------------------------
        # DELTA UPDATE
        # -----------------------------------------

        else:

            for price, quantity in data.get(
                "b",
                [],
            ):

                price = float(price)
                quantity = float(quantity)

                if quantity == 0:
                    self.data.bids.pop(
                        price,
                        None,
                    )
                else:
                    self.data.bids[
                        price
                    ] = quantity

            for price, quantity in data.get(
                "a",
                [],
            ):

                price = float(price)
                quantity = float(quantity)

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

        best_bid = self.data.sorted_bids(1)

        if best_bid:
            self.data.price = best_bid[0][0]

        self.data.last_update = time.time()

    def _process_trade(
        self,
        trade: dict[str, Any],
    ) -> None:

        trade_id = str(
            trade.get(
                "i",
                f"{trade.get('T')}-{self._trade_sequence}",
            )
        )

        self._trade_sequence += 1

        # Avoid duplicate trade IDs.
        if trade_id == self.data.last_trade_id:
            return

        self.data.last_trade_id = trade_id

        timestamp_ms = int(
            trade.get(
                "T",
                time.time() * 1000,
            )
        )

        record = {
            "id": trade_id,
            "timestamp": timestamp_ms,
            "price": float(trade["p"]),
            "quantity": float(trade["v"]),
            "side": str(
                trade["S"]
            ).upper(),
        }

        self.data.price = record["price"]

        self.data.trades.append(record)

        # Keep bounded memory.
        self.data.trades = self.data.trades[-5000:]

        self.data.last_update = time.time()

    def _process_message(
        self,
        message: dict[str, Any],
    ) -> None:

        topic = message.get(
            "topic",
            "",
        )

        data = message.get("data")

        if not data:
            return

        if topic.startswith(
            "orderbook."
        ):

            self._apply_orderbook(
                message
            )

        elif topic.startswith(
            "publicTrade."
        ):

            if isinstance(data, list):

                for trade in data:
                    self._process_trade(
                        trade
                    )

    async def run(self) -> None:

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

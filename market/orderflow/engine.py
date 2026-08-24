from dataclasses import dataclass
from typing import Any


@dataclass
class OrderFlowSnapshot:
    buy_volume: float
    sell_volume: float
    delta: float
    cumulative_delta: float
    buy_sell_ratio: float
    orderbook_imbalance: float
    bias: str
    aggression: str
    absorption: bool


class OrderFlowEngine:

    def __init__(self):
        self.cumulative_delta = 0.0

    def analyze(
        self,
        trades: list[dict[str, Any]],
        orderbook_imbalance: float = 0.0,
    ) -> OrderFlowSnapshot:

        buy_volume = 0.0
        sell_volume = 0.0

        for trade in trades:

            quantity = float(
                trade.get("quantity", 0.0)
            )

            side = str(
                trade.get("side", "")
            ).upper()

            if side == "BUY":
                buy_volume += quantity

            elif side == "SELL":
                sell_volume += quantity

        delta = buy_volume - sell_volume

        self.cumulative_delta += delta

        if sell_volume > 0:
            ratio = buy_volume / sell_volume
        else:
            ratio = float("inf") if buy_volume > 0 else 0.0

        if delta > 0:
            bias = "bullish"
        elif delta < 0:
            bias = "bearish"
        else:
            bias = "neutral"

        total = buy_volume + sell_volume

        if total == 0:
            aggression = "none"
        else:

            delta_ratio = abs(delta) / total

            if delta_ratio >= 0.50:
                aggression = "strong"
            elif delta_ratio >= 0.20:
                aggression = "moderate"
            else:
                aggression = "weak"

        absorption = (
            aggression == "strong"
            and abs(orderbook_imbalance) < 0.10
        )

        return OrderFlowSnapshot(
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
            cumulative_delta=self.cumulative_delta,
            buy_sell_ratio=ratio,
            orderbook_imbalance=orderbook_imbalance,
            bias=bias,
            aggression=aggression,
            absorption=absorption,
        )

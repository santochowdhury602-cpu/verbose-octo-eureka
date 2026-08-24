from dataclasses import dataclass
from math import isfinite
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
        self._trades: dict[str, tuple[float, str, float]] = {}

    @staticmethod
    def _trade_id(trade: dict[str, Any]) -> str:
        value = trade.get("id")
        if value is not None and str(value):
            return str(value)
        return "|".join(
            str(trade.get(key, ""))
            for key in ("timestamp", "price", "quantity", "side")
        )

    def _remember(self, trade: dict[str, Any]) -> str | None:
        trade_id = self._trade_id(trade)
        timestamp = float(trade.get("timestamp", 0.0))
        quantity = float(trade.get("quantity", 0.0))
        side = str(trade.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            return None
        if not isfinite(timestamp) or not isfinite(quantity) or quantity < 0:
            return None
        self._trades.setdefault(trade_id, (timestamp, side, quantity))
        return trade_id

    def analyze(
        self,
        trades: list[dict[str, Any]],
        orderbook_imbalance: float = 0.0,
    ) -> OrderFlowSnapshot:

        current_ids = {
            trade_id
            for trade in trades
            for trade_id in [self._remember(trade)]
            if trade_id is not None
        }

        buy_volume = 0.0
        sell_volume = 0.0

        for trade_id in sorted(current_ids):
            _, side, quantity = self._trades[trade_id]

            if side == "BUY":
                buy_volume += quantity

            elif side == "SELL":
                sell_volume += quantity

        delta = buy_volume - sell_volume

        cumulative_delta = sum(
            quantity if side == "BUY" else -quantity
            for _, side, quantity in sorted(
                self._trades.values(),
                key=lambda item: (item[0], item[1], item[2]),
            )
        )

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
            cumulative_delta=cumulative_delta,
            buy_sell_ratio=ratio,
            orderbook_imbalance=orderbook_imbalance,
            bias=bias,
            aggression=aggression,
            absorption=absorption,
        )

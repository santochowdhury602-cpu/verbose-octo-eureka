from collections import deque
from dataclasses import dataclass
from time import time


@dataclass
class RollingFlow:
    seconds: int
    buy_volume: float
    sell_volume: float
    delta: float
    buy_ratio: float


class RollingOrderFlow:

    def __init__(self, windows=(5, 15, 30, 60, 300)):
        self.windows = windows
        self.trades = deque(maxlen=10000)

    def add_trade(
        self,
        timestamp: float,
        side: str,
        quantity: float,
    ) -> None:

        self.trades.append(
            (
                timestamp,
                side.upper(),
                float(quantity),
            )
        )

    def calculate(self, seconds: int) -> RollingFlow:

        cutoff = time() - seconds

        buy = 0.0
        sell = 0.0

        for timestamp, side, quantity in reversed(self.trades):

            if timestamp < cutoff:
                break

            if side == "BUY":
                buy += quantity
            elif side == "SELL":
                sell += quantity

        total = buy + sell

        ratio = buy / total if total else 0.0

        return RollingFlow(
            seconds=seconds,
            buy_volume=buy,
            sell_volume=sell,
            delta=buy - sell,
            buy_ratio=ratio,
        )

    def snapshot(self) -> dict[int, RollingFlow]:

        return {
            window: self.calculate(window)
            for window in self.windows
        }

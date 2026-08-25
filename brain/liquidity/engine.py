
from __future__ import annotations

from dataclasses import dataclass

from typing import Any

@dataclass(frozen=True)

class LiquidityPool:

    kind: str

    price: float

    first_index: int

    last_index: int

    touches: int

    tolerance: float

    def to_dict(self) -> dict[str, Any]:

        return {

            "kind": self.kind,

            "price": self.price,

            "first_index": self.first_index,

            "last_index": self.last_index,

            "touches": self.touches,

            "tolerance": self.tolerance,

        }

@dataclass(frozen=True)

class LiquiditySweep:

    direction: str

    pool_kind: str

    level: float

    sweep_price: float

    close_price: float

    index: int

    wick_size: float

    displacement: bool

    def to_dict(self) -> dict[str, Any]:

        return {

            "direction": self.direction,

            "pool_kind": self.pool_kind,

            "level": self.level,

            "sweep_price": self.sweep_price,

            "close_price": self.close_price,

            "index": self.index,

            "wick_size": self.wick_size,

            "displacement": self.displacement,

        }

@dataclass

class LiquidityResult:

    buy_side_pools: list[LiquidityPool]

    sell_side_pools: list[LiquidityPool]

    sweeps: list[LiquiditySweep]

    latest_sweep: LiquiditySweep | None

    bias: str

    confidence: float

    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:

        return {

            "buy_side_pools": [

                x.to_dict() for x in self.buy_side_pools

            ],

            "sell_side_pools": [

                x.to_dict() for x in self.sell_side_pools

            ],

            "sweeps": [

                x.to_dict() for x in self.sweeps

            ],

            "latest_sweep": (

                self.latest_sweep.to_dict()

                if self.latest_sweep

                else None

            ),

            "bias": self.bias,

            "confidence": self.confidence,

            "reasons": self.reasons,

        }

class LiquidityEngine:

    """

    Detects:

    - equal highs

    - equal lows

    - buy-side liquidity

    - sell-side liquidity

    - liquidity sweeps

    - post-sweep displacement

    This module is deliberately independent of exchange/API code.

    """

    def __init__(

        self,

        tolerance_pct: float = 0.0015,

        min_touches: int = 2,

        displacement_pct: float = 0.001,

    ) -> None:

        if tolerance_pct <= 0:

            raise ValueError(

                "tolerance_pct must be positive"

            )

        if min_touches < 2:

            raise ValueError(

                "min_touches must be >= 2"

            )

        if displacement_pct < 0:

            raise ValueError(

                "displacement_pct cannot be negative"

            )

        self.tolerance_pct = tolerance_pct

        self.min_touches = min_touches

        self.displacement_pct = displacement_pct

    # =========================================================

    # PRICE HELPERS

    # =========================================================

    def _high(self, candle: dict[str, Any]) -> float:

        return float(candle["high"])

    def _low(self, candle: dict[str, Any]) -> float:

        return float(candle["low"])

    def _close(self, candle: dict[str, Any]) -> float:

        return float(candle["close"])

    def _open(self, candle: dict[str, Any]) -> float:

        return float(candle.get("open", candle["close"]))

    def _near(

        self,

        a: float,

        b: float,

    ) -> bool:

        reference = max(abs(a), abs(b), 1e-12)

        return (

            abs(a - b) / reference

            <= self.tolerance_pct

        )

    # =========================================================

    # EQUAL HIGH / LOW DETECTION

    # =========================================================

    def detect_pools(

        self,

        candles: list[dict[str, Any]],

    ) -> tuple[

        list[LiquidityPool],

        list[LiquidityPool],

    ]:

        high_groups: list[list[tuple[int, float]]] = []

        low_groups: list[list[tuple[int, float]]] = []

        for index, candle in enumerate(candles):

            high = self._high(candle)

            low = self._low(candle)

            matched_high = False

            for group in high_groups:

                reference = group[0][1]

                if self._near(high, reference):

                    group.append((index, high))

                    matched_high = True

                    break

            if not matched_high:

                high_groups.append(

                    [(index, high)]

                )

            matched_low = False

            for group in low_groups:

                reference = group[0][1]

                if self._near(low, reference):

                    group.append((index, low))

                    matched_low = True

                    break

            if not matched_low:

                low_groups.append(

                    [(index, low)]

                )

        buy_side: list[LiquidityPool] = []

        sell_side: list[LiquidityPool] = []

        for group in high_groups:

            if len(group) < self.min_touches:

                continue

            prices = [

                price for _, price in group

            ]

            level = sum(prices) / len(prices)

            buy_side.append(

                LiquidityPool(

                    kind="BUY_SIDE",

                    price=level,

                    first_index=group[0][0],

                    last_index=group[-1][0],

                    touches=len(group),

                    tolerance=self.tolerance_pct,

                )

            )

        for group in low_groups:

            if len(group) < self.min_touches:

                continue

            prices = [

                price for _, price in group

            ]

            level = sum(prices) / len(prices)

            sell_side.append(

                LiquidityPool(

                    kind="SELL_SIDE",

                    price=level,

                    first_index=group[0][0],

                    last_index=group[-1][0],

                    touches=len(group),

                    tolerance=self.tolerance_pct,

                )

            )

        return buy_side, sell_side

    # =========================================================

    # SWEEP DETECTION

    # =========================================================

    def _bullish_sweep(

        self,

        candle: dict[str, Any],

        pool: LiquidityPool,

        index: int,

        next_candle: dict[str, Any] | None,

    ) -> LiquiditySweep | None:

        low = self._low(candle)

        close = self._close(candle)

        # Sell-side liquidity sits below price.

        # A bullish sweep trades below the level

        # and closes back above it.

        if low >= pool.price:

            return None

        if close <= pool.price:

            return None

        wick_size = pool.price - low

        displacement = False

        if next_candle is not None:

            next_close = self._close(

                next_candle

            )

            displacement = (

                next_close

                > close

                * (1 + self.displacement_pct)

            )

        return LiquiditySweep(

            direction="BULLISH",

            pool_kind="SELL_SIDE",

            level=pool.price,

            sweep_price=low,

            close_price=close,

            index=index,

            wick_size=wick_size,

            displacement=displacement,

        )

    def _bearish_sweep(

        self,

        candle: dict[str, Any],

        pool: LiquidityPool,

        index: int,

        next_candle: dict[str, Any] | None,

    ) -> LiquiditySweep | None:

        high = self._high(candle)

        close = self._close(candle)

        # Buy-side liquidity sits above price.

        # A bearish sweep trades above the level

        # and closes back below it.

        if high <= pool.price:

            return None

        if close >= pool.price:

            return None

        wick_size = high - pool.price

        displacement = False

        if next_candle is not None:

            next_close = self._close(

                next_candle

            )

            displacement = (

                next_close

                < close

                * (1 - self.displacement_pct)

            )

        return LiquiditySweep(

            direction="BEARISH",

            pool_kind="BUY_SIDE",

            level=pool.price,

            sweep_price=high,

            close_price=close,

            index=index,

            wick_size=wick_size,

            displacement=displacement,

        )

    def detect_sweeps(

        self,

        candles: list[dict[str, Any]],

        buy_side: list[LiquidityPool],

        sell_side: list[LiquidityPool],

    ) -> list[LiquiditySweep]:

        sweeps: list[LiquiditySweep] = []

        for index, candle in enumerate(candles):

            next_candle = (

                candles[index + 1]

                if index + 1 < len(candles)

                else None

            )

            for pool in sell_side:

                if index <= pool.last_index:

                    continue

                sweep = self._bullish_sweep(

                    candle,

                    pool,

                    index,

                    next_candle,

                )

                if sweep is not None:

                    sweeps.append(sweep)

            for pool in buy_side:

                if index <= pool.last_index:

                    continue

                sweep = self._bearish_sweep(

                    candle,

                    pool,

                    index,

                    next_candle,

                )

                if sweep is not None:

                    sweeps.append(sweep)

        sweeps.sort(

            key=lambda x: x.index

        )

        return sweeps

    # =========================================================

    # MAIN ANALYSIS

    # =========================================================

    def analyze(

        self,

        candles: list[dict[str, Any]],
        as_of: float | None = None,

    ) -> LiquidityResult:

        if as_of is not None:
            candles = [
                candle for candle in candles
                if candle.get("event_time", candle.get("timestamp")) is None
                or float(candle.get("event_time", candle.get("timestamp"))) <= as_of
            ]

        if not candles:

            return LiquidityResult(

                buy_side_pools=[],

                sell_side_pools=[],

                sweeps=[],

                latest_sweep=None,

                bias="WAIT",

                confidence=0.0,

                reasons=[],

            )

        buy_side, sell_side = (

            self.detect_pools(candles)

        )

        sweeps = self.detect_sweeps(

            candles,

            buy_side,

            sell_side,

        )

        latest = (

            sweeps[-1]

            if sweeps

            else None

        )

        reasons: list[str] = []

        if buy_side:

            reasons.append(

                f"{len(buy_side)} buy-side liquidity pool(s)"

            )

        if sell_side:

            reasons.append(

                f"{len(sell_side)} sell-side liquidity pool(s)"

            )

        confidence = 0.0

        bias = "WAIT"

        if latest is not None:

            if latest.direction == "BULLISH":

                bias = "LONG"

                confidence = 70.0

                reasons.append(

                    "Bullish sell-side liquidity sweep"

                )

            elif latest.direction == "BEARISH":

                bias = "SHORT"

                confidence = 70.0

                reasons.append(

                    "Bearish buy-side liquidity sweep"

                )

            if latest.displacement:

                confidence += 20.0

                reasons.append(

                    "Post-sweep displacement confirmed"

                )

            else:

                reasons.append(

                    "Sweep detected without displacement confirmation"

                )

        confidence = min(

            100.0,

            confidence,

        )

        return LiquidityResult(

            buy_side_pools=buy_side,

            sell_side_pools=sell_side,

            sweeps=sweeps,

            latest_sweep=latest,

            bias=bias,

            confidence=confidence,

            reasons=reasons,

        )


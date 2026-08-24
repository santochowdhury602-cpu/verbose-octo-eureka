from dataclasses import dataclass
from typing import Any

from .engine import MarketStructureEngine


@dataclass
class MTFStructureResult:
    bias: str
    aligned: bool

    timeframes: dict[str, dict[str, Any]]

    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bias": self.bias,
            "aligned": self.aligned,
            "timeframes": self.timeframes,
            "reasons": self.reasons,
        }


class MultiTimeframeStructure:

    def __init__(
        self,
        swing_strength: int = 2,
    ):

        self.engine = MarketStructureEngine(
            swing_strength=swing_strength
        )

    def analyze(
        self,
        candles_by_timeframe: dict[
            str,
            list[dict[str, Any]]
        ],
    ) -> MTFStructureResult:

        results: dict[
            str,
            dict[str, Any]
        ] = {}

        bullish = 0
        bearish = 0

        reasons: list[str] = []

        for timeframe, candles in (
            candles_by_timeframe.items()
        ):

            result = self.engine.analyze(
                candles
            )

            data = result.to_dict()

            results[
                timeframe
            ] = data

            if result.bias == "LONG":

                bullish += 1

            elif result.bias == "SHORT":

                bearish += 1

        if bullish > bearish:

            bias = "LONG"

        elif bearish > bullish:

            bias = "SHORT"

        else:

            bias = "WAIT"

        active = [
            x for x in results.values()
            if x.get("bias") in {
                "LONG",
                "SHORT",
            }
        ]

        aligned = False

        if active:

            active_biases = {
                x["bias"]
                for x in active
            }

            aligned = (
                len(active_biases) == 1
            )

        if aligned:

            reasons.append(
                f"Multi-timeframe structure aligned {bias}"
            )

        else:

            reasons.append(
                "Multi-timeframe structure not fully aligned"
            )

        return MTFStructureResult(
            bias=bias,
            aligned=aligned,
            timeframes=results,
            reasons=reasons,
        )

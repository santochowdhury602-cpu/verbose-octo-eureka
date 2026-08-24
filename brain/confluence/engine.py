from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Signal:
    name: str
    direction: str
    score: float
    active: bool = True
    reason: str = ""

    def __post_init__(self) -> None:
        direction = self.direction.upper()

        if direction not in {
            "BULLISH",
            "BEARISH",
            "NEUTRAL",
        }:
            raise ValueError(
                f"Invalid direction: {self.direction}"
            )

        if self.score < 0:
            raise ValueError(
                "Signal score cannot be negative"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "score": self.score,
            "active": self.active,
            "reason": self.reason,
        }


@dataclass
class ConfluenceResult:
    score: float
    bullish_score: float
    bearish_score: float

    bias: str
    quality: str
    status: str

    signals: list[Signal] = field(
        default_factory=list
    )

    reasons: list[str] = field(
        default_factory=list
    )

    conflicts: list[str] = field(
        default_factory=list
    )
    @property
    def approved(self) -> bool:
        return self.status == "TRADE_CANDIDATE"

    @property
    def blockers(self) -> list[str]:
        return list(self.conflicts) if not self.approved else []

    @property
    def components(self) -> dict[str, float]:
        return {
            signal.name: signal.score
            for signal in self.signals
            if signal.active
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "bullish_score": self.bullish_score,
            "bearish_score": self.bearish_score,
            "bias": self.bias,
            "quality": self.quality,
            "status": self.status,
            "signals": [
                x.to_dict()
                for x in self.signals
            ],
            "reasons": self.reasons,
            "conflicts": self.conflicts,
        }


class ConfluenceEngine:
    """
    APEX Stage 7.

    Converts independent market signals into one
    normalized confluence decision.

    This module does NOT place trades.
    """

    DEFAULT_WEIGHTS = {
        "structure": 20.0,
        "liquidity": 25.0,
        "displacement": 20.0,
        "fvg": 15.0,
        "orderflow": 20.0,
    }

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        minimum_score: float = 60.0,
        strong_score: float = 80.0,
    ) -> None:

        self.weights = dict(
            self.DEFAULT_WEIGHTS
        )

        if weights:
            self.weights.update(weights)

        if minimum_score < 0:
            raise ValueError(
                "minimum_score must be >= 0"
            )

        if strong_score < minimum_score:
            raise ValueError(
                "strong_score must be >= minimum_score"
            )

        self.minimum_score = minimum_score
        self.strong_score = strong_score

    # =========================================================
    # SIGNAL BUILDERS
    # =========================================================

    def _make_signal(
        self,
        name: str,
        direction: str,
        weight_key: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return Signal(
            name=name,
            direction=direction.upper(),
            score=self.weights.get(
                weight_key,
                0.0,
            ),
            active=active,
            reason=reason,
        )

    def structure(
        self,
        direction: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return self._make_signal(
            "Market Structure",
            direction,
            "structure",
            active,
            reason,
        )

    def liquidity(
        self,
        direction: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return self._make_signal(
            "Liquidity Sweep",
            direction,
            "liquidity",
            active,
            reason,
        )

    def displacement(
        self,
        direction: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return self._make_signal(
            "Displacement",
            direction,
            "displacement",
            active,
            reason,
        )

    def fvg(
        self,
        direction: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return self._make_signal(
            "Fair Value Gap",
            direction,
            "fvg",
            active,
            reason,
        )

    def orderflow(
        self,
        direction: str,
        active: bool = True,
        reason: str = "",
    ) -> Signal:

        return self._make_signal(
            "Order Flow",
            direction,
            "orderflow",
            active,
            reason,
        )

    # =========================================================
    # ANALYSIS
    # =========================================================

    def analyze(
        self,
        signals: list[Signal],
    ) -> ConfluenceResult:

        active = [
            x for x in signals
            if x.active
        ]

        bullish_score = sum(
            x.score
            for x in active
            if x.direction == "BULLISH"
        )

        bearish_score = sum(
            x.score
            for x in active
            if x.direction == "BEARISH"
        )

        total_possible = sum(
            x.score
            for x in active
            if x.direction != "NEUTRAL"
        )

        if total_possible <= 0:

            return ConfluenceResult(
                score=0.0,
                bullish_score=0.0,
                bearish_score=0.0,
                bias="WAIT",
                quality="NONE",
                status="NO_SIGNAL",
                signals=signals,
                reasons=[],
                conflicts=[],
            )

        conflicts: list[str] = []

        bullish = [
            x for x in active
            if x.direction == "BULLISH"
        ]

        bearish = [
            x for x in active
            if x.direction == "BEARISH"
        ]

        if bullish and bearish:

            conflicts.append(
                "Bullish and bearish signals are conflicting"
            )

        # A small difference between opposing signals
        # is not sufficient to establish directional bias.
        #
        # This prevents a single 25-point bearish signal
        # from overriding a 20-point bullish signal.
        conflict_margin = 15.0

        if (
            bullish_score > bearish_score
            and (
                bullish_score - bearish_score
                >= conflict_margin
            )
        ):

            bias = "LONG"
            score = bullish_score

        elif (
            bearish_score > bullish_score
            and (
                bearish_score - bullish_score
                >= conflict_margin
            )
        ):

            bias = "SHORT"
            score = bearish_score

        else:

            bias = "WAIT"
            score = 0.0

        # Normalize to 0–100.
        score = min(
            100.0,
            max(
                0.0,
                score,
            ),
        )

        if bias == "WAIT":

            quality = "NONE"
            status = "NO_SIGNAL"

        elif score >= self.strong_score:

            quality = "A+"
            status = "TRADE_CANDIDATE"

        elif score >= self.minimum_score:

            quality = "B"
            status = "TRADE_CANDIDATE"

        else:

            quality = "C"
            status = "FILTERED"

        # Conflicting signals should never become
        # a strong candidate merely because one side
        # narrowly wins.
        if conflicts:

            dominance = abs(
                bullish_score
                - bearish_score
            )

            if dominance < 15:

                status = "CONFLICT"
                quality = "NONE"

                if score >= self.minimum_score:
                    score = dominance

        reasons: list[str] = []

        for signal in active:

            if signal.reason:

                reasons.append(
                    f"{signal.name}: "
                    f"{signal.reason}"
                )

            else:

                reasons.append(
                    f"{signal.name}: "
                    f"{signal.direction}"
                )

        if status == "TRADE_CANDIDATE":

            reasons.append(
                f"Confluence score {score:.1f}/100 "
                f"meets minimum threshold"
            )

        elif status == "FILTERED":

            reasons.append(
                f"Confluence score {score:.1f}/100 "
                f"below minimum threshold"
            )

        elif status == "CONFLICT":

            reasons.append(
                "Signal conflict prevents "
                "high-confidence setup"
            )

        return ConfluenceResult(
            score=round(score, 2),
            bullish_score=round(
                bullish_score,
                2,
            ),
            bearish_score=round(
                bearish_score,
                2,
            ),
            bias=bias,
            quality=quality,
            status=status,
            signals=signals,
            reasons=reasons,
            conflicts=conflicts,
        )

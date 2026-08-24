from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DecisionLevels:
    entry: float | None = None
    stop_loss: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None


@dataclass
class BrainDecision:
    action: str
    confidence: float
    levels: DecisionLevels
    reasons: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_trade(self) -> bool:
        return self.action in {"LONG", "SHORT"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "levels": {
                "entry": self.levels.entry,
                "stop_loss": self.levels.stop_loss,
                "tp1": self.levels.tp1,
                "tp2": self.levels.tp2,
                "tp3": self.levels.tp3,
            },
            "reasons": list(self.reasons),
            "invalidation": list(self.invalidation),
            "metadata": dict(self.metadata),
        }


class APEXDecisionBrain:
    """
    Deterministic decision layer.

    It does not place orders.
    It converts already-computed market evidence
    into LONG / SHORT / WAIT.
    """

    def __init__(
        self,
        minimum_confidence: float = 60.0,
    ) -> None:
        self.minimum_confidence = minimum_confidence

    def analyze(
        self,
        context: Any,
    ) -> BrainDecision:

        bias = str(
            getattr(context, "bias", "WAIT")
        ).upper()

        score = float(
            getattr(context, "score", 0.0)
        )

        price = float(
            getattr(
                context,
                "current_price",
                0.0,
            )
        )

        if bias not in {"LONG", "SHORT"}:
            return BrainDecision(
                action="WAIT",
                confidence=min(score, 100.0),
                levels=DecisionLevels(),
                reasons=[
                    "Market bias is not directional"
                ],
                invalidation=[
                    "Directional confluence required"
                ],
            )

        if score < self.minimum_confidence:
            return BrainDecision(
                action="WAIT",
                confidence=score,
                levels=DecisionLevels(),
                reasons=[
                    f"Confluence score {score:.1f} "
                    f"is below required "
                    f"{self.minimum_confidence:.1f}"
                ],
                invalidation=[
                    "Confidence threshold not met"
                ],
            )

        reasons = [
            f"Confluence bias: {bias}",
            f"Confluence score: {score:.1f}",
        ]

        if bias == "LONG":
            action = "LONG"
        else:
            action = "SHORT"

        return BrainDecision(
            action=action,
            confidence=min(score, 100.0),
            levels=DecisionLevels(
                entry=price,
            ),
            reasons=reasons,
            invalidation=[
                "Market structure invalidation",
                "Liquidity thesis invalidation",
                "Risk gate rejection",
            ],
            metadata={
                "engine": "APEXDecisionBrain",
            },
        )

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningResult:
    bias: str
    confidence: float
    setup_valid: bool

    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ApexReasoner:
    """
    Deterministic APEX reasoning layer.

    This is deliberately independent of any LLM.
    The LLM can later provide advisory reasoning,
    but it cannot override this layer or the RiskGate.
    """

    def evaluate(
        self,
        market: dict[str, Any],
    ) -> ReasoningResult:

        reasons: list[str] = []
        warnings: list[str] = []

        score_long = 0.0
        score_short = 0.0

        # ==========================================
        # MARKET STRUCTURE
        # ==========================================

        structure = market.get(
            "structure",
            {},
        )

        structure_bias = str(
            structure.get(
                "bias",
                "",
            )
        ).lower()

        if structure_bias == "bullish":

            score_long += 20

            reasons.append(
                "Bullish market structure"
            )

        elif structure_bias == "bearish":

            score_short += 20

            reasons.append(
                "Bearish market structure"
            )

        # ==========================================
        # LIQUIDITY
        # ==========================================

        liquidity = market.get(
            "liquidity",
            {},
        )

        sweep = str(
            liquidity.get(
                "sweep",
                "",
            )
        ).lower()

        if sweep == "sell_side":

            score_long += 20

            reasons.append(
                "Sell-side liquidity sweep detected"
            )

        elif sweep == "buy_side":

            score_short += 20

            reasons.append(
                "Buy-side liquidity sweep detected"
            )

        # ==========================================
        # ORDER FLOW
        # ==========================================

        order_flow = market.get(
            "order_flow",
            {},
        )

        flow_bias = str(
            order_flow.get(
                "bias",
                "",
            )
        ).lower()

        aggression = str(
            order_flow.get(
                "aggression",
                "",
            )
        ).lower()

        delta = float(
            order_flow.get(
                "delta",
                0.0,
            )
        )

        if flow_bias == "bullish":

            score_long += 20

            reasons.append(
                "Bullish order flow"
            )

        elif flow_bias == "bearish":

            score_short += 20

            reasons.append(
                "Bearish order flow"
            )

        if aggression == "strong":

            if delta > 0:

                score_long += 10

                reasons.append(
                    "Strong buy aggression"
                )

            elif delta < 0:

                score_short += 10

                reasons.append(
                    "Strong sell aggression"
                )

        # ==========================================
        # ORDER BOOK
        # ==========================================

        orderbook = market.get(
            "orderbook",
            {},
        )

        imbalance = float(
            orderbook.get(
                "imbalance",
                0.0,
            )
        )

        if imbalance >= 0.20:

            score_long += 10

            reasons.append(
                "Bid-side order-book imbalance"
            )

        elif imbalance <= -0.20:

            score_short += 10

            reasons.append(
                "Ask-side order-book imbalance"
            )

        # ==========================================
        # OPEN INTEREST
        # ==========================================

        open_interest = market.get(
            "open_interest",
            {},
        )

        oi_change = float(
            open_interest.get(
                "change_pct",
                0.0,
            )
        )

        if oi_change >= 3.0:

            reasons.append(
                f"Open interest expanding "
                f"(+{oi_change:.2f}%)"
            )

            if score_long > score_short:

                score_long += 10

            elif score_short > score_long:

                score_short += 10

        elif oi_change <= -3.0:

            warnings.append(
                f"Open interest contracting "
                f"({oi_change:.2f}%)"
            )

        # ==========================================
        # RELATIVE VOLUME
        # ==========================================

        volume = market.get(
            "volume",
            {},
        )

        rvol = float(
            volume.get(
                "rvol",
                0.0,
            )
        )

        if rvol >= 3.0:

            reasons.append(
                f"High relative volume "
                f"({rvol:.2f}x)"
            )

            if score_long > score_short:

                score_long += 10

            elif score_short > score_long:

                score_short += 10

        # ==========================================
        # DETERMINE BIAS
        # ==========================================

        highest_score = max(
            score_long,
            score_short,
        )

        if highest_score == 0:

            return ReasoningResult(
                bias="WAIT",
                confidence=0.0,
                setup_valid=False,
                reasons=reasons,
                warnings=[
                    "Insufficient market confluence"
                ],
            )

        if score_long > score_short:

            bias = "LONG"

            confidence = min(
                score_long,
                100.0,
            )

        elif score_short > score_long:

            bias = "SHORT"

            confidence = min(
                score_short,
                100.0,
            )

        else:

            return ReasoningResult(
                bias="WAIT",
                confidence=0.0,
                setup_valid=False,
                reasons=reasons,
                warnings=[
                    "Long and short signals are balanced"
                ],
            )

        # ==========================================
        # MINIMUM CONFLUENCE
        # ==========================================

        setup_valid = confidence >= 75.0

        if not setup_valid:

            warnings.append(
                "Confluence below 75"
            )

        return ReasoningResult(
            bias=bias,
            confidence=confidence,
            setup_valid=setup_valid,
            reasons=reasons,
            warnings=warnings,
        )

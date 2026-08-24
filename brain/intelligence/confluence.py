from dataclasses import dataclass
from typing import Any


@dataclass
class ConfluenceResult:
    bias: str
    score: float
    approved: bool

    reasons: list[str]
    blockers: list[str]

    components: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bias": self.bias,
            "score": self.score,
            "approved": self.approved,
            "reasons": self.reasons,
            "blockers": self.blockers,
            "components": self.components,
        }


class ConfluenceEngine:

    MIN_SCORE = 75.0

    def evaluate(
        self,
        market: dict[str, Any],
        microstructure: dict[str, Any],
    ) -> ConfluenceResult:

        long_score = 0.0
        short_score = 0.0

        reasons: list[str] = []
        blockers: list[str] = []

        components: dict[str, float] = {}

        # =====================================================
        # MICROSTRUCTURE
        # =====================================================

        micro_bias = str(
            microstructure.get(
                "bias",
                "WAIT",
            )
        ).upper()

        micro_score = float(
            microstructure.get(
                "score",
                0.0,
            ) or 0.0
        )

        # Give microstructure a maximum contribution
        # of 60 points.
        micro_contribution = min(
            60.0,
            micro_score * 0.60,
        )

        components[
            "microstructure"
        ] = micro_contribution

        if micro_bias == "LONG":

            long_score += micro_contribution

        elif micro_bias == "SHORT":

            short_score += micro_contribution

        # =====================================================
        # MARKET STRUCTURE
        # =====================================================

        structure = market.get(
            "structure",
            {},
        ) or {}

        structure_bias = str(
            structure.get(
                "bias",
                "",
            )
        ).upper()

        if structure_bias == "BULLISH":

            long_score += 20

            components["structure"] = 20

            reasons.append(
                "Bullish market structure"
            )

        elif structure_bias == "BEARISH":

            short_score += 20

            components["structure"] = 20

            reasons.append(
                "Bearish market structure"
            )

        else:

            components["structure"] = 0

        # =====================================================
        # OPEN INTEREST
        # =====================================================

        oi = market.get(
            "open_interest",
            {},
        ) or {}

        oi_change = float(
            oi.get(
                "change_pct",
                0.0,
            ) or 0.0
        )

        if oi_change >= 3.0:

            if long_score > short_score:

                long_score += 10

            elif short_score > long_score:

                short_score += 10

            components["oi"] = 10

            reasons.append(
                f"OI expansion +{oi_change:.2f}%"
            )

        else:

            components["oi"] = 0

        # =====================================================
        # RELATIVE VOLUME
        # =====================================================

        volume = market.get(
            "volume",
            {},
        ) or {}

        rvol = float(
            volume.get(
                "rvol",
                0.0,
            ) or 0.0
        )

        if rvol >= 3.0:

            if long_score > short_score:

                long_score += 10

            elif short_score > long_score:

                short_score += 10

            components["rvol"] = 10

            reasons.append(
                f"High relative volume {rvol:.2f}x"
            )

        else:

            components["rvol"] = 0

        # =====================================================
        # FVG
        # =====================================================

        fvg = market.get(
            "fvg",
            {},
        ) or {}

        if fvg.get("active"):

            fvg_bias = str(
                fvg.get(
                    "bias",
                    "",
                )
            ).upper()

            if fvg_bias == "BULLISH":

                long_score += 5
                components["fvg"] = 5

                reasons.append(
                    "Bullish FVG active"
                )

            elif fvg_bias == "BEARISH":

                short_score += 5
                components["fvg"] = 5

                reasons.append(
                    "Bearish FVG active"
                )

        else:

            components["fvg"] = 0

        # =====================================================
        # ORDER BLOCK
        # =====================================================

        order_blocks = market.get(
            "order_blocks",
            {},
        ) or {}

        if order_blocks.get("active"):

            ob_bias = str(
                order_blocks.get(
                    "bias",
                    "",
                )
            ).upper()

            if ob_bias == "BULLISH":

                long_score += 5
                components["order_block"] = 5

                reasons.append(
                    "Bullish order block active"
                )

            elif ob_bias == "BEARISH":

                short_score += 5
                components["order_block"] = 5

                reasons.append(
                    "Bearish order block active"
                )

        else:

            components["order_block"] = 0

        # =====================================================
        # FINAL DECISION
        # =====================================================

        if long_score > short_score:

            bias = "LONG"
            score = min(
                100.0,
                long_score,
            )

        elif short_score > long_score:

            bias = "SHORT"
            score = min(
                100.0,
                short_score,
            )

        else:

            bias = "WAIT"
            score = 0.0

        approved = (
            bias != "WAIT"
            and score >= self.MIN_SCORE
        )

        if not approved:

            blockers.append(
                f"Score below minimum "
                f"{self.MIN_SCORE:.0f}"
            )

        return ConfluenceResult(
            bias=bias,
            score=score,
            approved=approved,
            reasons=reasons,
            blockers=blockers,
            components=components,
        )

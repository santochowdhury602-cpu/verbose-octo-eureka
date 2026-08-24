from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RiskConfig:
    account_size: float = 500.0
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 5.0
    max_concurrent_positions: int = 2
    daily_drawdown_kill_pct: float = 3.0
    minimum_confidence: float = 75.0


@dataclass
class RiskResult:
    approved: bool
    risk_usd: float
    position_size: float
    leverage: float

    reasons: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "risk_usd": self.risk_usd,
            "position_size": self.position_size,
            "leverage": self.leverage,
            "reasons": list(self.reasons),
            "rejection_reasons": list(self.rejection_reasons),
            "metadata": dict(self.metadata),
        }


class RiskGate:

    def __init__(
        self,
        config: RiskConfig | None = None,
    ) -> None:

        self.config = config or RiskConfig()

        # Persistent kill switch.
        self._killed = False

    # =========================================================
    # KILL SWITCH
    # =========================================================

    def kill(self) -> None:
        """Permanently reject new trades until a new gate is created."""
        self._killed = True

    def reset(self) -> None:
        """Reset the in-memory kill switch."""
        self._killed = False

    @property
    def killed(self) -> bool:
        return self._killed

    # =========================================================
    # INTERNAL EVALUATOR
    # =========================================================

    def _evaluate(
        self,
        *,
        action: str,
        confidence: float,
        entry: float,
        stop_loss: float | None,
        leverage: float,
        open_positions: int,
        daily_drawdown_pct: float,
    ) -> RiskResult:

        reasons: list[str] = []
        rejected: list[str] = []

        risk_usd = (
            self.config.account_size
            * self.config.risk_per_trade_pct
            / 100.0
        )

        # -----------------------------------------------------
        # KILL SWITCH
        # -----------------------------------------------------

        if self._killed:
            rejected.append(
                "Risk gate kill switch is active"
            )

        # -----------------------------------------------------
        # ACTION
        # -----------------------------------------------------

        if action not in {"LONG", "SHORT"}:
            rejected.append(
                "Action is not executable"
            )

        # -----------------------------------------------------
        # CONFIDENCE
        # -----------------------------------------------------

        if confidence < self.config.minimum_confidence:
            rejected.append(
                "Confidence below risk threshold"
            )
        else:
            reasons.append(
                "Confidence approved"
            )

        # -----------------------------------------------------
        # ENTRY
        # -----------------------------------------------------

        if entry <= 0:
            rejected.append(
                "Invalid entry price"
            )

        # -----------------------------------------------------
        # STOP LOSS
        # -----------------------------------------------------

        if stop_loss is None:

            rejected.append(
                "Stop-loss is required"
            )

        else:

            if (
                action == "LONG"
                and stop_loss >= entry
            ):
                rejected.append(
                    "LONG stop-loss must be below entry"
                )

            if (
                action == "SHORT"
                and stop_loss <= entry
            ):
                rejected.append(
                    "SHORT stop-loss must be above entry"
                )

            if action in {"LONG", "SHORT"}:
                reasons.append(
                    "Stop-loss geometry approved"
                )

        # -----------------------------------------------------
        # LEVERAGE
        # -----------------------------------------------------

        if leverage <= 0:

            rejected.append(
                "Leverage must be positive"
            )

        elif leverage > self.config.max_leverage:

            rejected.append(
                "Leverage exceeds configured maximum"
            )

        else:

            reasons.append(
                "Leverage approved"
            )

        # -----------------------------------------------------
        # POSITION LIMIT
        # -----------------------------------------------------

        if (
            open_positions
            >= self.config.max_concurrent_positions
        ):

            rejected.append(
                "Position limit reached"
            )

        else:

            reasons.append(
                "Position limit approved"
            )

        # -----------------------------------------------------
        # DAILY DRAWDOWN
        # -----------------------------------------------------

        if (
            daily_drawdown_pct
            >= self.config.daily_drawdown_kill_pct
        ):

            # Latch the kill switch. Once the configured
            # daily drawdown limit is reached, subsequent
            # evaluations remain rejected until reset().
            self.kill()

            rejected.append(
                "Daily drawdown kill switch active"
            )

        else:

            reasons.append(
                "Drawdown approved"
            )

        # -----------------------------------------------------
        # FINAL DECISION
        # -----------------------------------------------------

        approved = len(rejected) == 0

        position_size = 0.0

        if (
            approved
            and stop_loss is not None
            and abs(entry - stop_loss) > 0
        ):

            position_size = (
                risk_usd
                / abs(entry - stop_loss)
            )

        return RiskResult(
            approved=approved,
            risk_usd=risk_usd,
            position_size=position_size,
            leverage=leverage,
            reasons=reasons,
            rejection_reasons=rejected,
            metadata={
                "account_size":
                    self.config.account_size,

                "risk_per_trade_pct":
                    self.config.risk_per_trade_pct,

                "max_leverage":
                    self.config.max_leverage,

                "max_concurrent_positions":
                    self.config.max_concurrent_positions,

                "daily_drawdown_kill_pct":
                    self.config.daily_drawdown_kill_pct,

                "minimum_confidence":
                    self.config.minimum_confidence,

                "killed":
                    self._killed,
            },
        )

    # =========================================================
    # PUBLIC COMPATIBLE API
    # =========================================================

    def evaluate(
        self,
        decision=None,
        *,
        action: str | None = None,
        confidence: float | None = None,
        entry: float | None = None,
        stop_loss: float | None = None,
        leverage: float | None = None,
        open_positions: int | None = None,
        daily_drawdown_pct: float = 0.0,

        # Legacy parameter names.
        current_positions: int | None = None,
        requested_leverage: float | None = None,
    ) -> RiskResult:
        """
        Supports both the original APEX API and the newer API.

        Legacy:

            RiskGate().evaluate(
                decision,
                current_positions=0,
                daily_drawdown_pct=0,
                requested_leverage=5,
            )

        New:

            RiskGate().evaluate(
                action="LONG",
                confidence=80,
                entry=100000,
                stop_loss=99500,
                leverage=5,
                open_positions=0,
                daily_drawdown_pct=0,
            )
        """

        # -----------------------------------------------------
        # LEGACY DECISION OBJECT
        # -----------------------------------------------------

        if decision is not None:

            action = getattr(
                decision,
                "action",
                action,
            )

            confidence = getattr(
                decision,
                "confidence",
                confidence,
            )

            entry = getattr(
                decision,
                "entry",
                entry,
            )

            stop_loss = getattr(
                decision,
                "stop_loss",
                stop_loss,
            )

        # -----------------------------------------------------
        # LEGACY POSITION NAME
        # -----------------------------------------------------

        if open_positions is None:

            if current_positions is not None:
                open_positions = current_positions
            else:
                open_positions = 0

        # -----------------------------------------------------
        # LEGACY LEVERAGE NAME
        # -----------------------------------------------------

        if leverage is None:

            if requested_leverage is not None:
                leverage = requested_leverage
            else:
                leverage = self.config.max_leverage

        # -----------------------------------------------------
        # REQUIRED VALUES
        # -----------------------------------------------------

        if action is None:
            action = "WAIT"

        if confidence is None:
            confidence = 0.0

        if entry is None:
            entry = 0.0

        return self._evaluate(
            action=action,
            confidence=float(confidence),
            entry=float(entry),
            stop_loss=stop_loss,
            leverage=float(leverage),
            open_positions=int(open_positions),
            daily_drawdown_pct=float(
                daily_drawdown_pct
            ),
        )

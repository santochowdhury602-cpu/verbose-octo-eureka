from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from brain.confluence import ConfluenceEngine
from brain.decision import APEXDecisionBrain, BrainDecision
from brain.execution import ExecutionIntent, ExecutionIntentBuilder
from brain.fvg import FVGEngine
from brain.intelligence import MicrostructureEngine
from brain.liquidity import LiquidityEngine
from brain.oi import OIEngine, OISnapshot
from brain.risk import RiskGate, RiskResult
from brain.structure import MarketStructureEngine, MultiTimeframeStructure
from market.orderflow import OrderFlowEngine
from market.indicators import ATRCalculator, VWAPCalculator


@dataclass
class PipelineResult:
    context: Any
    decision: BrainDecision
    risk: RiskResult
    intent: ExecutionIntent | None

    def to_dict(self):
        return {
            "context": self.context.to_dict(),
            "decision": self.decision.to_dict(),
            "risk": self.risk.to_dict(),
            "intent": self.intent.to_dict() if self.intent else None,
        }


class ApexBrainPipeline:
    """One deterministic market-context-to-paper-intent execution path."""

    def __init__(self, risk_gate: RiskGate | None = None) -> None:
        self.structure = MarketStructureEngine(swing_strength=1)
        self.mtf = MultiTimeframeStructure(swing_strength=1)
        self.liquidity = LiquidityEngine()
        self.fvg = FVGEngine()
        self.orderflow = OrderFlowEngine()
        self.atr = ATRCalculator()
        self.oi = OIEngine()
        self.microstructure = MicrostructureEngine()
        self.confluence = ConfluenceEngine()
        self.decision = APEXDecisionBrain()
        self.risk = risk_gate or RiskGate()
        self.intent = ExecutionIntentBuilder()

    @staticmethod
    def _dict(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return value.to_dict() if hasattr(value, "to_dict") else vars(value)

    def run(
        self,
        context,
        *,
        open_positions: int = 0,
        daily_drawdown_pct: float = 0.0,
    ) -> PipelineResult:
        as_of = context.event_time
        candles = [vars(candle) for candle in context.candles]
        structure = self.structure.analyze(candles, as_of=as_of)

        timeframe_candles = context.metadata.get("candles_by_timeframe", {})
        if not timeframe_candles and candles:
            timeframe_candles = {context.price.timeframe: candles}
        mtf = self.mtf.analyze(
            timeframe_candles,
            as_of=as_of,
            timeframe_metadata=context.metadata.get("timeframe_metadata"),
        )

        liquidity = self.liquidity.analyze(candles)
        fvg = self.fvg.analyze(candles, as_of=as_of)
        vwap = VWAPCalculator.calculate(candles, as_of=as_of)
        volatility = self.atr.calculate(candles, as_of=as_of)
        flow = context.orderflow
        if flow is None and context.trades:
            flow = self.orderflow.analyze([vars(trade) for trade in context.trades])
        flow_data = self._dict(flow)
        oi = context.oi
        if oi is None and context.oi_change is not None:
            oi = self.oi.analyze(OISnapshot(
                price_change_pct=context.price.change_pct,
                oi_change_pct=context.oi_change,
                oi_value=context.open_interest,
                volume_ratio=context.price.volume_ratio,
                funding_rate=context.funding,
            ))
        liquidity_data = self._dict(liquidity)
        fvg_data = self._dict(fvg)
        micro = self.microstructure.analyze({
            "order_flow": flow_data,
            "orderbook": {"imbalance": context.metadata.get("orderbook_imbalance", 0.0)},
            "liquidity": {
                "sweep": "sell_side" if liquidity.bias == "LONG" else "buy_side" if liquidity.bias == "SHORT" else "none",
                "sweep_strength": liquidity.confidence / 100.0,
            },
        })

        signals = []
        if structure.bias in {"LONG", "SHORT"}:
            signals.append(self.confluence.structure("BULLISH" if structure.bias == "LONG" else "BEARISH"))
        if liquidity.bias in {"LONG", "SHORT"}:
            signals.append(self.confluence.liquidity("BULLISH" if liquidity.bias == "LONG" else "BEARISH"))
        if fvg.bias in {"LONG", "SHORT"}:
            signals.append(self.confluence.fvg("BULLISH" if fvg.bias == "LONG" else "BEARISH"))
        if flow_data.get("bias") in {"bullish", "bearish"}:
            signals.append(self.confluence.orderflow("BULLISH" if flow_data["bias"] == "bullish" else "BEARISH"))
        confluence = self.confluence.analyze(signals)
        enriched = replace(
            context,
            structure=structure,
            mtf=mtf,
            liquidity=liquidity,
            fvg=fvg,
            orderflow=flow,
            microstructure=micro,
            confluence=confluence,
            oi=oi,
            vwap=vwap,
            volatility=volatility,
        )
        decision = self.decision.analyze(enriched)
        risk = self.risk.evaluate(
            decision=decision,
            open_positions=open_positions,
            daily_drawdown_pct=daily_drawdown_pct,
            data_quality=enriched.data_quality.status,
            exchange_metadata=enriched.exchange_metadata,
        )
        if decision.is_trade and not risk.approved:
            decision = BrainDecision(
                action="WAIT",
                confidence=decision.confidence,
                levels=decision.levels,
                reasons=["Risk gate rejected the setup"],
                invalidation=list(risk.rejection_reasons),
                metadata={
                    "event_time": enriched.event_time,
                    "data_quality": enriched.data_quality.status,
                    "confluence_score": decision.confluence_score,
                },
            )
        intent = None
        if decision.entry is not None and decision.stop_loss is not None:
            intent = self.intent.build(symbol=enriched.symbol, decision=decision, risk=risk)
        return PipelineResult(enriched, decision, risk, intent)


BrainPipeline = ApexBrainPipeline
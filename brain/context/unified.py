from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from brain.confluence import ConfluenceResult
from brain.oi import OIAnalysis


@dataclass(frozen=True)
class PriceContext:
    symbol: str
    price: float

    timeframe: str = "5m"

    change_pct: float = 0.0

    volume: float = 0.0
    volume_ratio: float = 1.0

    atr: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "timeframe": self.timeframe,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "volume_ratio": self.volume_ratio,
            "atr": self.atr,
        }


@dataclass
class MarketContext:
    """
    Unified APEX market state.

    This is the bridge between the individual
    analysis engines and the final APEX Brain.
    """

    price: PriceContext

    confluence: ConfluenceResult

    oi: OIAnalysis

    orderflow: Any | None = None
    liquidity: Any | None = None
    structure: Any | None = None
    fvg: Any | None = None

    timestamp: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def symbol(self) -> str:
        return self.price.symbol

    @property
    def current_price(self) -> float:
        return self.price.price

    @property
    def bias(self) -> str:
        return self.confluence.bias

    @property
    def score(self) -> float:
        return self.confluence.score

    @property
    def regime(self) -> str:
        return self.oi.regime

    @property
    def oi_direction(self) -> str:
        return self.oi.direction

    @property
    def trade_candidate(self) -> bool:
        return (
            self.confluence.status
            == "TRADE_CANDIDATE"
        )

    def to_dict(self) -> dict[str, Any]:

        def serialize(value: Any) -> Any:

            if value is None:
                return None

            if hasattr(value, "to_dict"):
                return value.to_dict()

            if isinstance(value, dict):
                return {
                    k: serialize(v)
                    for k, v in value.items()
                }

            if isinstance(value, list):
                return [
                    serialize(v)
                    for v in value
                ]

            if hasattr(value, "__dict__"):
                return {
                    k: serialize(v)
                    for k, v in vars(value).items()
                }

            return value

        return {
            "symbol": self.symbol,
            "price": serialize(self.price),
            "confluence": serialize(
                self.confluence
            ),
            "oi": serialize(self.oi),
            "orderflow": serialize(
                self.orderflow
            ),
            "liquidity": serialize(
                self.liquidity
            ),
            "structure": serialize(
                self.structure
            ),
            "fvg": serialize(
                self.fvg
            ),
            "timestamp": self.timestamp,
            "metadata": serialize(
                self.metadata
            ),
        }


class MarketContextBuilder:
    """
    Builder used by the APEX data pipeline.

    Individual engines can be updated independently,
    then the builder produces one immutable snapshot.
    """

    def __init__(
        self,
        symbol: str,
        price: float,
        timeframe: str = "5m",
    ) -> None:

        self._price = PriceContext(
            symbol=symbol,
            price=price,
            timeframe=timeframe,
        )

        self._confluence: ConfluenceResult | None = None
        self._oi: OIAnalysis | None = None

        self._orderflow: Any | None = None
        self._liquidity: Any | None = None
        self._structure: Any | None = None
        self._fvg: Any | None = None

        self._timestamp: float | None = None

        self._metadata: dict[str, Any] = {}

    def set_price(
        self,
        price: float,
        change_pct: float | None = None,
        volume: float | None = None,
        volume_ratio: float | None = None,
        atr: float | None = None,
    ) -> "MarketContextBuilder":

        self._price = PriceContext(
            symbol=self._price.symbol,
            price=price,
            timeframe=self._price.timeframe,
            change_pct=(
                self._price.change_pct
                if change_pct is None
                else change_pct
            ),
            volume=(
                self._price.volume
                if volume is None
                else volume
            ),
            volume_ratio=(
                self._price.volume_ratio
                if volume_ratio is None
                else volume_ratio
            ),
            atr=(
                self._price.atr
                if atr is None
                else atr
            ),
        )

        return self

    def set_confluence(
        self,
        result: ConfluenceResult,
    ) -> "MarketContextBuilder":

        self._confluence = result
        return self

    def set_oi(
        self,
        result: OIAnalysis,
    ) -> "MarketContextBuilder":

        self._oi = result
        return self

    def set_orderflow(
        self,
        result: Any,
    ) -> "MarketContextBuilder":

        self._orderflow = result
        return self

    def set_liquidity(
        self,
        result: Any,
    ) -> "MarketContextBuilder":

        self._liquidity = result
        return self

    def set_structure(
        self,
        result: Any,
    ) -> "MarketContextBuilder":

        self._structure = result
        return self

    def set_fvg(
        self,
        result: Any,
    ) -> "MarketContextBuilder":

        self._fvg = result
        return self

    def set_timestamp(
        self,
        timestamp: float,
    ) -> "MarketContextBuilder":

        self._timestamp = timestamp
        return self

    def add_metadata(
        self,
        key: str,
        value: Any,
    ) -> "MarketContextBuilder":

        self._metadata[key] = value
        return self

    def build(self) -> MarketContext:

        if self._confluence is None:
            raise ValueError(
                "Confluence result is required"
            )

        if self._oi is None:
            raise ValueError(
                "OI analysis is required"
            )

        return MarketContext(
            price=self._price,
            confluence=self._confluence,
            oi=self._oi,
            orderflow=self._orderflow,
            liquidity=self._liquidity,
            structure=self._structure,
            fvg=self._fvg,
            timestamp=self._timestamp,
            metadata=dict(self._metadata),
        )

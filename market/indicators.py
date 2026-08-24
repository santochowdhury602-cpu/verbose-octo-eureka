from __future__ import annotations


class VWAPCalculator:
    @staticmethod
    def calculate(candles, as_of=None):
        total_volume = 0.0
        total_value = 0.0
        for candle in candles:
            timestamp = candle.get("event_time", candle.get("timestamp"))
            if as_of is not None and timestamp is not None and float(timestamp) > as_of:
                continue
            volume = float(candle.get("volume", 0.0))
            if volume < 0:
                raise ValueError("Candle volume cannot be negative")
            if volume == 0:
                continue
            typical = (float(candle["high"]) + float(candle["low"]) + float(candle["close"])) / 3
            total_volume += volume
            total_value += typical * volume
        return total_value / total_volume if total_volume else None


class ATRCalculator:
    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("ATR period must be positive")
        self.period = period

    def calculate(self, candles, as_of=None):
        visible = [
            candle for candle in candles
            if as_of is None
            or candle.get("event_time", candle.get("timestamp")) is None
            or float(candle.get("event_time", candle.get("timestamp"))) <= as_of
        ]
        if len(visible) < self.period + 1:
            return None
        ranges = []
        for previous, current in zip(visible, visible[1:]):
            ranges.append(max(
                float(current["high"]) - float(current["low"]),
                abs(float(current["high"]) - float(previous["close"])),
                abs(float(current["low"]) - float(previous["close"])),
            ))
        return sum(ranges[-self.period:]) / self.period
"""Market candle storage and deterministic, explicitly synthetic sample data."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import math
import random
from typing import Protocol


@dataclass(frozen=True)
class Candle:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    source: str = "SAMPLE — generated demo data"

    def validate(self) -> "Candle":
        try:
            parsed = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Candle timestamp must be ISO-8601.") from exc
        if parsed.tzinfo is None:
            raise ValueError("Candle timestamp must include a timezone.")
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            raise ValueError("Candle values must be finite numbers.")
        if min(self.open, self.high, self.low, self.close) <= 0 or self.volume < 0:
            raise ValueError("Prices must be positive and volume cannot be negative.")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError("Candle high/low values do not contain the open and close.")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


class MarketDataProvider(Protocol):
    def get_candles(self, asset: str, limit: int = 100) -> list[Candle]: ...


SAMPLE_ASSETS = {"EUR/USD": 1.0842, "BTC/USD": 67_250.0, "GOLD": 2_325.0, "NASDAQ": 18_240.0}


class DataEngine:
    """Stores sample candles; no live market connection is present."""

    def __init__(self, asset: str = "EUR/USD", seed: int = 41, count: int = 80):
        if asset not in SAMPLE_ASSETS:
            raise ValueError("Unknown sample asset.")
        self.asset = asset
        self._rng = random.Random(seed)
        self._candles = self._make_history(count)

    def _make_history(self, count: int) -> list[Candle]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        price = SAMPLE_ASSETS[self.asset]
        candles = []
        for index in range(count):
            opening = price
            close = max(0.00001, opening * (1 + self._rng.uniform(-0.0011, 0.0011)))
            spread = abs(close - opening) + opening * self._rng.uniform(0.0001, 0.00045)
            candles.append(Candle((now - timedelta(minutes=count - index)).isoformat(), opening,
                                  max(opening, close) + spread / 2, min(opening, close) - spread / 2,
                                  close, round(self._rng.uniform(80, 900), 2)).validate())
            price = close
        return candles

    def get_candles(self, limit: int = 100) -> list[Candle]:
        return self._candles[-max(1, min(int(limit), 500)):].copy()

    def latest_candle(self) -> Candle:
        return self._candles[-1]

    def latest_price(self) -> float:
        return self.latest_candle().close

    def add_candle(self, candle: Candle) -> Candle:
        candle.validate()
        if self._candles and datetime.fromisoformat(candle.timestamp) <= datetime.fromisoformat(self._candles[-1].timestamp):
            raise ValueError("Candle timestamp must be later than the previous candle.")
        if candle.source != "SAMPLE — generated demo data":
            raise ValueError("This demo accepts sample candles only.")
        self._candles.append(candle)
        self._candles = self._candles[-500:]
        return candle

    def advance_sample(self) -> Candle:
        """Advance the latest sample candle with deterministic seeded movement."""
        previous = self.latest_candle()
        opening = previous.open
        close = max(0.00001, previous.close * (1 + self._rng.uniform(-0.00035, 0.00035)))
        candle = Candle(datetime.now(timezone.utc).isoformat(), opening,
                        max(previous.high, opening, close), min(previous.low, opening, close), close,
                        previous.volume + self._rng.uniform(1, 20))
        # Updates in-place within the current synthetic candle; timestamps are not a history feed.
        self._candles[-1] = candle.validate()
        return candle

    def select_asset(self, asset: str) -> None:
        replacement = DataEngine(asset=asset, seed=41, count=80)
        self.asset, self._rng, self._candles = replacement.asset, replacement._rng, replacement._candles

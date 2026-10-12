"""Validated configuration for the demo-only trading application."""

from dataclasses import dataclass
import math
from typing import Any

AGENT_NAME = "Trade with Tahir AI Bot"
VERSION = "3.2.0-demo"
DEBUG = False
DEFAULT_SETTINGS = {
    "starting_balance": 10_000.0, "investment": 100.0, "duration_seconds": 30,
    "max_investment": 1_000.0, "data_source": "SAMPLE", "sma_fast": 5,
    "sma_slow": 12, "rsi_period": 14, "max_consecutive_trades": 5,
    "max_demo_loss": 1_000.0, "payout_rate": 0.82, "log_level": "INFO",
}


@dataclass
class Settings:
    starting_balance: float = DEFAULT_SETTINGS["starting_balance"]
    investment: float = DEFAULT_SETTINGS["investment"]
    duration_seconds: int = DEFAULT_SETTINGS["duration_seconds"]
    max_investment: float = DEFAULT_SETTINGS["max_investment"]
    data_source: str = DEFAULT_SETTINGS["data_source"]
    sma_fast: int = DEFAULT_SETTINGS["sma_fast"]
    sma_slow: int = DEFAULT_SETTINGS["sma_slow"]
    rsi_period: int = DEFAULT_SETTINGS["rsi_period"]
    max_consecutive_trades: int = DEFAULT_SETTINGS["max_consecutive_trades"]
    max_demo_loss: float = DEFAULT_SETTINGS["max_demo_loss"]
    payout_rate: float = DEFAULT_SETTINGS["payout_rate"]
    log_level: str = DEFAULT_SETTINGS["log_level"]

    def validate(self) -> "Settings":
        numeric = ("starting_balance", "investment", "max_investment", "max_demo_loss", "payout_rate")
        for name in numeric:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be a finite number.")
        for name in ("duration_seconds", "sma_fast", "sma_slow", "rsi_period", "max_consecutive_trades"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name.replace('_', ' ').capitalize()} must be an integer.")
        if self.starting_balance <= 0:
            raise ValueError("Starting balance must be greater than zero.")
        if self.max_investment <= 0 or self.max_investment > self.starting_balance:
            raise ValueError("Maximum investment must be positive and within the starting balance.")
        if self.investment <= 0 or self.investment > self.max_investment:
            raise ValueError("Investment must be positive and no greater than the maximum.")
        if not 5 <= self.duration_seconds <= 86_400:
            raise ValueError("Trade duration must be between 5 seconds and 24 hours.")
        if self.sma_fast < 2 or self.sma_slow <= self.sma_fast:
            raise ValueError("Slow moving-average period must exceed the fast period (at least 2).")
        if not 2 <= self.rsi_period <= 100:
            raise ValueError("RSI period must be between 2 and 100.")
        if not 1 <= self.max_consecutive_trades <= 100:
            raise ValueError("Maximum consecutive trades must be between 1 and 100.")
        if self.max_demo_loss <= 0 or not 0 < self.payout_rate <= 1:
            raise ValueError("Loss threshold must be positive and payout rate must be in (0, 1].")
        if self.data_source != "SAMPLE":
            raise ValueError("Only the SAMPLE data source is available in this demo build.")
        return self

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "Settings":
        accepted = cls.__dataclass_fields__
        return cls(**{key: value for key, value in values.items() if key in accepted}).validate()

    def as_dict(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def default_settings() -> Settings:
    return Settings().validate()

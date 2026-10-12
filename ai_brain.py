# ai_brain.py

"""Simple, explainable technical analysis. Signals are educational, not advice."""

from math import isfinite
from typing import Any, Iterable


def _valid_prices(data: Iterable[Any]) -> list[float]:
    prices = []
    for item in data:
        value = item.get("close") if isinstance(item, dict) else getattr(item, "close", item)
        if isinstance(value, bool):
            raise ValueError("Prices must be finite positive numbers.")
        value = float(value)
        if not isfinite(value) or value <= 0:
            raise ValueError("Prices must be finite positive numbers.")
        prices.append(value)
    return prices


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    if period < 2 or len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(len(prices) - period, len(prices))]
    gains = sum(max(change, 0) for change in changes) / period
    losses = sum(max(-change, 0) for change in changes) / period
    if losses == 0:
        return 100.0 if gains else 50.0
    return round(100 - (100 / (1 + gains / losses)), 2)


def analyze_market(data: Iterable[Any], *, fast_period: int = 5, slow_period: int = 12,
                   rsi_period: int = 14) -> dict[str, Any]:
    """Return BUY, SELL, or WAIT with a reason and relevant indicator values."""
    try:
        prices = _valid_prices(data)
        if fast_period < 2 or slow_period <= fast_period or rsi_period < 2:
            raise ValueError("Indicator periods are invalid.")
    except (TypeError, ValueError, OverflowError) as exc:
        return {"signal": "WAIT", "reason": f"Invalid market data: {exc}", "indicators": {}}
    if len(prices) < slow_period:
        return {"signal": "WAIT", "reason": f"Need at least {slow_period} valid candles.", "indicators": {"samples": len(prices)}}

    fast_sma = sum(prices[-fast_period:]) / fast_period
    slow_sma = sum(prices[-slow_period:]) / slow_period
    rsi = calculate_rsi(prices, rsi_period)
    indicators = {"fast_sma": round(fast_sma, 6), "slow_sma": round(slow_sma, 6),
                  "rsi": rsi, "samples": len(prices)}
    if fast_sma > slow_sma and (rsi is None or rsi < 70):
        signal, reason = "BUY", "Fast SMA is above slow SMA; momentum is not strongly overbought."
    elif fast_sma < slow_sma and (rsi is None or rsi > 30):
        signal, reason = "SELL", "Fast SMA is below slow SMA; momentum is not strongly oversold."
    else:
        signal, reason = "WAIT", "Indicators are mixed or momentum is extended."
    return {"signal": signal, "reason": reason, "indicators": indicators}


if __name__ == "__main__":
    demo_prices = [100, 102, 101, 104]

    result = analyze_market(demo_prices)
    print("AI Agent Demo:", result)

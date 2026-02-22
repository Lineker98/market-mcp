"""
Tests the core computation functions in isolation.
No MCP, no Claude, no network (uses a synthetic DataFrame).
"""
import pandas as pd
import numpy as np

def make_fake_close(n=60, start=100.0, trend=0.5) -> pd.Series:
    """Generates a synthetic price series for deterministic tests."""
    prices = [start]
    for _ in range(n - 1):
        change = np.random.normal(trend, 2.0)
        prices.append(max(prices[-1] + change, 1.0))
    return pd.Series(prices)

def calc_rsi(close: pd.Series, period=14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return float((100 - 100 / (1 + rs)).iloc[-1])

def calc_bollinger(close: pd.Series, period=20) -> dict:
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    return {
        "upper": float((sma + 2 * std).iloc[-1]),
        "lower": float((sma - 2 * std).iloc[-1]),
        "sma":   float(sma.iloc[-1]),
    }

def test_rsi_range():
    close = make_fake_close()
    rsi = calc_rsi(close)
    assert 0 <= rsi <= 100, f"RSI out of range: {rsi}"
    print(f"✅ RSI in valid range: {rsi:.2f}")

def test_rsi_overbought():
    # Strongly upward trending series → RSI should be high
    close = pd.Series([100 + i * 2 for i in range(60)])
    rsi = calc_rsi(close)
    assert rsi > 70, f"Expected RSI > 70 for strong uptrend, got {rsi:.2f}"
    print(f"✅ RSI overbought detected: {rsi:.2f}")

def test_bollinger_width():
    close = make_fake_close()
    bands = calc_bollinger(close)
    assert bands["upper"] > bands["sma"] > bands["lower"]
    print(f"✅ Bollinger bands ordered correctly: {bands['lower']:.2f} < {bands['sma']:.2f} < {bands['upper']:.2f}")

def test_portfolio_pnl():
    holdings = [
        {"ticker": "AAPL", "quantity": 10, "avg_price": 150.0, "current_price": 180.0},
        {"ticker": "MSFT", "quantity":  5, "avg_price": 300.0, "current_price": 280.0},
    ]
    for h in holdings:
        h["pnl"]     = (h["current_price"] - h["avg_price"]) * h["quantity"]
        h["pnl_pct"] = (h["current_price"] / h["avg_price"] - 1) * 100

    assert holdings[0]["pnl"] == 300.0,   f"AAPL P&L wrong: {holdings[0]['pnl']}"
    assert holdings[1]["pnl"] == -100.0,  f"MSFT P&L wrong: {holdings[1]['pnl']}"
    print(f"✅ P&L calculation correct: AAPL +{holdings[0]['pnl']}, MSFT {holdings[1]['pnl']}")

if __name__ == "__main__":
    np.random.seed(42)   # deterministic results
    test_rsi_range()
    test_rsi_overbought()
    test_bollinger_width()
    test_portfolio_pnl()
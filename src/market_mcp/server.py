"""
Market Intelligence MCP Server — FastMCP version
"""

import json
from pathlib import Path
import yfinance as yf
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("market-intelligence")

BASE_DIR = Path(__file__).resolve().parents[2]
PORTFOLIO_FILE = BASE_DIR / "portfolio.json"

# ===========================================================================
# RESOURCES — dados que o host injeta no contexto (application-controlled)
# ===========================================================================

@mcp.resource("portfolio://holdings")
def portfolio_holdings() -> str:
    """Posições atuais da carteira: ticker, quantidade e preço médio de compra."""
    try:
        with open(PORTFOLIO_FILE) as f:
            return f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"{PORTFOLIO_FILE} não encontrado."})


@mcp.resource("market://overview")
def market_overview() -> str:
    """Cotação em tempo real dos principais índices: S&P 500, NASDAQ, Dow Jones e Bitcoin."""
    indices = {
        "^GSPC":   "S&P 500",
        "^IXIC":   "NASDAQ",
        "^DJI":    "Dow Jones",
        "BTC-USD": "Bitcoin",
    }
    overview = {}
    for symbol, name in indices.items():
        try:
            hist = yf.Ticker(symbol).history(period="2d")
            if hist.empty:
                overview[name] = {"error": "no data"}
                continue
            current    = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            change_pct = round((current / prev_close - 1) * 100, 2)
            overview[name] = {"price": round(current, 2), "change_pct": change_pct}
        except Exception as e:
            overview[name] = {"error": str(e)}

    return json.dumps(overview, indent=2, ensure_ascii=False)



# ===========================================================================
# TOOLS
# ===========================================================================
@mcp.tool()
def get_stock_quote(ticker: str) -> str:
    """
    Busca cotação atual de um ativo.
    Retorna preço, variação do dia, volume médio, máxima/mínima de 52 semanas e market cap.
    Exemplos de ticker: AAPL, MSFT, NVDA (EUA); PETR4.SA, VALE3.SA (Brasil); BTC-USD (crypto).
    """
    ticker = ticker.upper()
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period="5d")

        if hist.empty:
            return json.dumps({"error": f"Ticker '{ticker}' não encontrado."})

        info       = t.fast_info
        current    = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change     = current - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else 0

        return json.dumps({
            "ticker":           ticker,
            "price":            round(current, 2),
            "change":           round(change, 2),
            "change_pct":       round(change_pct, 2),
            "52w_high":         round(info.year_high, 2),
            "52w_low":          round(info.year_low, 2),
            "market_cap":       getattr(info, "market_cap", None),
            "volume_3m_avg":    getattr(info, "three_month_average_volume", None),
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker})


@mcp.tool()
def calculate_technical_indicators(ticker: str, period: str = "3mo") -> str:
    """
    Calcula indicadores técnicos: RSI (14), SMA20, SMA50 e Bandas de Bollinger.
    period: '1mo', '3mo', '6mo' ou '1y'. Padrão: '3mo'.
    """
    ticker = ticker.upper()
    try:
        hist  = yf.Ticker(ticker).history(period=period)
        close = hist["Close"]

        if len(close) < 20:
            return json.dumps({"error": "Dados insuficientes (mínimo 20 candles)."})

        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rsi   = float((100 - 100 / (1 + gain / loss)).iloc[-1])

        std20       = close.rolling(20).std()
        upper_band  = float((close.rolling(20).mean() + 2 * std20).iloc[-1])
        lower_band  = float((close.rolling(20).mean() - 2 * std20).iloc[-1])
        current     = float(close.iloc[-1])

        return json.dumps({
            "ticker":           ticker,
            "period":           period,
            "candles_analyzed": len(close),
            "current_price":    round(current, 2),
            "sma_20":           round(sma20, 2),
            "sma_50":           round(sma50, 2) if sma50 else "N/A",
            "rsi_14":           round(rsi, 2),
            "rsi_signal": (
                "Sobrecomprado (RSI > 70)" if rsi > 70 else
                "Sobrevendido (RSI < 30)"  if rsi < 30 else
                "Neutro"
            ),
            "bollinger_upper":  round(upper_band, 2),
            "bollinger_lower":  round(lower_band, 2),
            "price_vs_sma20":   "Acima" if current > sma20 else "Abaixo",
            "trend_direction":  "Alta"  if current > sma20 else "Baixa",
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e), "ticker": ticker})


@mcp.tool()
def evaluate_portfolio() -> str:
    """
    Calcula valor atual da carteira em portfolio.json.
    Retorna P&L por posição, alocação percentual e resumo consolidado.
    """
    try:
        with open(PORTFOLIO_FILE) as f:
            portfolio = json.load(f)
    except FileNotFoundError:
        return json.dumps({"error": f"Arquivo {PORTFOLIO_FILE} não encontrado."})

    total_invested = 0.0
    total_current  = 0.0
    positions      = []

    for holding in portfolio.get("holdings", []):
        ticker    = holding["ticker"]
        qty       = holding["quantity"]
        avg_price = holding["avg_price"]

        try:
            hist          = yf.Ticker(ticker).history(period="2d")
            current_price = float(hist["Close"].iloc[-1]) if not hist.empty else avg_price
        except Exception:
            current_price = avg_price

        invested      = qty * avg_price
        current_value = qty * current_price
        pnl           = current_value - invested
        pnl_pct       = (pnl / invested) * 100 if invested else 0

        total_invested += invested
        total_current  += current_value

        positions.append({
            "ticker":        ticker,
            "quantity":      qty,
            "avg_price":     round(avg_price, 2),
            "current_price": round(current_price, 2),
            "invested":      round(invested, 2),
            "current_value": round(current_value, 2),
            "pnl":           round(pnl, 2),
            "pnl_pct":       round(pnl_pct, 2),
        })

    for p in positions:
        p["allocation_pct"] = round(p["current_value"] / total_current * 100, 2) if total_current else 0

    total_pnl = total_current - total_invested

    return json.dumps({
        "summary": {
            "total_invested":      round(total_invested, 2),
            "total_current_value": round(total_current, 2),
            "total_pnl":           round(total_pnl, 2),
            "total_pnl_pct":       round((total_pnl / total_invested) * 100, 2) if total_invested else 0,
            "currency":            portfolio.get("currency", "BRL"),
        },
        "positions": sorted(positions, key=lambda x: x["current_value"], reverse=True),
    }, indent=2, ensure_ascii=False)
    

@mcp.prompt()
def analyze_stock(ticker: str, horizon: str = "médio") -> str:
    """Complete technical analysis of an asset using automated tools."""
    return f"""Perform a complete technical analysis of the asset **{ticker}** for a {horizon} time horizon.

**Required steps (use the tools in order):**
1. Call `get_stock_quote` to obtain the current quote.

2. Call `calculate_technical_indicators` with period="3mo".

## 1. Current Situation
- Price, daily variation, and 52-week context

## 2. Technical Analysis
- Trend (SMA20 and SMA50), RSI, Bollinger Bands

## 3. Support and Resistance
- Based on Bollinger Bands and SMAs

## 4. Points of Attention
- Warning signs and risks for the {horizon} time horizon

## 5. Conclusion
- Objective summary. Use only data from the tools."""


@mcp.prompt()
def portfolio_review(risk_profile: str = "moderado") -> str:
    """Complete portfolio review with performance analysis and rebalancing suggestions."""
    return f"""Perform a complete review of my portfolio. Risk profile: **{risk_profile}**.

**Required steps:**
1. Call `evaluate_portfolio` for the current state.
2. For the 2 largest weights, call `calculate_technical_indicators`.
3. Read the resource `market://overview` for market context.

## 1. Overall Performance — Total P&L vs. market
## 2. Position Analysis — Individual P&L, best and worst performers
## 3. Diversification — Concentration, suitability to the {risk_profile} profile
## 4. Technical Analysis — RSI, SMAs, and Bollinger Bands of the 2 largest weights
## 5. Rebalancing Suggestions — What to reduce, increase, or add
## 6. Risks — Technical alerts and risks of the current composition"""
    

# ===========================================================================
# Entry point
# ===========================================================================

def main_sync():
    mcp.run()


if __name__ == "__main__":
    mcp.run()
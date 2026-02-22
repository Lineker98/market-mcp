# market-mcp

> Investment assistant powered by the **Model Context Protocol** — real market data, technical indicators, and portfolio analysis through a conversational interface.

## How it works

```
┌─────────────────────────────────────────────────────┐
│                    CLIENT (REPL)                     │
│  User prompt → OpenAI agentic loop → final answer   │
└────────────────────┬────────────────────────────────┘
                     │ MCP over stdio
┌────────────────────▼────────────────────────────────┐
│                 MCP SERVER (FastMCP)                 │
│  Tools: get_stock_quote, calculate_technical_        │
│         indicators, evaluate_portfolio               │
│  Resources: portfolio://holdings, market://overview  │
│  Prompts: analyze_stock, portfolio_review            │
└────────────────────┬────────────────────────────────┘
                     │
              yfinance (Yahoo Finance)
```

The **server** is a pure data provider — it fetches prices and computes indicators via `yfinance`, with no LLM dependency. The **client** drives an OpenAI model in an agentic loop, calling MCP tools as needed to answer the user's question.

## Setup

```bash
uv sync
cp portfolio.json.example portfolio.json  # edit with your holdings
```

Set your OpenAI key:
```bash
export OPENAI_API_KEY=sk-...
```

## Running

```bash
# Start the interactive client (also spawns the server automatically)
uv run market-client
```

### Client commands

| Command | Description |
|---------|-------------|
| Free text | Natural language question → agentic loop |
| `/prompt analyze_stock ticker=PRIO3.SA` | Run a structured stock analysis |
| `/prompt portfolio_review risk_profile=agressivo` | Full portfolio review |
| `/resource market://overview` | Read a server resource directly |
| `/list` | Show all server capabilities |
| `sair` | Exit |

## Portfolio file

`portfolio.json` (gitignored — create locally):

```json
{
  "description": "My portfolio",
  "currency": "BRL",
  "holdings": [
    { "ticker": "PETR4.SA", "quantity": 100, "avg_price": 35.50 }
  ]
}
```

Tickers follow Yahoo Finance conventions: `.SA` suffix for B3, `-USD` for crypto (e.g. `BTC-USD`).

## Tests

```bash
uv run python tests/test_logic.py    # unit tests — no network, no MCP
uv run python tests/test_server.py   # MCP integration — spawns server, hits yfinance
uv run python tests/test_yfinance.py # yfinance smoke tests
```

## Technical decisions

**MCP over stdio (not HTTP).** The server and client run as sibling processes communicating over stdin/stdout. This keeps the setup dependency-free (no ports, no auth) and mirrors how MCP hosts like Claude Desktop work in practice.

**FastMCP.** The server uses `FastMCP` (decorator-based) rather than the low-level MCP SDK. This reduces boilerplate significantly — a tool is just a typed Python function.

**Server has no LLM dependency.** The server only knows about `yfinance` and `pandas`. The intelligence lives entirely in the client, which means you can swap the model (the client currently uses OpenAI, but Anthropic's SDK would work the same way against the same server).

**Prompts as reusable workflows.** MCP Prompts (`@mcp.prompt()`) are parameterized instruction templates stored server-side. The client fetches them at runtime, so prompt improvements don't require client changes.

**RSI and Bollinger computed from raw OHLCV data.** No external TA library is used — the indicators are implemented directly with `pandas` rolling windows. This avoids a heavy dependency and makes the math transparent and testable in isolation (`test_logic.py`).

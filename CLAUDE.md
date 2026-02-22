# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Market Intelligence MCP — an investment assistant built as a Model Context Protocol (MCP) server exposing stock market tools to an AI client. The server is consumed by an interactive CLI client that drives an OpenAI agentic loop over the MCP tools.

## Commands

This project uses `uv` for dependency management. Always use `uv run` to execute Python.

```bash
# Install dependencies
uv sync

# Run the MCP server standalone (stdio mode, for debugging)
uv run python src/market_mcp/server.py

# Run the interactive client (requires OPENAI_API_KEY)
uv run market-client
# or equivalently:
uv run python src/market_mcp/client.py

# Run unit tests (no network, no MCP)
uv run python tests/test_logic.py

# Run MCP integration tests (starts server as subprocess, requires network for yfinance)
uv run python tests/test_server.py

# Run yfinance smoke tests (requires network)
uv run python tests/test_yfinance.py
```

## Architecture

### Server (`src/market_mcp/server.py`)

FastMCP server exposing three MCP primitive types:

- **Resources** (application-controlled context injected by the host):
  - `portfolio://holdings` — reads `portfolio.json` from project root
  - `market://overview` — live prices for S&P 500, NASDAQ, Dow Jones, Bitcoin

- **Tools** (callable by the LLM):
  - `get_stock_quote(ticker)` — current price, daily change, 52-week high/low, market cap
  - `calculate_technical_indicators(ticker, period)` — RSI-14, SMA20, SMA50, Bollinger Bands
  - `evaluate_portfolio()` — reads `portfolio.json`, fetches live prices, returns P&L and allocation per position

- **Prompts** (reusable structured instructions):
  - `analyze_stock(ticker, horizon)` — guides the LLM to call quote + indicators tools in sequence
  - `portfolio_review(risk_profile)` — guides the LLM through full portfolio evaluation

### Client (`src/market_mcp/client.py`)

Interactive REPL that:
1. Launches `server.py` as a subprocess over stdio transport (`StdioServerParameters`)
2. Discovers tools via `session.list_tools()` and converts them to OpenAI function-calling format
3. Runs an agentic loop (`run_agent`) with up to `MAX_ROUNDS=10` iterations, passing tool results back to the model until `finish_reason == "stop"`

Client commands: `/help`, `/list`, `/resource <uri>`, `/prompt <name> [key=value ...]`, free-form natural language questions.

### Portfolio Data

`portfolio.json` at project root defines holdings (ticker, quantity, avg_price). It is **gitignored** — you must create it locally. See the file's structure: a `holdings` array with `ticker`, `quantity`, and `avg_price` fields, plus top-level `description` and `currency`.

### Environment

The client requires `OPENAI_API_KEY` set in the environment (or `.env` file, which is gitignored). The server has no API key dependency — all data comes from `yfinance`.

### Test Structure

- `tests/test_logic.py` — isolated unit tests for RSI, Bollinger, and P&L math using synthetic pandas Series; no network or MCP required
- `tests/test_server.py` — end-to-end integration: spawns the server as a subprocess and verifies all tools, resources, and prompts via the MCP protocol
- `tests/test_yfinance.py` — smoke tests hitting the real yfinance API

"""
Connects to the MCP server via stdio and tests every primitive:
  - tools/list + tools/call
  - resources/list + resources/read
  - prompts/list + prompts/get

No Claude involved — you're testing the server contract directly.
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_PATH = Path(__file__).parent.parent / "src" / "market_mcp" / "server.py"

async def run_tests():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(SERVER_PATH.parent.parent),   # so portfolio.json is found
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Connected to MCP server\n")

            # ── TOOLS ─────────────────────────────────────────────────────
            print("=" * 50)
            print("TOOLS")
            print("=" * 50)

            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"Discovered tools: {tool_names}")

            assert "get_stock_quote" in tool_names
            assert "calculate_technical_indicators" in tool_names
            assert "evaluate_portfolio" in tool_names
            print("✅ All expected tools declared\n")

            # Test get_stock_quote
            print("→ Calling get_stock_quote(AAPL)...")
            result = await session.call_tool("get_stock_quote", {"ticker": "AAPL"})
            data = json.loads(result.content[0].text)
            print(f"  Raw response: {json.dumps(data, indent=2)}")

            assert "price" in data,        "Missing 'price' field"
            assert data["price"] > 0,      "Price must be positive"
            assert "change_pct" in data,   "Missing 'change_pct' field"
            assert "52w_high" in data,     "Missing '52w_high' field"
            print("✅ get_stock_quote OK\n")

            # Test calculate_technical_indicators
            print("→ Calling calculate_technical_indicators(MSFT, 3mo)...")
            result = await session.call_tool(
                "calculate_technical_indicators",
                {"ticker": "MSFT", "period": "3mo"}
            )
            data = json.loads(result.content[0].text)
            print(f"  RSI: {data.get('rsi_14')} | SMA20: {data.get('sma_20')}")
            print(f"  Bollinger: {data.get('bollinger_lower')} — {data.get('bollinger_upper')}")

            assert 0 <= data["rsi_14"] <= 100,     "RSI out of range"
            assert data["bollinger_upper"] > data["bollinger_lower"]
            print("✅ calculate_technical_indicators OK\n")

            # Test evaluate_portfolio
            print("→ Calling evaluate_portfolio()...")
            result = await session.call_tool("evaluate_portfolio", {})
            data = json.loads(result.content[0].text)

            if "error" in data:
                print(f"  ⚠️  portfolio.json not found: {data['error']}")
            else:
                summary = data["summary"]
                print(f"  Total invested:  ${summary['total_invested']}")
                print(f"  Current value:   ${summary['total_current_value']}")
                print(f"  Total P&L:       ${summary['total_pnl']} ({summary['total_pnl_pct']}%)")
                print(f"  Positions: {len(data['positions'])}")
                assert "positions" in data
                assert summary["total_invested"] > 0
                print("✅ evaluate_portfolio OK\n")

            # ── RESOURCES ─────────────────────────────────────────────────
            print("=" * 50)
            print("RESOURCES")
            print("=" * 50)

            resources = await session.list_resources()
            uris = [str(r.uri) for r in resources.resources]
            assert "portfolio://holdings" in uris
            assert "market://overview" in uris
            print("✅ All expected resources declared\n")

            # Read portfolio resource
            print("→ Reading portfolio://holdings...")
            result = await session.read_resource("portfolio://holdings")
            data = json.loads(result.contents[0].text)
            print(f"  Holdings found: {len(data.get('holdings', []))}")
            print("✅ portfolio://holdings OK\n")

            # Read market overview resource
            print("→ Reading market://overview...")
            result = await session.read_resource("market://overview")
            data = json.loads(result.contents[0].text)
            print(f"  Indices returned: {list(data.keys())}")
            assert len(data) > 0
            print("✅ market://overview OK\n")

            # ── PROMPTS ───────────────────────────────────────────────────
            print("=" * 50)
            print("PROMPTS")
            print("=" * 50)

            prompts = await session.list_prompts()
            prompt_names = [p.name for p in prompts.prompts]
            print(f"Discovered prompts: {prompt_names}")
            assert "analyze_stock" in prompt_names
            assert "portfolio_review" in prompt_names
            print("✅ All expected prompts declared\n")

            # Get analyze_stock prompt
            print("→ Getting prompt analyze_stock(ticker=AAPL, horizon=médio)...")
            result = await session.get_prompt(
                "analyze_stock",
                {"ticker": "AAPL", "horizon": "médio"}
            )
            prompt_text = result.messages[0].content.text
            print(f"  Prompt length: {len(prompt_text)} chars")
            print(f"  First 100 chars: {prompt_text[:100]}...")
            assert "AAPL" in prompt_text,         "ticker not injected into prompt"
            assert "get_stock_quote" in prompt_text
            assert "calculate_technical_indicators" in prompt_text
            print("✅ analyze_stock prompt OK\n")

            # Get portfolio_review prompt
            print("→ Getting prompt portfolio_review(risk_profile=moderado)...")
            result = await session.get_prompt(
                "portfolio_review",
                {"risk_profile": "moderado"}
            )
            prompt_text = result.messages[0].content.text
            assert "moderado" in prompt_text,     "risk_profile not injected"
            assert "evaluate_portfolio" in prompt_text
            print("✅ portfolio_review prompt OK\n")

            print("=" * 50)
            print("🎉 All tests passed!")
            print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_tests())
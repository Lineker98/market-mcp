import asyncio
import json
import sys
import os
from openai import OpenAI                        # ← changed
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pathlib import Path

MODEL      = "gpt-5-mini" 
MAX_TOKENS = 4096
MAX_ROUNDS = 10

SERVER_PATH = Path(__file__).resolve().parent / "server.py"

SYSTEM_PROMPT = """Você é um assistente especializado em análise de investimentos.
Sempre use as ferramentas para obter dados reais antes de analisar.
Nunca invente preços ou indicadores. Responda em português.
"""

# ===========================================================================
# Helpers
# ===========================================================================
def _extract_text(content) -> str:
    """Extracts plain text from MCP tool result content."""
    if isinstance(content, list):
        return "\n".join(
            c.text if hasattr(c, "text") else str(c)
            for c in content
        )
    if hasattr(content, "text"):
        return content.text
    return str(content)


def _tools_to_openai(tools_response) -> list[dict]:
    """
    Converts MCP tool definitions to OpenAI format.
    FastMCP returns inputSchema directly — no conversion needed.
    """
    return [
        {
            "type": "function",                  # ← OpenAI requires this
            "function": {
                "name":        t.name,
                "description": t.description or "",
                "parameters":  t.inputSchema,    # same JSON schema, different key name
            }
        }
        for t in tools_response.tools
    ]

# ===========================================================================
# Agentic Loop
# ===========================================================================
async def run_agent(session: ClientSession, user_message: str) -> str:
    client = OpenAI() 

    # Discover tools from the FastMCP server
    tools_response = await session.list_tools()
    tools          = _tools_to_openai(tools_response)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},   # ← system goes in messages for OpenAI
        {"role": "user",   "content": user_message},
    ]

    print(f"\n{'─'*60}")
    print(f"💬 {user_message[:80]}{'...' if len(user_message) > 80 else ''}")
    print(f"{'─'*60}")

    for round_num in range(MAX_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=MAX_TOKENS,
            tools=tools,
            messages=messages,
        )

        choice  = response.choices[0]
        message = choice.message

        # ── Model wants to call tools ─────────────────────────────────
        if choice.finish_reason == "tool_calls":
            # Append assistant message with tool_calls
            messages.append(message)

            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                print(f"\n  🔧 {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")

                try:
                    mcp_result  = await session.call_tool(fn_name, fn_args)
                    result_text = _extract_text(mcp_result.content)
                except Exception as e:
                    result_text = json.dumps({"error": str(e)})

                preview = " | ".join(result_text.splitlines()[:3])
                print(f"     ↳ {preview}")

                # OpenAI expects one "tool" message per tool call
                messages.append({
                    "role":         "tool",              # ← different from Anthropic
                    "tool_call_id": tool_call.id,        # ← must match the call id
                    "content":      result_text,
                })

            continue

        # ── Final answer ──────────────────────────────────────────────
        if choice.finish_reason in ("stop", "length"):
            final = message.content or ""
            print(f"\n{final}\n{'─'*60}\n")
            return final

        return f"[finish_reason={choice.finish_reason}]"

    return "[Limite de iterações atingido]"


# ===========================================================================
# Commands
# ===========================================================================

def print_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║  Perguntas livres:                                           ║
║    Qual o preço da PRIO3.SA hoje?                           ║
║    Analise os indicadores técnicos da BPAC11.SA              ║
║    Como está minha carteira?                                 ║
║                                                              ║
║  Prompts do servidor:                                        ║
║    /prompt analyze_stock ticker=PRIO3.SA                     ║
║    /prompt analyze_stock ticker=BPAC11.SA horizon=longo      ║
║    /prompt portfolio_review                                  ║
║    /prompt portfolio_review risk_profile=agressivo           ║
║                                                              ║
║  Resources:                                                  ║
║    /resource portfolio://holdings                            ║
║    /resource market://overview                               ║
║                                                              ║
║  Utilitários:                                                ║
║    /list   — capacidades do servidor                         ║
║    /help   — este menu                                       ║
║    sair    — encerra                                         ║
╚══════════════════════════════════════════════════════════════╝
""")


async def show_capabilities(session: ClientSession):
    tools     = await session.list_tools()
    resources = await session.list_resources()
    prompts   = await session.list_prompts()

    print("\n═"*60)
    print("  🔧 TOOLS")
    for t in tools.tools:
        print(f"  • {t.name} — {(t.description or '')[:70]}")

    print("\n  📁 RESOURCES")
    for r in resources.resources:
        print(f"  • {r.uri}")

    print("\n  📋 PROMPTS")
    for p in prompts.prompts:
        args = ", ".join(
            f"{a.name}{'*' if a.required else '?'}"
            for a in (p.arguments or [])
        )
        print(f"  • {p.name}({args})")
    print()


# ===========================================================================
# Interactive loop
# ===========================================================================

async def interactive_loop(session: ClientSession):
    print("\n" + "═"*60)
    print("  🏦  Market Intelligence MCP")
    print("═"*60)
    print("  /help para ver os comandos\n")

    while True:
        try:
            raw = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAté logo! 👋")
            break

        if not raw:
            continue

        if raw.lower() in ("sair", "exit", "q"):
            print("Até logo! 👋")
            break

        if raw.lower() in ("/help", "help"):
            print_help()
            continue

        if raw.lower() == "/list":
            await show_capabilities(session)
            continue

        # ── /resource <uri> ───────────────────────────────────────────
        if raw.startswith("/resource "):
            uri = raw[10:].strip()
            try:
                result  = await session.read_resource(uri)
                content = _extract_text(
                    [c for c in result.contents]
                ) if result.contents else "Sem conteúdo"
                # contents[0].text for FastMCP resources
                text = result.contents[0].text if result.contents else "Sem conteúdo"
                print(f"\n📁 {uri}:\n{text}\n")
            except Exception as e:
                print(f"  ❌ {e}\n")
            continue

        # ── /prompt <name> [key=value ...] ────────────────────────────
        if raw.startswith("/prompt "):
            parts       = raw[8:].strip().split()
            prompt_name = parts[0] if parts else ""
            args        = {}
            for part in parts[1:]:
                if "=" in part:
                    k, v = part.split("=", 1)
                    args[k] = v

            if not prompt_name:
                print("  Uso: /prompt <nome> [chave=valor ...]\n")
                continue

            try:
                result      = await session.get_prompt(prompt_name, args)
                prompt_text = result.messages[0].content.text
                print(f"\n  📋 Prompt '{prompt_name}' carregado")
                await run_agent(session, prompt_text)
            except Exception as e:
                print(f"  ❌ Erro ao carregar prompt '{prompt_name}': {e}\n")
            continue

        # ── Free question → agentic loop ──────────────────────────────
        try:
            await run_agent(session, raw)
        except Exception as e:
            print(f"  ❌ {e}\n")


# ===========================================================================
# Entry point
# ===========================================================================

async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
        cwd=str(SERVER_PATH.parent.parent.parent),  # project root
    )

    print("🔌 Iniciando servidor MCP...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Conectado ao servidor market-intelligence\n")
            await interactive_loop(session)


def main_sync():
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY não configurada.")
        sys.exit(1)
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()

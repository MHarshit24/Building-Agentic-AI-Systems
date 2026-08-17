"""
FinDoc Analyzer — MCP Client + Yahoo Finance Integration
Dual .env loader: root .env (secrets) + project .env (config).
mcp_client.py: main/mcp/mcp_client.py
  parents[5] = Building_Agentic_AI_Systems  -> root .env
  parents[2] = FinDoc Analyzer              -> project .env

Yahoo Finance (yfinance) powers real-time financial data queries.
Falls back gracefully if yfinance or MCP is unavailable.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Any, Optional
from urllib.parse import quote_plus
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_env():
    if "pytest" in sys.modules:
        return
    base_dir = Path(__file__).resolve().parents[5]
    base_env_path = base_dir / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
    else:
        load_dotenv()
        logger.warning(f"Root .env not found at {base_env_path}")
    _preserved = {
        "DB_PASSWORD":           os.getenv("DB_PASSWORD"),
        "AZURE_OPENAI_API_KEY":  os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "LANGFUSE_PUBLIC_KEY":   os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY":   os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_HOST":         os.getenv("LANGFUSE_HOST"),
    }
    proj_dir = Path(__file__).resolve().parents[2]
    proj_env_path = proj_dir / ".env"
    if proj_env_path.exists():
        load_dotenv(dotenv_path=proj_env_path, override=True)
    else:
        load_dotenv()
        logger.warning(f"Project .env not found at {proj_env_path}")
    for key, val in _preserved.items():
        if val:
            os.environ[key] = val
    for var in ["DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
                "PGUSER", "PGPASSWORD", "PGDATABASE"]:
        os.environ.pop(var, None)


_load_env()

# ── yfinance (graceful import) ────────────────────────────────────
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
    logger.info("yfinance loaded ✓")
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed — run: pip install yfinance")

# ── LlamaIndex MCP (graceful import) ─────────────────────────────
try:
    from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE  = False
    BasicMCPClient = None
    McpToolSpec    = None

try:
    from llama_index.agent.openai import OpenAIAgent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

# ── Known ticker mapping for TechVision demo queries ─────────────
TICKER_ALIASES = {
    "techvision":            "MSFT",   # proxy for demo purposes
    "techvision corporation": "MSFT",
    "apple":  "AAPL",
    "google": "GOOGL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "nvidia": "NVDA",
    "meta":   "META",
}


def _resolve_ticker(question: str) -> Optional[str]:
    """Extract ticker symbol from question text."""
    import re
    q = question.lower()

    # Check alias map first
    for name, ticker in TICKER_ALIASES.items():
        if name in q:
            return ticker

    # Look for explicit ticker pattern like $MSFT or (MSFT)
    match = re.search(r'\$([A-Z]{1,5})\b|\(([A-Z]{1,5})\)', question)
    if match:
        return match.group(1) or match.group(2)

    return None


def _fetch_yfinance_data(question: str) -> Optional[str]:
    """
    Fetch real-time financial data via yfinance.
    Handles: stock price, market cap, P/E ratio, revenue, info.
    """
    if not YFINANCE_AVAILABLE:
        return None

    ticker_sym = _resolve_ticker(question)
    if not ticker_sym:
        return None

    q = question.lower()

    try:
        ticker = yf.Ticker(ticker_sym)
        info   = ticker.info

        if not info:
            return f"No data found for ticker {ticker_sym}."

        company_name = info.get("longName", ticker_sym)
        currency     = info.get("currency", "USD")

        # Stock price
        if any(w in q for w in ["price", "trading", "stock price", "share price", "current price"]):
            price  = info.get("currentPrice") or info.get("regularMarketPrice")
            prev   = info.get("previousClose")
            change = ((price - prev) / prev * 100) if price and prev else None
            result = f"{company_name} ({ticker_sym}) current stock price: {currency} {price:.2f}"
            if change is not None:
                result += f" ({'+' if change >= 0 else ''}{change:.2f}% vs prev close)"
            return result

        # Market cap
        if any(w in q for w in ["market cap", "market capitalization", "valuation"]):
            mcap = info.get("marketCap")
            if mcap:
                mcap_b = mcap / 1e9
                return f"{company_name} ({ticker_sym}) market cap: {currency} {mcap_b:.2f}B"

        # P/E ratio
        if any(w in q for w in ["p/e", "pe ratio", "price to earnings"]):
            pe = info.get("trailingPE") or info.get("forwardPE")
            if pe:
                return f"{company_name} ({ticker_sym}) P/E ratio: {pe:.2f}"

        # 52-week high/low
        if any(w in q for w in ["52 week", "52-week", "year high", "year low"]):
            high = info.get("fiftyTwoWeekHigh")
            low  = info.get("fiftyTwoWeekLow")
            return (
                f"{company_name} ({ticker_sym}) 52-week range: "
                f"{currency} {low:.2f} – {currency} {high:.2f}"
            )

        # Revenue (trailing twelve months)
        if any(w in q for w in ["revenue", "sales"]):
            rev = info.get("totalRevenue")
            if rev:
                rev_b = rev / 1e9
                return f"{company_name} ({ticker_sym}) trailing 12-month revenue: {currency} {rev_b:.2f}B"

        # Analyst recommendation
        if any(w in q for w in ["analyst", "recommendation", "rating", "target"]):
            rec    = info.get("recommendationKey", "N/A")
            target = info.get("targetMeanPrice")
            result = f"{company_name} ({ticker_sym}) analyst recommendation: {rec.upper()}"
            if target:
                result += f", mean price target: {currency} {target:.2f}"
            return result

        # Default: return key summary
        price  = info.get("currentPrice") or info.get("regularMarketPrice", "N/A")
        mcap   = info.get("marketCap", 0)
        mcap_b = mcap / 1e9 if mcap else 0
        sector = info.get("sector", "N/A")
        return (
            f"{company_name} ({ticker_sym}) — "
            f"Price: {currency} {price} | "
            f"Market Cap: {currency} {mcap_b:.1f}B | "
            f"Sector: {sector}"
        )

    except Exception as e:
        logger.error(f"yfinance fetch failed for {ticker_sym}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# MCP Service (HuggingFace MCP — optional)
# ═══════════════════════════════════════════════════════════════════

class FinDocMCPService:
    """MCP service for external financial data enrichment via HuggingFace."""

    def __init__(self):
        self.url     = os.getenv("MCP_SERVER_URL", "https://huggingface.co/mcp")
        self.token   = os.getenv("HF_TOKEN")
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

    async def load_tools(self, allowed_tools: Optional[List[str]] = None) -> List[Any]:
        if not MCP_AVAILABLE:
            return []
        if not self.token:
            logger.warning("HF_TOKEN not set — MCP tools unavailable")
            return []
        try:
            client    = BasicMCPClient(command_or_url=self.url, headers=self.headers)
            tool_spec = McpToolSpec(client=client)
            tools     = await tool_spec.to_tool_list_async()
            if allowed_tools:
                tools = [t for t in tools if t.metadata.name in allowed_tools]
            logger.info(f"Loaded {len(tools)} MCP tools")
            return tools
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            return []


_mcp_service: Optional[FinDocMCPService] = None


def get_mcp_service() -> FinDocMCPService:
    global _mcp_service
    if _mcp_service is None:
        _mcp_service = FinDocMCPService()
    return _mcp_service


# ═══════════════════════════════════════════════════════════════════
# Main entry point — called by query_router.py for MCP route
# ═══════════════════════════════════════════════════════════════════

async def query_mcp_tools(question: str) -> str:
    """
    Execute a question using:
    1. yfinance — for real-time stock/market data (primary)
    2. HuggingFace MCP tools — for research/model queries (secondary)
    3. Fallback message if neither is available
    """

    # ── 1. Try yfinance first ─────────────────────────────────────
    yf_result = _fetch_yfinance_data(question)
    if yf_result:
        logger.info(f"yfinance answered MCP query: {yf_result[:80]}")
        return yf_result

    # ── 2. Try HuggingFace MCP ────────────────────────────────────
    if MCP_AVAILABLE and AGENT_AVAILABLE:
        try:
            from llama_index.core.settings import Settings
            svc   = get_mcp_service()
            tools = await svc.load_tools(
                allowed_tools=["model_search", "search_papers", "summarization"]
            )
            if tools:
                agent = OpenAIAgent.from_tools(
                    tools,
                    llm=Settings.llm,
                    verbose=True,
                    system_prompt=(
                        "You are a financial research assistant. "
                        "Use available tools to find relevant financial data, "
                        "research papers, and market information."
                    ),
                )
                response = agent.chat(question)
                return str(response)
        except Exception as e:
            logger.error(f"MCP agent query failed: {e}")

    # ── 3. Fallback ───────────────────────────────────────────────
    return (
        "Real-time financial data is not available for this query. "
        "For live market data, ensure a valid ticker symbol is mentioned "
        "(e.g. 'What is the current price of MSFT?'). "
        "For historical TechVision financial data, try the /query endpoint "
        "without the 'current/latest' keywords."
    )
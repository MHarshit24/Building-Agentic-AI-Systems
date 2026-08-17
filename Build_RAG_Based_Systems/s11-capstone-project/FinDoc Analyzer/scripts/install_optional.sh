#!/usr/bin/env bash
# FinDoc Analyzer — Optional Package Installer
# Run after: pip install -r requirements.txt
#
# Installs and configures:
#   1. guardrails-ai hub validators
#   2. presidio spacy model
#   3. RAGAS + datasets
#   4. Anthropic LLamaIndex LLM adapter
#   5. llama-index-tools-mcp (if available)

set -e

echo "======================================================"
echo " FinDoc Analyzer — Optional Packages Setup"
echo "======================================================"

# ── 1. guardrails-ai hub validators ──────────────────────────────
echo ""
echo "[1/5] Installing guardrails-ai hub validators..."
if python -c "import guardrails" 2>/dev/null; then
    guardrails hub install hub://guardrails/detect_pii --quiet || echo "  ⚠ detect_pii install failed (may need auth)"
    guardrails hub install hub://guardrails/toxic_language --quiet || echo "  ⚠ toxic_language install failed"
    echo "  ✓ guardrails-ai validators installed"
else
    echo "  ⚠ guardrails-ai not found. Run: pip install guardrails-ai first"
fi

# ── 2. Presidio spacy model ───────────────────────────────────────
echo ""
echo "[2/5] Installing presidio spacy model (en_core_web_lg)..."
if python -c "import presidio_analyzer" 2>/dev/null; then
    python -m spacy download en_core_web_lg || echo "  ⚠ spacy model download failed"
    echo "  ✓ presidio spacy model installed"
else
    echo "  ⚠ presidio-analyzer not found. Run: pip install presidio-analyzer presidio-anonymizer spacy"
fi

# ── 3. RAGAS ─────────────────────────────────────────────────────
echo ""
echo "[3/5] Verifying RAGAS installation..."
if python -c "import ragas; import datasets" 2>/dev/null; then
    python -c "import ragas; print(f'  ✓ ragas {ragas.__version__} ready')"
else
    echo "  Installing ragas + datasets..."
    pip install ragas datasets --quiet
    echo "  ✓ RAGAS installed"
fi

# ── 4. Anthropic LLamaIndex adapter ──────────────────────────────
echo ""
echo "[4/5] Verifying Anthropic LlamaIndex adapter..."
if python -c "from llama_index.llms.anthropic import Anthropic" 2>/dev/null; then
    echo "  ✓ llama-index-llms-anthropic ready"
else
    echo "  Installing llama-index-llms-anthropic..."
    pip install llama-index-llms-anthropic --quiet
    echo "  ✓ Anthropic adapter installed"
fi

# ── 5. llama-index-tools-mcp ─────────────────────────────────────
echo ""
echo "[5/5] Trying llama-index-tools-mcp..."
if python -c "from llama_index.tools.mcp import BasicMCPClient" 2>/dev/null; then
    echo "  ✓ llama-index-tools-mcp ready"
else
    pip install llama-index-tools-mcp --quiet 2>/dev/null && \
        echo "  ✓ llama-index-tools-mcp installed" || \
        echo "  ⚠ llama-index-tools-mcp not available in PyPI yet — MCP will use mock fallback"
fi

echo ""
echo "======================================================"
echo " Optional setup complete!"
echo " Run: python scripts/setup_db.py   (one-time DB setup)"
echo " Run: python main.py               (start server)"
echo "======================================================"

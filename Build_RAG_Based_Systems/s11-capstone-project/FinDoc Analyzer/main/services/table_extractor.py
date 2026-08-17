"""
FinDoc Analyzer — Financial Table & Structure Extractor
Gap Fix: Dedicated table, footnote, chart-caption, and IMAGE extraction from financial PDFs.

Uses:
  - pymupdf (fitz)  → PDF page rendering, text blocks, table detection, image extraction
  - pandas           → Table normalization and structured data parsing
  - sqlalchemy       → Auto-insert extracted rows into financial_statements SQL table
  - LLM (vision)     → Multimodal analysis of embedded chart/figure images (NEW)

Called from ingest_routes.py after SimpleDirectoryReader ingestion.
Extracted structured data is inserted into the SQL tables for SQL/Hybrid query routing.
Image-derived insights are returned as LlamaIndex Document objects for RAG indexing (NEW).
"""

import sys
import base64
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

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

    for var in [
        "DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGPORT",
        "PGUSER", "PGPASSWORD", "PGDATABASE",
    ]:
        os.environ.pop(var, None)


_load_env()

# Known financial metric patterns to identify table rows
INCOME_METRICS = {
    "revenue", "net revenue", "total revenue", "net sales",
    "gross profit", "operating income", "operating profit", "ebitda",
    "net income", "earnings", "eps", "earnings per share",
    "research and development", "r&d", "selling general", "sg&a",
    "depreciation", "amortization", "interest expense", "income tax",
}

BALANCE_METRICS = {
    "total assets", "current assets", "cash", "cash equivalents",
    "accounts receivable", "inventory", "total liabilities",
    "current liabilities", "long term debt", "total equity",
    "shareholders equity", "stockholders equity", "retained earnings",
    "goodwill", "intangible assets", "property plant equipment",
}

CASHFLOW_METRICS = {
    "operating cash flow", "capital expenditure", "capex", "free cash flow",
    "investing activities", "financing activities", "dividends",
    "share repurchase", "net change in cash",
}

RATIO_METRICS = {
    "gross margin", "net margin", "operating margin", "ebitda margin",
    "return on equity", "roe", "return on assets", "roa",
    "debt to equity", "current ratio", "quick ratio", "p/e", "price to earnings",
    "revenue growth", "earnings growth",
}


def classify_metric(metric_name: str) -> str:
    """Classify a financial metric into statement type."""
    name_lower = metric_name.lower().strip()
    if any(m in name_lower for m in INCOME_METRICS):
        return "income_statement"
    if any(m in name_lower for m in BALANCE_METRICS):
        return "balance_sheet"
    if any(m in name_lower for m in CASHFLOW_METRICS):
        return "cash_flow"
    if any(m in name_lower for m in RATIO_METRICS):
        return "ratio"
    return "other"


def _parse_number(value_str: str) -> Optional[float]:
    """
    Parse a financial number string to float.
    Handles: (1,234) = negative, 1.2B = billion, 1.2M = million, 45% = ratio
    """
    if not value_str:
        return None
    s = str(value_str).strip()
    if s in ("-", "—", "N/A", "n/a", "nm", "NM", ""):
        return None

    negative = s.startswith("(") and s.endswith(")")
    s = s.replace("(", "").replace(")", "")
    s = re.sub(r"[$£€¥,\s]", "", s)

    multiplier = 1.0
    if s.upper().endswith("B"):
        multiplier = 1_000.0
        s = s[:-1]
    elif s.upper().endswith("M"):
        multiplier = 1.0
        s = s[:-1]
    elif s.upper().endswith("K"):
        multiplier = 0.001
        s = s[:-1]
    elif s.endswith("%"):
        s = s[:-1]
        multiplier = 1.0

    try:
        value = float(s) * multiplier
        return -value if negative else value
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════
# Multimodal Image Analyzer  (NEW)
# ═══════════════════════════════════════════════════════════════════

class PDFImageAnalyzer:
    """
    Extract images/charts from a PDF page and run LLM vision analysis on them.

    Strategy:
      1. Render each PDF page as a high-resolution PNG via pymupdf.
      2. Also extract embedded raster images (XOBJECT) for higher fidelity where available.
      3. Send each image to the configured LLM provider's vision API.
      4. Return structured text descriptions suitable for RAG indexing.

    Supported LLM providers:
      - Anthropic  (claude-3-5-sonnet / claude-opus-4 via messages API)
      - Azure OpenAI / OpenAI (gpt-4o via chat completions with image_url)
    """

    # Minimum image dimensions — skip tiny icons / logos
    MIN_WIDTH  = 150
    MIN_HEIGHT = 100

    # System prompt used for all chart analyses
    CHART_ANALYSIS_PROMPT = (
        "You are a financial analyst assistant. "
        "Analyze the following financial chart or figure extracted from an annual report. "
        "Extract ALL quantitative data visible (values, percentages, years, labels). "
        "Describe the trend, key data points, and any notable observations. "
        "Format your response as:\n"
        "CHART TYPE: <type>\n"
        "DATA POINTS: <list all visible numbers with their labels>\n"
        "TREND SUMMARY: <2-3 sentence description of the trend>\n"
        "KEY INSIGHTS: <bullet list of important observations>\n"
        "Return plain text only — no markdown headers or code fences."
    )

    def __init__(self):
        self._provider = os.getenv("LLM_PROVIDER", "azure").lower()

    # ── Provider-specific vision calls ───────────────────────────

    def _analyze_with_anthropic(self, image_b64: str, mime: str = "image/png") -> str:
        """Call Anthropic Messages API with base64 image."""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            model  = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            msg = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type":       "base64",
                                "media_type": mime,
                                "data":       image_b64,
                            },
                        },
                        {"type": "text", "text": self.CHART_ANALYSIS_PROMPT},
                    ],
                }],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            logger.error(f"Anthropic vision call failed: {e}")
            return ""

    def _analyze_with_openai(self, image_b64: str, mime: str = "image/png") -> str:
        """Call OpenAI / Azure OpenAI chat completions with base64 image_url."""
        try:
            from openai import AzureOpenAI, OpenAI

            if self._provider == "azure":
                client = AzureOpenAI(
                    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                )
                model = os.getenv("AZURE_OPENAI_LLM_DEPLOYMENT", "gpt-4o")
            else:
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                model  = os.getenv("OPENAI_MODEL", "gpt-4o")

            data_url = f"data:{mime};base64,{image_b64}"
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text",      "text": self.CHART_ANALYSIS_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI/Azure vision call failed: {e}")
            return ""

    def analyze_image(self, image_b64: str, mime: str = "image/png") -> str:
        """Route to the configured provider's vision API."""
        if self._provider == "anthropic":
            return self._analyze_with_anthropic(image_b64, mime)
        return self._analyze_with_openai(image_b64, mime)

    # ── Page-level image extraction ───────────────────────────────

    def extract_and_analyze_page_images(
        self,
        page,                   # fitz.Page
        page_num: int,
        source_name: str,
        company_name: str,
        fiscal_year: Optional[int],
        seen_xrefs: Optional[set] = None,   # FIX: cross-page XObject deduplication
    ) -> List[Dict[str, Any]]:
        """
        For a single PDF page:
          1. Try to extract embedded XObject images first (higher quality).
          2. Fall back to rendering the full page as a PNG if no images found
             but the page appears to contain a chart/figure.
          3. Run vision analysis on each qualifying image.

        Returns a list of dicts with keys:
          page, image_index, width, height, analysis, source, company_name,
          fiscal_year, image_type ("embedded" | "page_render")
        """
        results = []
        try:
            import fitz  # noqa: F401 — already imported by caller
        except ImportError:
            return results

        # FIX: use the shared seen_xrefs set passed in from extract_all so that
        # the same PDF XObject (e.g. a chart embedded once but referenced on
        # multiple pages) is only sent to the vision API once across all pages.
        if seen_xrefs is None:
            seen_xrefs = set()

        # ── Attempt 1: embedded raster images ────────────────────
        image_list = page.get_images(full=True)
        processed  = 0

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]

            # FIX: skip xrefs already processed on a previous page
            if xref in seen_xrefs:
                logger.debug(f"  Skipping duplicate xref={xref} on page {page_num}")
                continue
            seen_xrefs.add(xref)

            try:
                import fitz as _fitz
                base_img = page.parent.extract_image(xref)
                if not base_img:
                    continue

                w, h = base_img.get("width", 0), base_img.get("height", 0)
                if w < self.MIN_WIDTH or h < self.MIN_HEIGHT:
                    logger.debug(f"  Skipping tiny image ({w}x{h}) on page {page_num}")
                    continue

                img_bytes = base_img["image"]
                ext       = base_img.get("ext", "png")
                mime      = f"image/{ext}" if ext in ("png", "jpeg", "jpg") else "image/png"
                img_b64   = base64.b64encode(img_bytes).decode("utf-8")

                logger.info(
                    f"  Analyzing embedded image {img_idx+1} on page {page_num} "
                    f"({w}x{h} {ext})"
                )
                analysis = self.analyze_image(img_b64, mime)
                if not analysis:
                    continue

                results.append({
                    "page":         page_num,
                    "image_index":  img_idx,
                    "width":        w,
                    "height":       h,
                    "analysis":     analysis,
                    "source":       source_name,
                    "company_name": company_name,
                    "fiscal_year":  fiscal_year,
                    "image_type":   "embedded",
                })
                processed += 1

            except Exception as e:
                logger.debug(f"  Embedded image extraction failed (xref={xref}): {e}")

        # ── Attempt 2: full-page render if no embedded images found ──
        # Only render pages that look like they contain charts
        if processed == 0:
            page_text_lower = page.get_text().lower()
            chart_signals   = [
                "revenue", "growth", "quarterly", "chart", "figure",
                "trend", "graph", "%", "million", "billion",
            ]
            has_chart_signal = sum(1 for s in chart_signals if s in page_text_lower) >= 3

            if has_chart_signal:
                try:
                    import fitz as _fitz
                    # Render at 2× scale for better OCR/vision quality
                    mat  = _fitz.Matrix(2.0, 2.0)
                    pix  = page.get_pixmap(matrix=mat, alpha=False)
                    w, h = pix.width, pix.height

                    if w >= self.MIN_WIDTH and h >= self.MIN_HEIGHT:
                        img_bytes = pix.tobytes("png")
                        img_b64   = base64.b64encode(img_bytes).decode("utf-8")

                        logger.info(
                            f"  Rendering page {page_num} as image for chart analysis "
                            f"({w}x{h})"
                        )
                        analysis = self.analyze_image(img_b64, "image/png")
                        if analysis:
                            results.append({
                                "page":         page_num,
                                "image_index":  0,
                                "width":        w,
                                "height":       h,
                                "analysis":     analysis,
                                "source":       source_name,
                                "company_name": company_name,
                                "fiscal_year":  fiscal_year,
                                "image_type":   "page_render",
                            })
                except Exception as e:
                    logger.debug(f"  Page render for chart analysis failed (page {page_num}): {e}")

        return results


def image_analyses_to_documents(
    image_results: List[Dict[str, Any]],
) -> List:
    """
    Convert image analysis dicts into LlamaIndex Document objects
    so they can be indexed alongside text chunks in PGVector.

    Returns an empty list if llama_index is not available.
    """
    try:
        from llama_index.core import Document
    except ImportError:
        logger.warning("llama_index not available — skipping image document conversion")
        return []

    docs = []
    for r in image_results:
        analysis = r.get("analysis", "").strip()
        if not analysis:
            continue

        text = (
            f"[CHART ANALYSIS — Page {r['page']} of {r['source']}]\n"
            f"Company: {r.get('company_name', 'unknown')} | "
            f"Fiscal Year: {r.get('fiscal_year', 'unknown')} | "
            f"Image Type: {r.get('image_type', 'unknown')}\n\n"
            f"{analysis}"
        )
        docs.append(Document(
            text=text,
            metadata={
                "source_file":   r["source"],
                "company_name":  r.get("company_name", "unknown"),
                "fiscal_year":   str(r.get("fiscal_year", "unknown")),
                "content_type":  "chart_analysis",
                "page_number":   str(r["page"]),
                "image_type":    r.get("image_type", "unknown"),
                "image_width":   str(r.get("width", 0)),
                "image_height":  str(r.get("height", 0)),
            },
        ))

    logger.info(f"Created {len(docs)} Document objects from image analyses")
    return docs


# ═══════════════════════════════════════════════════════════════════
# PDF Table Extractor (pymupdf)
# ═══════════════════════════════════════════════════════════════════

class PDFTableExtractor:
    """
    Extract financial tables and images from PDF using pymupdf.
    Sprint5 pattern: multimodal document processing.
    Sprint5 enhancement: PDFImageAnalyzer integration for chart extraction.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path     = pdf_path
        self._check_pymupdf()
        self._img_analyzer = PDFImageAnalyzer()

    def _check_pymupdf(self):
        try:
            import fitz
            self._fitz = fitz
        except ImportError:
            raise ImportError("pymupdf not installed. Run: pip install pymupdf")

    def extract_all(
        self,
        company_name: str = "unknown",
        fiscal_year:  int = None,
        analyze_images: bool = True,
        original_filename: Optional[str] = None,   # FIX: accept original uploaded filename
    ) -> Dict[str, Any]:
        """
        Full extraction pipeline:
        1. Detect financial statement pages
        2. Extract tables with pymupdf find_tables()
        3. Extract footnotes (text blocks after asterisk / small-font text)
        4. Extract and analyze images/charts via LLM vision (NEW)
        5. Return structured result including image_documents
        """
        result = {
            "tables":            [],
            "footnotes":         [],
            "metrics":           [],
            "page_count":        0,
            "image_analyses":    [],     # raw dicts from PDFImageAnalyzer (NEW)
            "image_documents":   [],     # LlamaIndex Document objects (NEW)
        }

        fitz = self._fitz
        try:
            doc = fitz.open(self.pdf_path)
        except Exception as e:
            logger.error(f"Cannot open PDF {self.pdf_path}: {e}")
            return result

        result["page_count"] = len(doc)
        # FIX: use original_filename if provided so that image analysis documents
        # are tagged with the user-facing filename rather than the temp file name.
        source_name = original_filename or Path(self.pdf_path).name
        logger.info(
            f"Extracting tables + images from {len(doc)}-page PDF: {source_name}"
        )

        all_image_analyses: List[Dict[str, Any]] = []
        seen_xrefs: set = set()   # FIX: shared across all pages to deduplicate XObjects

        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text().lower()
            is_financial_page = any(kw in page_text for kw in [
                "consolidated statements", "balance sheet", "income statement",
                "cash flow", "statement of operations", "financial highlights",
                "revenue", "net income", "total assets",
            ])

            if not is_financial_page:
                footnotes = self._extract_footnotes(page)
                result["footnotes"].extend(footnotes)
                # Still check for images on non-financial pages (e.g. charts on cover)
                if analyze_images:
                    imgs = self._img_analyzer.extract_and_analyze_page_images(
                        page, page_num, source_name, company_name, fiscal_year,
                        seen_xrefs=seen_xrefs,   # FIX: pass shared set
                    )
                    all_image_analyses.extend(imgs)
                continue

            logger.debug(f"  Processing financial page {page_num}")

            # ── Extract tables ────────────────────────────────────
            try:
                tables_found = page.find_tables()
                for tbl in tables_found:
                    df = self._table_to_dataframe(tbl)
                    if df is not None and len(df) > 1:
                        result["tables"].append({
                            "page":  page_num,
                            "rows":  len(df),
                            "cols":  len(df.columns),
                            "data":  df.to_dict(orient="records"),
                        })
                        metrics = self._parse_metrics_from_df(
                            df, company_name, fiscal_year, page_num
                        )
                        result["metrics"].extend(metrics)
            except Exception as e:
                logger.debug(f"  find_tables() not available ({e}), using text-block fallback")
                metrics = self._extract_metrics_from_text(
                    page_text, company_name, fiscal_year, page_num
                )
                result["metrics"].extend(metrics)

            # ── Extract footnotes ─────────────────────────────────
            footnotes = self._extract_footnotes(page)
            result["footnotes"].extend(footnotes)

            # ── Extract and analyze images (NEW) ──────────────────
            if analyze_images:
                imgs = self._img_analyzer.extract_and_analyze_page_images(
                    page, page_num, source_name, company_name, fiscal_year,
                    seen_xrefs=seen_xrefs,   # FIX: pass shared set
                )
                all_image_analyses.extend(imgs)

        doc.close()

        # Convert image analyses to LlamaIndex Documents
        result["image_analyses"]  = all_image_analyses
        result["image_documents"] = image_analyses_to_documents(all_image_analyses)

        logger.info(
            f"✓ Extraction complete: {len(result['tables'])} tables, "
            f"{len(result['metrics'])} metrics, "
            f"{len(result['footnotes'])} footnotes, "
            f"{len(all_image_analyses)} image analyses"
        )
        return result

    def _table_to_dataframe(self, tbl) -> Optional[pd.DataFrame]:
        """Convert a pymupdf table object to a pandas DataFrame."""
        try:
            data = tbl.extract()
            if not data or len(data) < 2:
                return None
            headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(data[0])]
            rows    = data[1:]
            df      = pd.DataFrame(rows, columns=headers)
            df.dropna(how="all", inplace=True)
            df      = df.loc[:, df.apply(lambda c: c.astype(str).str.strip().ne("").any())]
            return df if len(df) > 0 else None
        except Exception as e:
            logger.debug(f"DataFrame conversion failed: {e}")
            return None

    def _parse_metrics_from_df(
        self, df: pd.DataFrame,
        company_name: str, fiscal_year: Optional[int], page_num: int
    ) -> List[Dict[str, Any]]:
        metrics   = []
        if df.empty or len(df.columns) < 2:
            return metrics

        cols      = list(df.columns)
        label_col = cols[0]
        value_cols = cols[1:]

        year_map = {}
        for col in value_cols:
            match = re.search(r"20\d{2}", str(col))
            if match:
                year_map[col] = int(match.group())

        for _, row in df.iterrows():
            metric_name = str(row.get(label_col, "")).strip()
            if not metric_name or len(metric_name) < 3:
                continue

            stmt_type = classify_metric(metric_name)

            for col in value_cols:
                raw_val = str(row.get(col, "")).strip()
                value   = _parse_number(raw_val)
                if value is None:
                    continue

                year = year_map.get(col, fiscal_year)
                metrics.append({
                    "company_name":    company_name,
                    "fiscal_year":     year,
                    "statement_type":  stmt_type,
                    "metric_name":     metric_name,
                    "metric_value":    value,
                    "source_document": Path(self.pdf_path).name,
                    "page_number":     page_num,
                })

        return metrics

    def _extract_metrics_from_text(
        self, page_text: str,
        company_name: str, fiscal_year: Optional[int], page_num: int
    ) -> List[Dict[str, Any]]:
        metrics  = []
        pattern  = re.compile(
            r"([A-Za-z][A-Za-z ,&\-/()]{3,60})\s{2,}"
            r"([\$\(]?[\d,\.]+[BMK%\)]?)"
            r"(?:\s{2,}([\$\(]?[\d,\.]+[BMK%\)]?))?"
            r"(?:\s{2,}([\$\(]?[\d,\.]+[BMK%\)]?))?",
            re.MULTILINE
        )

        for match in pattern.finditer(page_text):
            label     = match.group(1).strip()
            stmt_type = classify_metric(label)
            if stmt_type == "other":
                continue

            for raw_val in [match.group(2), match.group(3), match.group(4)]:
                if not raw_val:
                    continue
                value = _parse_number(raw_val)
                if value is None:
                    continue

                metrics.append({
                    "company_name":    company_name,
                    "fiscal_year":     fiscal_year,
                    "statement_type":  stmt_type,
                    "metric_name":     label,
                    "metric_value":    value,
                    "source_document": Path(self.pdf_path).name,
                    "page_number":     page_num,
                })
                break

        return metrics

    def _extract_footnotes(self, page) -> List[Dict[str, Any]]:
        footnotes = []
        try:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        size = span.get("size", 12)
                        is_footnote_font   = size < 9
                        is_footnote_marker = bool(re.match(r"^[\*†‡1-9]\s+", text))
                        if (is_footnote_font or is_footnote_marker) and len(text) > 10:
                            footnotes.append({
                                "text":      text,
                                "font_size": round(size, 1),
                                "type":      "footnote",
                            })
        except Exception as e:
            logger.debug(f"Footnote extraction failed: {e}")
        return footnotes


# ═══════════════════════════════════════════════════════════════════
# CSV / Excel Table Extractor
# ═══════════════════════════════════════════════════════════════════

class SpreadsheetTableExtractor:
    """
    Extract financial tables from CSV / Excel files using pandas.
    Sprint5 pattern: structured financial data ingestion.
    """

    def extract(
        self,
        file_path: str,
        company_name: str = "unknown",
        fiscal_year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        metrics = []
        path    = Path(file_path)
        ext     = path.suffix.lower()

        try:
            if ext == ".csv":
                df = pd.read_csv(file_path)
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(file_path)
            else:
                logger.warning(f"Unsupported spreadsheet type: {ext}")
                return metrics

            logger.info(f"Loaded spreadsheet: {path.name} ({len(df)} rows × {len(df.columns)} cols)")
            metrics = self._parse_spreadsheet(df, company_name, fiscal_year, path.name)
        except Exception as e:
            logger.error(f"Spreadsheet extraction failed for {file_path}: {e}")

        return metrics

    def _parse_spreadsheet(
        self, df: pd.DataFrame,
        company_name: str, fiscal_year: Optional[int], source_name: str
    ) -> List[Dict[str, Any]]:
        metrics = []
        cols    = list(df.columns)

        year_col_candidates   = [c for c in cols if re.search(r"year|period|date|fy",   str(c), re.I)]
        metric_col_candidates = [c for c in cols if re.search(r"metric|item|name|description|account", str(c), re.I)]
        value_col_candidates  = [c for c in cols if re.search(r"value|amount|figure",   str(c), re.I)]

        if year_col_candidates and metric_col_candidates and value_col_candidates:
            year_col   = year_col_candidates[0]
            metric_col = metric_col_candidates[0]
            value_col  = value_col_candidates[0]
            for _, row in df.iterrows():
                metric_name = str(row.get(metric_col, "")).strip()
                raw_val     = str(row.get(value_col, "")).strip()
                year        = row.get(year_col, fiscal_year)
                value       = _parse_number(raw_val)
                if not metric_name or value is None:
                    continue
                metrics.append({
                    "company_name":    company_name,
                    "fiscal_year":     int(year) if year else fiscal_year,
                    "statement_type":  classify_metric(metric_name),
                    "metric_name":     metric_name,
                    "metric_value":    value,
                    "source_document": source_name,
                    "page_number":     None,
                })
            return metrics

        label_col  = cols[0]
        value_cols = cols[1:]
        year_map   = {}
        for col in value_cols:
            m = re.search(r"20\d{2}", str(col))
            if m:
                year_map[col] = int(m.group())

        for _, row in df.iterrows():
            metric_name = str(row.get(label_col, "")).strip()
            if not metric_name or len(metric_name) < 2:
                continue
            stmt_type = classify_metric(metric_name)

            for col in value_cols:
                raw_val = str(row.get(col, "")).strip()
                value   = _parse_number(raw_val)
                if value is None:
                    continue
                year = year_map.get(col, fiscal_year)
                metrics.append({
                    "company_name":    company_name,
                    "fiscal_year":     year,
                    "statement_type":  stmt_type,
                    "metric_name":     metric_name,
                    "metric_value":    value,
                    "source_document": source_name,
                    "page_number":     None,
                })

        return metrics


# ═══════════════════════════════════════════════════════════════════
# SQL Insertion
# ═══════════════════════════════════════════════════════════════════

def insert_metrics_to_sql(metrics: List[Dict[str, Any]]) -> int:
    """
    Insert extracted metrics using the project's canonical SQL service.
    Structured metrics are inserted through sql_service.insert_financial_metric().
    """
    if not metrics:
        return 0

    try:
        from main.services.sql_service import insert_financial_metric
    except Exception as e:
        logger.error(f"Could not import insert_financial_metric: {e}")
        return 0

    inserted = 0

    for m in metrics:
        fiscal_year  = m.get("fiscal_year")
        metric_name  = m.get("metric_name")
        metric_value = m.get("metric_value")

        if not fiscal_year or not metric_name or metric_value is None:
            continue

        try:
            insert_financial_metric(
                company_name=m.get("company_name", "unknown"),
                fiscal_year=int(fiscal_year),
                statement_type=m.get("statement_type", "income_statement"),
                metric_name=metric_name,
                metric_value=float(metric_value),
                source_document=m.get("source_document"),
            )
            inserted += 1
        except Exception as e:
            logger.debug(f"Insert skipped ({metric_name}): {e}")

    logger.info(f"✓ Inserted {inserted}/{len(metrics)} financial metrics into SQL")
    return inserted


# ═══════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════

def extract_and_store_financial_data(
    file_path:    str,
    company_name: str = "unknown",
    fiscal_year:  Optional[int] = None,
    analyze_images: bool = True,
    original_filename: Optional[str] = None,   # FIX: accept original uploaded filename
) -> Dict[str, Any]:
    """
    Main entry point called from ingest_routes.py.
    Selects extractor based on file type, extracts structured data + images,
    inserts into SQL, returns summary including image_documents for RAG.

    Args:
        file_path:          Path to the uploaded financial document.
        company_name:       Company name tag for metadata.
        fiscal_year:        Fiscal year tag for metadata.
        analyze_images:     Whether to run LLM vision on embedded charts (PDF only).
        original_filename:  Original uploaded filename (overrides temp path basename
                            in image document metadata).

    Returns:
        dict with keys:
          metrics_extracted, metrics_inserted, tables_found, footnotes_found,
          extractor_used, image_analyses_count, image_documents (List[Document])
    """
    ext    = Path(file_path).suffix.lower()
    result = {
        "metrics_extracted":   0,
        "metrics_inserted":    0,
        "tables_found":        0,
        "footnotes_found":     0,
        "extractor_used":      "none",
        "image_analyses_count": 0,
        "image_documents":     [],
    }

    if ext == ".pdf":
        try:
            extractor = PDFTableExtractor(file_path)
            data      = extractor.extract_all(
                company_name,
                fiscal_year,
                analyze_images=analyze_images,
                original_filename=original_filename,   # FIX: thread through
            )
            metrics = data["metrics"]
            result.update({
                "metrics_extracted":    len(metrics),
                "tables_found":         len(data["tables"]),
                "footnotes_found":      len(data["footnotes"]),
                "extractor_used":       "pymupdf",
                "image_analyses_count": len(data.get("image_analyses", [])),
                "image_documents":      data.get("image_documents", []),
            })
        except ImportError as e:
            logger.warning(f"PDF table extraction skipped: {e}")
            return result

    elif ext in (".csv", ".xlsx", ".xls"):
        extractor = SpreadsheetTableExtractor()
        metrics   = extractor.extract(file_path, company_name, fiscal_year)
        result.update({
            "metrics_extracted": len(metrics),
            "extractor_used":    "pandas",
        })

    else:
        logger.debug(f"No table extractor for extension: {ext}")
        return result

    if metrics:
        inserted = insert_metrics_to_sql(metrics)
        result["metrics_inserted"] = inserted

    return result
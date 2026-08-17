"""
app/ingestion/extract_text.py

Text extraction + structure-aware recursive chunking, per §8.2.1.

Two-level split:
  1. Structure split (this file, custom) — PyMuPDF span-level font-size
     detection finds header boundaries, same technique already proven
     for footnote detection in prior work (is_footnote_font pattern,
     inverted: larger/bolder text = header, not smaller). NOT
     LangChain's MarkdownHeaderTextSplitter — that operates on literal
     `#`/`##` Markdown syntax, which doesn't exist in these PDFs; the
     "headers" only exist as font metadata.
  2. Recursive sub-split within each section (langchain-text-splitters'
     RecursiveCharacterTextSplitter, token-counted via tiktoken so the
     ~400-token target is an actual token count, not a character count).

Fallback (§8.2.1): a document with no detectable header structure skips
level 1 entirely and goes straight to level-2 recursive splitting.
"""

import re
from dataclasses import dataclass, field

import fitz  # PyMuPDF
import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_TARGET_TOKENS = 400
CHUNK_OVERLAP_RATIO = 0.15

# §8.2.1's original spec: "split on numbered section headers where
# present." This is the PRIMARY signal — matches "1.", "8.2.1", "A.",
# etc. at the start of a line. Deliberately does NOT match on font
# styling alone: a font-size/bold-only heuristic was tried first and
# found to misfire badly on table cells and flowchart labels (short,
# bold, larger-than-body text that isn't a header at all — e.g. "CPU",
# "Yes", "(Client)", "502").
_NUMBERED_HEADER_PATTERN = re.compile(r"^(\d+\.\d+(\.\d+)*\.?|\d+\.|[A-Z]\.)\s+\S")

# Fallback signal, used ONLY if a document has zero numbered headers
# anywhere in it (the unlikely case one of the 7 docs uses pure styled
# headers with no numbering at all). Tightened from the original
# version: requires size AND bold together, not either alone.
HEADER_SIZE_RATIO = 1.15
_BOLD_FLAG = 1 << 4  # PyMuPDF font flags bit for bold


@dataclass
class Section:
    header: str | None  # None if this section has no detected header (fallback case)
    text: str
    page_number: int  # page the section STARTS on


@dataclass
class Chunk:
    text: str
    section_header: str | None
    page_number: int


def _get_encoding():
    # cl100k_base matches GPT-4o-mini/GPT-5-mini-family tokenization
    # closely enough for chunk-sizing purposes (exact tokenizer parity
    # isn't required here — this only needs to keep chunks in the right
    # ballpark, not hit an exact model-specific token count).
    return tiktoken.get_encoding("cl100k_base")


def _token_length(text: str, encoding) -> int:
    return len(encoding.encode(text))


def _detect_body_font_size(doc: fitz.Document) -> float:
    """
    Body-text baseline = the most common span font size across the
    document. Used as the reference point for HEADER_SIZE_RATIO, since
    an absolute point size isn't reliable across different document
    templates.
    """
    from collections import Counter

    sizes: Counter[float] = Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        sizes[round(span["size"], 1)] += len(span["text"])

    if not sizes:
        return 10.0  # arbitrary safe default; no text at all is a degenerate case
    return sizes.most_common(1)[0][0]


def _is_numbered_header_line(line_text: str) -> bool:
    """Primary signal — §8.2.1's original spec: numbered section headers."""
    text = line_text.strip()
    return bool(text) and len(text) < 120 and bool(_NUMBERED_HEADER_PATTERN.match(text))


def _is_typographic_header_span(span: dict, body_size: float) -> bool:
    """
    Fallback signal ONLY — used at the document level when a document
    has no numbered headers at all. Requires size AND bold together
    (tightened from OR), which is still an imperfect heuristic — it's a
    fallback for docs without numbering, not the primary mechanism.
    """
    is_larger = span["size"] >= body_size * HEADER_SIZE_RATIO
    is_bold = bool(span["flags"] & _BOLD_FLAG)
    text = span["text"].strip()
    return bool(text) and len(text) < 120 and is_larger and is_bold


def _is_monospace_span(span: dict) -> bool:
    return "Courier" in span["font"]


def _first_nonblank_span(spans: list[dict]) -> dict | None:
    for s in spans:
        if s["text"].strip():
            return s
    return None


def _is_label_line(line_text: str, spans: list[dict]) -> bool:
    """
    A short bold caption immediately introducing a following code/command
    block — e.g. "Python Example:", "Step 2: Install Docker". Confirmed
    empirically (span["font"]/span["flags"]) across the corpus: these
    lines are consistently bold, non-monospace, and always contain a
    colon somewhere (either trailing, as in "Token Response:", or
    mid-line, as in "Step 2: Install Docker").

    Bold-and-colon alone is NOT sufficient — the same styling is used
    throughout the corpus for unrelated field labels that are never
    followed by code (document-metadata blocks like "Version:"/"Owner:",
    escalation labels like "Level 1: Security Team", "Base URL:"). The
    signal that actually isolates the code-example idiom is checked
    separately by the caller: whether the line immediately following one
    of these is itself monospace (Courier) text.
    """
    text = line_text.strip()
    if not text or len(text) >= 100 or ":" not in text:
        return False
    if _is_numbered_header_line(text):
        return False
    span = _first_nonblank_span(spans)
    return span is not None and bool(span["flags"] & _BOLD_FLAG) and not _is_monospace_span(span)


def split_into_sections(doc: fitz.Document) -> list[Section]:
    """
    Level 1 — structure split. Walks every page's text spans, treats a
    detected header span as a new section boundary, and accumulates
    everything until the next header into that section's text.

    Fallback: if zero headers are detected across the whole document,
    returns a single Section with header=None covering the entire
    document — the caller then skips straight to level-2 recursive
    splitting on that one section, per §8.2.1's stated fallback.
    """
    body_size = _detect_body_font_size(doc)

    # First pass: does this document have ANY numbered headers at all?
    # If yes, numbered-prefix detection is used exclusively for the
    # whole document (it's a reliable, low-false-positive signal once
    # present). If a document has none anywhere, fall back to the
    # typographic heuristic for that whole document instead — never mix
    # the two signals within one document, since that would make the
    # boundary between "using the fallback" and "using the real signal"
    # unpredictable page to page.
    has_numbered_headers = False
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                line_text = "".join(s["text"] for s in line.get("spans", []))
                if _is_numbered_header_line(line_text):
                    has_numbered_headers = True
                    break
            if has_numbered_headers:
                break
        if has_numbered_headers:
            break

    sections: list[Section] = []
    current_header: str | None = None
    current_text_parts: list[str] = []
    current_start_page: int = 1
    in_header_run = False  # True while accumulating a (possibly multi-line) header
    header_run_signature: tuple[float, bool] | None = None  # (size, is_bold) of the line that started the current header

    def _flush() -> None:
        text = "".join(current_text_parts).strip()
        if text:
            sections.append(Section(header=current_header, text=text, page_number=current_start_page))

    def _line_font_signature(spans: list[dict]) -> tuple[float, bool] | None:
        for s in spans:
            if s["text"].strip():
                return (round(s["size"], 1), bool(s["flags"] & _BOLD_FLAG))
        return None

    # Flattened once (rather than the nested page/block/line loop used
    # above for has_numbered_headers) so label detection below can look
    # one line ahead — deciding whether a bold "Label:" line is a
    # code-example caption requires knowing whether the line right after
    # it is monospace, which needs lookahead the nested-loop form doesn't
    # give for free.
    flat_lines: list[tuple[int, str, list[dict]]] = []
    for page_index, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                line_text = "".join(s["text"] for s in spans)
                flat_lines.append((page_index, line_text, spans))

    def _next_nonblank_spans(start_idx: int) -> list[dict] | None:
        for j in range(start_idx + 1, len(flat_lines)):
            _, text, spans = flat_lines[j]
            if text.strip():
                return spans
        return None

    for i, (page_index, line_text, spans) in enumerate(flat_lines):
        line_sig = _line_font_signature(spans)

        starts_new_header = (
            _is_numbered_header_line(line_text) if has_numbered_headers
            else bool(spans) and all(_is_typographic_header_span(s, body_size) for s in spans if s["text"].strip())
        )

        # A continuation line of an already-started header carries
        # NO number of its own (only the first physical line does)
        # — so it's recognized by matching font signature against
        # the line that started the header, not by the header
        # pattern again. This is what makes a wrapped title's
        # second line attach correctly instead of falling through
        # to "not a header" and ending the run prematurely.
        is_continuation = (
            in_header_run
            and line_sig is not None
            and line_sig == header_run_signature
            and bool(line_text.strip())
        )

        if is_continuation:
            current_header = f"{current_header} {line_text.strip()}"
        elif starts_new_header and line_text.strip():
            _flush()
            current_header = line_text.strip()
            current_text_parts = []
            current_start_page = page_index
            header_run_signature = line_sig
            in_header_run = True
        else:
            in_header_run = False
            header_run_signature = None
            # A code-example caption ("Python Example:", "Step 2: Install
            # Docker") immediately followed by a monospace block: insert a
            # paragraph break ahead of it so multiple back-to-back
            # examples don't glue into one run with zero boundary between
            # them (§8.2.1 investigation — confirmed via real chunk
            # output). A soft \n\n boundary, not a separate sub-section:
            # each example is only a few lines, and giving the level-2
            # recursive splitter (which already prioritizes \n\n as its
            # first separator) a real boundary to catch is enough to fix
            # the glued-text symptom — forcing every short example into
            # its own chunk would fragment retrieval context for no
            # benefit when the whole labeled group already fits in one
            # chunk, while still letting the splitter break exactly here
            # when a section (e.g. an 8-step install run) is long enough
            # that it must split somewhere anyway.
            next_spans = _next_nonblank_spans(i) if _is_label_line(line_text, spans) else None
            if next_spans is not None and (s := _first_nonblank_span(next_spans)) is not None and _is_monospace_span(s):
                current_text_parts.append("\n" + line_text + "\n")
            else:
                current_text_parts.append(line_text + "\n")

    _flush()

    if not sections:
        # Fallback: no structure detected anywhere -> whole doc, one section
        full_text = "".join(page.get_text() for page in doc).strip()
        return [Section(header=None, text=full_text, page_number=1)]

    return sections


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    """
    Level 2 — recursive sub-split within each section, ~400 tokens /
    15% overlap, on the \\n\\n -> \\n -> sentence -> space separator
    hierarchy. Each resulting chunk inherits its section's header.
    """
    encoding = _get_encoding()
    overlap_tokens = int(CHUNK_TARGET_TOKENS * CHUNK_OVERLAP_RATIO)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TARGET_TOKENS,
        chunk_overlap=overlap_tokens,
        length_function=lambda text: _token_length(text, encoding),
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[Chunk] = []
    for section in sections:
        for piece in splitter.split_text(section.text):
            piece = piece.strip()
            if piece:
                chunks.append(
                    Chunk(text=piece, section_header=section.header, page_number=section.page_number)
                )
    return chunks


def extract_and_chunk(pdf_path: str) -> list[Chunk]:
    """Full level-1 + level-2 pipeline for one PDF. Does not embed or
    insert anything — that's pipeline.py's job, this module only
    produces chunk text + metadata."""
    doc = fitz.open(pdf_path)
    try:
        sections = split_into_sections(doc)
        return chunk_sections(sections)
    finally:
        doc.close()
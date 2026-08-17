"""
app/ingestion/extract_tables.py

Table extraction, per §8.2's `tables` row: "raw JSON + text serialization
for embedding" (e.g. the SLA response-time-by-severity table).

Tooling decision (already made, not revisited here): §8.2 lists
pdfplumber/camelot as the table-tooling options, but this file uses
`fitz.find_tables()` (PyMuPDF's own built-in table detection) instead —
validated in prior work on a different project, where it correctly pulled
financial tables with no separate table library, and it avoids camelot's
external Ghostscript system dependency entirely. PyMuPDF is already a
project dependency (extract_text.py already imports `fitz`), so nothing
new is added to requirements.txt for this file.

Cross-page stitching (added after the original "known limitation, not
attempted" disclosure proved to matter in practice — confirmed on the
real corpus, not hypothetical): find_tables() operates per page, so a
table split across a page break comes back as two separate Table
objects, and PyMuPDF has no way to know the second is a continuation —
it mis-detects that fragment's first *data* row as a header row. Gated
by three signals, chosen and validated against real bbox coordinates
across the whole 7-document corpus (see _stitch_across_page_break()'s
docstring for the actual numbers), not guessed.

Snapshot-immediately requirement, found the hard way: fitz's Table
objects go stale once find_tables() has been called again on a later
page — .extract()/.bbox/.header on an "old" Table silently return
empty/wrong data rather than raising, so a naive "gather every page's
tables first, process after" implementation (needed for stitching's
next-page lookahead) quietly corrupted every table in the document, not
just the stitched ones. Fixed by converting every fitz Table into a
plain-Python _TableSnapshot the moment its own page's find_tables() call
returns, before moving to the next page — all stitching/serialization
logic below operates on those snapshots, never on a live Table object
from a page other than the one just visited.
"""

import re
from dataclasses import dataclass

import fitz  # PyMuPDF

from app.ingestion.extract_text import Section, split_into_sections
from app.ingestion.hashing import hash_text

# Deliberately tight — matches only a real tag shape (`<`, optional `/`,
# a letter, then word characters, optional trailing `/`, `>`), NOT any
# run of characters between a stray `<` and a later `>`. Found the hard
# way: the original `<[^>]+>` was so loose that on any table whose own
# cell text legitimately contains both `<`/`>` as comparison operators
# (extremely common in metrics/threshold tables — "< 4hrs", "> 70%"),
# `[^>]+` (which matches newlines too) would span from that stray `<`
# clean through to the *next* `>` anywhere later in the markdown string —
# potentially the closing bracket of an unrelated `<br>` tag several rows
# down — silently eating entire rows of real cell content. Confirmed via
# real extracted data: this corrupted the ITIL "Key Incident Metrics" and
# Security "Severity" tables into scrambled multi-row messes, and quietly
# clipped text in the SLA and Performance tables too. Validated against
# the real corpus: this pattern matches every genuine `<br>`/`<token>`
# tag PyMuPDF's to_markdown() emits with zero change in match count, and
# zero false matches on any of the corpus's real "< Npt" / "> N%"
# comparison-operator cells.
_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*\s*/?>")

# ZapfDingbats status-icon glyphs, found across 4 of the 7 real course
# documents (same generation pipeline/template) rendering as raw,
# non-printable control characters in PyMuPDF's extracted text — genuine
# corrupted DATA, confirmed via repr() (not a console-display artifact
# like the earlier bullet-point/"o with grave" case). Visually confirmed
# by rendering the source PDF regions to an image, not guessed: \x13 is a
# check mark (Product_Installation_Setup_Guide.pdf p.5's "Support
# Status" column, Security_Vulnerability_Response_Policy.pdf p.3's
# "Encouraged" column header), \x17 is an X mark (same Security doc
# page's "Prohibited" column header). Safe to substitute unconditionally,
# unlike the font's third observed glyph (renders as a bare capital "I")
# — that code point collides with the ordinary Latin letter used
# throughout normal prose everywhere else in the corpus, and nothing in
# find_tables()'s plain-text output carries per-character font
# information to safely tell "the letter I" apart from "this font's
# square-icon glyph that happens to reuse code point 0x49" — see
# _table_has_unresolved_dingbat_glyphs() below for how that case is
# flagged instead of guessed at.
_DINGBAT_SUBSTITUTIONS = {
    "\x13": "✓",  # check mark
    "\x17": "✗",  # x mark / ballot X
}
_DINGBAT_FONT = "ZapfDingbats"

# ---------------------------------------------------------------------------
# Headerless axis-labeled matrix detection (e.g. ITIL_Incident_Management_
# Summary.pdf p.3's Urgency x Impact -> Priority grid)
# ---------------------------------------------------------------------------
# find_tables() detects this table's inner grid of P0-P3 codes correctly as
# *cells*, but has no header row of its own to find (all 9 cells share an
# identical font signature — confirmed via span["font"]/["size"]/["flags"],
# same technique used elsewhere in this codebase), so it defaults to
# promoting the first data row to a header, discarding it as real data and
# leaving the remaining rows meaningless without their row/column context.
# The row/column axis labels ("Low/Medium/High", "High/Medium/Low") sit
# entirely outside the detected bbox on two sides, so they're never part of
# the table at all — not misattributed, just never looked at.
#
# An earlier, broader detection signal (header row's font signature
# identical to the body rows') was tested against all 47 real tables in the
# 7-document corpus and fired on 8 unrelated ones — some already-correct
# minimalist headers (a header row that's real, meaningful text but just
# isn't visually bolder than the body), some already-handled cross-page
# stitching continuations (_stitch_across_page_break's whole reason for
# existing). Neither needed or would have safely tolerated an axis-label
# search. This narrower, two-part signal — combining "every cell is short
# and code-like" with "the table itself is small and roughly square" — was
# tested the same way and found exactly ONE match in the whole corpus: this
# table. Either condition alone is too broad; together, they're specific
# enough to act on safely.
_MAX_MATRIX_CELL_LEN = 3  # e.g. "P3", "P0" - genuinely short codes, not prose
_MAX_MATRIX_DIMENSION = 5  # candidate table must itself be small
_MAX_LABEL_TEXT_LEN = 20  # a real per-row/-column label is a word or two, not a sentence
_ARROW_CHARS = "→↓↑←"  # marks an axis TITLE ("IMPACT →"), not a per-column/-row VALUE label

# Margins sized from the one real instance, with real headroom on both
# sides (not a hairline fit): the observed column labels/axis title sit
# 12-41pt above the table's own bbox top, comfortably inside a 60pt search;
# the observed row labels/axis title sit 15-85pt left of the bbox's left
# edge, comfortably inside a 120pt search — both well clear of the
# descriptive paragraph one line further up (which ends 8.6pt above where
# the top search starts) and of unrelated content further left on the page.
_AXIS_LABEL_TOP_MARGIN_PT = 60.0
_AXIS_LABEL_LEFT_MARGIN_PT = 120.0


def _is_matrix_candidate(all_rows_as_data: list[list], col_count: int) -> bool:
    """See this module's "Headerless axis-labeled matrix detection" comment
    above for why both conditions, together, are the safe trigger."""
    all_cells = [c for row in all_rows_as_data for c in row]
    if not all_cells:
        return False
    all_short_and_codelike = all(
        isinstance(c, str) and 0 < len(c.strip()) <= _MAX_MATRIX_CELL_LEN for c in all_cells
    )
    row_count = len(all_rows_as_data)
    roughly_square = (
        row_count <= _MAX_MATRIX_DIMENSION
        and col_count <= _MAX_MATRIX_DIMENSION
        and abs(row_count - col_count) <= 1
    )
    return all_short_and_codelike and roughly_square


def _is_short_label_text(text: str) -> bool:
    text = text.strip()
    return bool(text) and len(text) <= _MAX_LABEL_TEXT_LEN and not any(a in text for a in _ARROW_CHARS)


def _is_axis_title_text(text: str) -> bool:
    text = text.strip()
    return bool(text) and len(text) <= _MAX_LABEL_TEXT_LEN and any(a in text for a in _ARROW_CHARS)


def _nearby_lines(
    page, search_rect: "fitz.Rect", exclude_rects: list["fitz.Rect"]
) -> list[tuple[str, "fitz.Rect"]]:
    """Text lines inside `search_rect`, skipping anything that overlaps a
    known table on the page (another real table sitting in the search
    margin shouldn't be misread as axis labels)."""
    lines = []
    for block in page.get_text("dict", clip=search_rect)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line.get("spans", [])).strip()
            if not text:
                continue
            rect = fitz.Rect(line["bbox"])
            if any(rect.intersects(ex) for ex in exclude_rects):
                continue
            lines.append((text, rect))
    return lines


def _match_to_centers(candidates: list[tuple[str, "fitz.Rect"]], centers: list[float], axis: str) -> list[str] | None:
    """Nearest-center assignment: each candidate line is matched to
    whichever column x-center or row y-center it sits closest to. Returns
    None unless the match is completely clean — exactly one candidate per
    center, none left over, none doubled up. A partial or ambiguous match
    is worse than none at all: it would silently mislabel a row/column
    rather than honestly leaving the table as find_tables() produced it."""
    if len(candidates) != len(centers):
        return None
    assigned: dict[int, str] = {}
    for text, rect in candidates:
        pos = (rect.x0 + rect.x1) / 2 if axis == "x" else (rect.y0 + rect.y1) / 2
        nearest_index = min(range(len(centers)), key=lambda i: abs(centers[i] - pos))
        if nearest_index in assigned:
            return None  # two labels claimed the same slot - ambiguous, don't guess
        assigned[nearest_index] = text
    return [assigned[i] for i in range(len(centers))] if len(assigned) == len(centers) else None


def _find_axis_labels(
    page, table_bbox: tuple[float, float, float, float], row_count: int, col_count: int,
    other_table_bboxes: list[tuple[float, float, float, float]],
) -> tuple[list[str] | None, list[str] | None, str | None]:
    """
    Searches above and to the left of a matrix-candidate's bbox for
    per-column and per-row axis labels, matched to each column/row by
    geometry (nearest x-/y-center) — not a keyword match, so this isn't
    tied to "IMPACT"/"URGENCY" specifically, just to the two-sided
    external-label SHAPE. Returns (row_labels, column_labels, corner_text):
    the first two are None (never a partial guess) unless every row/column
    got exactly one clean match; corner_text is a best-effort axis-title
    annotation for the corner cell, cosmetic only.
    """
    bbox = fitz.Rect(table_bbox)
    exclude = [fitz.Rect(b) for b in other_table_bboxes]

    col_width = bbox.width / col_count
    col_centers = [bbox.x0 + col_width * (i + 0.5) for i in range(col_count)]
    row_height = bbox.height / row_count
    row_centers = [bbox.y0 + row_height * (i + 0.5) for i in range(row_count)]

    top_search = fitz.Rect(bbox.x0, bbox.y0 - _AXIS_LABEL_TOP_MARGIN_PT, bbox.x1, bbox.y0)
    left_search = fitz.Rect(bbox.x0 - _AXIS_LABEL_LEFT_MARGIN_PT, bbox.y0, bbox.x0, bbox.y1)

    top_lines = _nearby_lines(page, top_search, exclude)
    left_lines = _nearby_lines(page, left_search, exclude)

    # Lines containing an arrow character are unambiguously part of the
    # axis title, never a per-row/-column value — excluded from label
    # candidates outright, kept for the (cosmetic-only) corner text.
    column_candidates = [(text, rect) for text, rect in top_lines if _is_short_label_text(text)]
    row_candidates = [(text, rect) for text, rect in left_lines if _is_short_label_text(text)]
    top_arrow_texts = [text for text, _ in top_lines if _is_axis_title_text(text)]
    left_arrow_texts = [text for text, _ in left_lines if _is_axis_title_text(text)]

    # An axis title isn't always ONE line containing the arrow — PyMuPDF
    # sometimes segments a title word and its arrow glyph into separate
    # lines (confirmed on the real page: "URGENCY" and "↓" land as two
    # distinct lines, so "URGENCY" alone has no arrow character and would
    # otherwise be miscounted as a 4th row-label candidate against only 3
    # real rows). Tried gauging this by "further from the table than the
    # nearest confirmed title line" and rejected it — with a two-line
    # title split across a word and a narrow arrow glyph, the two pieces
    # don't reliably order that way (the arrow glyph here is a narrower,
    # not-further span than "URGENCY" itself). What's actually reliable:
    # the real per-row/-column labels form a tight cluster of identical
    # gap-from-table (they're right-aligned to the same edge, by
    # construction of a grid) — a lone extra candidate sitting well
    # outside that cluster is the title word, not a label. Only acts when
    # there's exactly ONE extra candidate AND it's an unambiguous outlier
    # (>1.5x the next-largest gap) — anything messier is left alone and
    # the subsequent exact-count match below fails closed instead.
    def _drop_title_outlier(candidates, gap_fn, expected_count: int):
        if len(candidates) != expected_count + 1:
            return candidates, None
        gaps = sorted(((gap_fn(rect), i) for i, (_, rect) in enumerate(candidates)), reverse=True)
        if gaps[0][0] > gaps[1][0] * 1.5:
            dropped_text = candidates[gaps[0][1]][0]
            return [c for i, c in enumerate(candidates) if i != gaps[0][1]], dropped_text
        return candidates, None

    column_candidates, dropped_col_title = _drop_title_outlier(
        column_candidates, lambda r: bbox.y0 - r.y1, col_count
    )
    row_candidates, dropped_row_title = _drop_title_outlier(
        row_candidates, lambda r: bbox.x0 - r.x1, row_count
    )

    top_title = " ".join(([dropped_col_title] if dropped_col_title else []) + top_arrow_texts)
    left_title = " ".join(([dropped_row_title] if dropped_row_title else []) + left_arrow_texts)
    corner_text = " / ".join(t for t in (left_title, top_title) if t) or None

    column_labels = _match_to_centers(column_candidates, col_centers, axis="x")
    row_labels = _match_to_centers(row_candidates, row_centers, axis="y")

    return row_labels, column_labels, corner_text


# Calibrated against real bbox coordinates across all 7 documents, not
# guessed (see _stitch_across_page_break()'s docstring for the full
# validation). Confirmed continuations observed bottom_gap in [59, 86]pt
# and top_gap in [51, 77]pt; the nearest confirmed NON-continuation with
# matching column count sat at top_gap=175pt — a ~95pt margin of
# separation from the real cases, so these thresholds have real headroom
# on both sides, not a hairline cutoff.
_BOTTOM_MARGIN_PT = 100.0
_TOP_MARGIN_PT = 80.0


def _strip_html_markup(text: str) -> str:
    """
    PyMuPDF's Table.to_markdown() emits literal HTML tags for in-cell line
    breaks (`<br>`), and potentially other inline tags for other cell
    content. That's harmless in raw_json (untouched, structured data) but
    undesirable in text_serialization specifically, since that string is
    what gets hashed (§8.3) and embedded (§8.2) — markup tags sitting in
    embedded text pollute the embedding for no benefit. Generic tag strip
    (not just `<br>` specifically) so any other inline tag the renderer
    emits is caught too, not just the one we've observed. Only the
    (occasional) runs of spaces left behind by a removed tag are
    collapsed — newlines between table rows are deliberately left alone.
    """
    cleaned = _HTML_TAG_RE.sub(" ", text)
    return re.sub(r"[ \t]+", " ", cleaned)


def _substitute_dingbat_glyphs(value):
    """Applies the two visually-confirmed-safe ZapfDingbats substitutions
    to a single cell value. Only touches `str` values — extract()/
    to_markdown() cells are always str in practice, but a plain isinstance
    guard costs nothing and avoids assuming that everywhere this is called."""
    if isinstance(value, str):
        for raw, replacement in _DINGBAT_SUBSTITUTIONS.items():
            value = value.replace(raw, replacement)
    return value


def _unresolved_dingbat_codes(page, bbox: tuple[float, float, float, float]) -> set[str]:
    """
    Scans the page region a table occupies for ZapfDingbats-font
    characters that AREN'T one of the two visually-confirmed-safe codes
    above. Used only to flag a table (has_unresolved_symbols), never to
    guess a substitution — this font's third observed code point renders
    as a bare capital "I", which is indistinguishable from the ordinary
    letter once it's plain text with no font attached (§ this module's
    _DINGBAT_SUBSTITUTIONS comment). Reading font info straight from the
    page here, not from find_tables()'s output, since Table.extract()/
    to_markdown() never carry per-character font metadata at all.
    """
    codes: set[str] = set()
    rect = fitz.Rect(bbox)
    for block in page.get_text("dict", clip=rect)["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["font"] != _DINGBAT_FONT:
                    continue
                for ch in span["text"]:
                    if ch not in _DINGBAT_SUBSTITUTIONS:
                        codes.add(ch)
    return codes


@dataclass
class ExtractedTable:
    raw_json: list[dict[str, str | None]]  # body rows only, keyed by column header
    text_serialization: str  # Markdown table — this is what gets embedded (§8.2)
    page_number: int
    section_header: str | None
    asset_hash: str  # hash_text(text_serialization), per §8.3's ingested_assets.asset_hash
    possibly_truncated: bool = False  # True: this fragment sat near a page bottom but a
    # matching continuation on the next page couldn't be confirmed — an honest
    # "might be incomplete" signal, not a guess dressed up as certainty.
    has_unresolved_symbols: bool = False  # True: this table's source region contains a
    # ZapfDingbats (or similar icon-font) glyph this module doesn't have a
    # visually-confirmed-safe substitution for — the row/column structure is
    # correct, but at least one cell's plain text may not reflect the icon
    # actually shown in the PDF (e.g. a status icon coming through as a bare
    # letter). An honest "some cell content may not read as intended" signal,
    # conceptually different from possibly_truncated (nothing here is missing
    # rows — the concern is cell CONTENT, not table completeness).


@dataclass
class _TableSnapshot:
    """Everything needed from one fitz Table, captured the instant its
    own page's find_tables() call returns — see module docstring for why
    this can't be deferred."""

    bbox: tuple[float, float, float, float]
    col_count: int
    header_names: list[str]
    body_rows: list[list]  # extract() minus the header row (if not external)
    all_rows_as_data: list[list]  # every row as data — for merging a continuation fragment
    markdown: str  # table.to_markdown(), already resolved to a plain string
    has_unresolved_symbols: bool  # see ExtractedTable.has_unresolved_symbols


def _snapshot(table, page, other_table_bboxes: list[tuple[float, float, float, float]]) -> _TableSnapshot:
    header_names = [
        _substitute_dingbat_glyphs(name) if name else f"column_{i}"
        for i, name in enumerate(table.header.names)
    ]
    extracted = [[_substitute_dingbat_glyphs(cell) for cell in row] for row in table.extract()]
    if table.header.external:
        body_rows = extracted
        all_rows_as_data = [header_names] + extracted
    else:
        # Header row is included as extract()'s first row.
        body_rows = extracted[1:]
        all_rows_as_data = extracted
    markdown = _substitute_dingbat_glyphs(table.to_markdown())
    col_count = table.col_count
    bbox = tuple(table.bbox)

    # Headerless axis-labeled matrix reconstruction — see this module's
    # dedicated comment block above _is_matrix_candidate() for the full
    # rationale and corpus validation. Only ever touches a table matching
    # BOTH narrow conditions, and only replaces anything if a completely
    # clean row+column label match is found; otherwise the table is left
    # exactly as find_tables() produced it.
    if _is_matrix_candidate(all_rows_as_data, col_count):
        row_count = len(all_rows_as_data)
        row_labels, column_labels, corner_text = _find_axis_labels(
            page, bbox, row_count, col_count, other_table_bboxes
        )
        if row_labels is not None and column_labels is not None:
            header_names = [corner_text or ""] + column_labels
            all_rows_as_data = [[label] + row for label, row in zip(row_labels, all_rows_as_data)]
            body_rows = all_rows_as_data
            markdown = _rows_to_markdown(header_names, all_rows_as_data)
            col_count = col_count + 1

    return _TableSnapshot(
        bbox=bbox,
        col_count=col_count,
        header_names=header_names,
        body_rows=body_rows,
        all_rows_as_data=all_rows_as_data,
        markdown=markdown,
        has_unresolved_symbols=bool(_unresolved_dingbat_codes(page, table.bbox)),
    )


def _section_header_for_page(sections: list[Section], page_number: int) -> str | None:
    """
    Attributes a page to whichever section is "in effect" by that page:
    the last section (in document order) whose own start page is <= this
    page. `sections` comes straight from extract_text.py's
    split_into_sections(), which walks the document page-by-page, so the
    list is already ordered by non-decreasing page_number — a single
    forward scan, keeping the latest match, is enough.

    This also resolves two edge cases for free, without special-casing:
      - a table on a page before any header is ever detected -> the
        first section (header=None in the no-structure/fallback case,
        or the pre-first-header section otherwise) always starts at
        page_number=1, so it's <= any table page and is picked correctly.
      - two section headers landing on the very same page as a table ->
        whichever section starts closer to (at or before) the table's
        page wins, rather than building explicit start/end page ranges
        that can come out empty when consecutive sections share a page.
    """
    current_header: str | None = None
    for section in sections:
        if section.page_number <= page_number:
            current_header = section.header
        else:
            break
    return current_header


def _rows_to_markdown(header_names: list[str], rows: list[list]) -> str:
    """
    Builds the merged table's Markdown serialization directly, rather
    than reusing fitz's Table.to_markdown() (a method on one real Table
    object — there's no such method for a synthetic merged table, and no
    live Table object to call it on by this point anyway). Plain GFM
    table, no bold-first-column styling — simpler to get right than
    replicating fitz's private rendering choices, and arguably better for
    embedding text anyway (less markup noise). Used only for the merged
    (stitched) case; every other table keeps its original
    Table.to_markdown() output, captured in its _TableSnapshot.
    """
    def _cell(value) -> str:
        return "" if value is None else str(value).replace("\n", " ")

    header_line = "|" + "|".join(header_names) + "|"
    separator_line = "|" + "|".join("---" for _ in header_names) + "|"
    row_lines = ["|" + "|".join(_cell(c) for c in row) + "|" for row in rows]
    return "\n".join([header_line, separator_line, *row_lines]) + "\n\n"


def _stitch_across_page_break(
    fragment: _TableSnapshot, page_height: float, next_page_tables: list[_TableSnapshot]
) -> tuple[list[dict[str, str | None]], str] | None:
    """
    Three-signal check, all required, before treating `fragment` (the
    last table on its page) and the next page's first table as one
    continuous table:

      1. `fragment`'s bbox bottom is within _BOTTOM_MARGIN_PT of its own
         page's bottom edge — a table that ends well above the bottom
         margin had room to keep going and simply didn't; it isn't a
         truncation candidate at all.
      2. The next page's first table has the same column count as
         `fragment` — different column counts can't be the same table.
      3. That next-page table's bbox top is within _TOP_MARGIN_PT of its
         page's top edge — a genuine continuation resumes immediately;
         one that starts well down the next page sat behind unrelated
         content in between and is a different table.

    Thresholds validated against real bbox coordinates, not guessed: run
    across all 7 real course documents, checking bottom_gap/top_gap/
    column-count at every page-to-page table boundary in the corpus.
    Every one of the 6 pairs that satisfied all three signals turned out
    to be a genuine continuation on inspection (matching subject matter,
    a fitz-mis-detected "header" that's actually the next data row) —
    zero false positives found. One near-miss confirmed the discriminating
    power of signal 3 specifically: API_Error_Codes_Troubleshooting_
    Handbook.pdf's own page 1->2 boundary has matching column counts
    (4 and 4) and a passable bottom_gap (86pt), but the next table's
    top_gap is 175pt — correctly excluded as the two unrelated tables
    they actually are (a rate-limiting table and an unrelated input-
    validation table that merely happen to share a column count).

    Returns (merged_raw_json, merged_text_serialization) if all three
    signals fire, else None.
    """
    if not next_page_tables:
        return None

    bottom_gap = page_height - fragment.bbox[3]
    if bottom_gap > _BOTTOM_MARGIN_PT:
        return None

    continuation = next_page_tables[0]
    if continuation.col_count != fragment.col_count:
        return None

    top_gap = continuation.bbox[1]
    if top_gap > _TOP_MARGIN_PT:
        return None

    merged_rows = fragment.body_rows + continuation.all_rows_as_data
    merged_raw_json = [dict(zip(fragment.header_names, row)) for row in merged_rows]
    merged_serialization = _strip_html_markup(_rows_to_markdown(fragment.header_names, merged_rows))
    return merged_raw_json, merged_serialization


def extract_tables(pdf_path: str) -> list[ExtractedTable]:
    """
    Extracts every table `fitz.find_tables()` can detect, one
    ExtractedTable per table (two page fragments that stitch together
    become one). Extraction only — does not embed, insert into the DB,
    or call any LLM (that's pipeline.py's job later).

    section_header attribution reuses extract_text.py's
    split_into_sections() wholesale (its numbered-header primary signal
    + typographic fallback, already tuned there) instead of
    reimplementing similar-but-different detection logic in this file.
    Chosen over importing the individual per-line detection helpers
    directly, because those helpers are only half the picture — the
    stateful multi-page walk that turns them into ordered Section
    boundaries (has_numbered_headers document-level pass, multi-line
    header continuation tracking, the fallback path) is the part that
    would actually need duplicating, not just the per-line predicates.
    Calling split_into_sections() once and doing a page-range lookup
    against its output keeps this file trivially consistent with
    extract_text.py by construction: any future retuning of header
    detection there (already retuned twice) applies here automatically,
    with zero logic to keep in sync by hand.
    """
    doc = fitz.open(pdf_path)
    try:
        sections = split_into_sections(doc)

        # Snapshotted per page, immediately (see module docstring on why):
        # stitching needs to look at the next page's first table before
        # the current page's last one can be finalized, but a fitz Table
        # object is only safe to read from during its own page's pass.
        # Every other table's bbox on the SAME page is gathered here too
        # (from this one find_tables() call, not a second one — see the
        # module docstring's staleness warning) so the axis-label search
        # inside _snapshot() can exclude real tables sitting in its
        # search margin from being misread as axis labels.
        pages_tables: list[list[_TableSnapshot]] = []
        for page in doc:
            page_tables = page.find_tables().tables
            page_bboxes = [tuple(t.bbox) for t in page_tables]
            pages_tables.append(
                [
                    _snapshot(t, page, [b for j, b in enumerate(page_bboxes) if j != i])
                    for i, t in enumerate(page_tables)
                ]
            )
        page_heights = [page.rect.height for page in doc]

        results: list[ExtractedTable] = []
        consumed_as_continuation: set[int] = set()  # page indices whose 1st table was already merged in

        for page_index, tables in enumerate(pages_tables):
            page_number = page_index + 1
            section_header = _section_header_for_page(sections, page_number)

            for table_index, snap in enumerate(tables):
                if table_index == 0 and page_index in consumed_as_continuation:
                    continue  # already folded into the previous page's stitched table

                is_last_on_page = table_index == len(tables) - 1
                has_next_page = page_index + 1 < len(pages_tables)

                if is_last_on_page and has_next_page:
                    bottom_gap = page_heights[page_index] - snap.bbox[3]
                    near_bottom = bottom_gap <= _BOTTOM_MARGIN_PT

                    if near_bottom:
                        stitched = _stitch_across_page_break(
                            snap, page_heights[page_index], pages_tables[page_index + 1]
                        )
                        if stitched is not None:
                            merged_raw_json, merged_serialization = stitched
                            continuation = pages_tables[page_index + 1][0]
                            results.append(
                                ExtractedTable(
                                    raw_json=merged_raw_json,
                                    text_serialization=merged_serialization,
                                    page_number=page_number,
                                    section_header=section_header,
                                    asset_hash=hash_text(merged_serialization),
                                    possibly_truncated=False,
                                    has_unresolved_symbols=snap.has_unresolved_symbols or continuation.has_unresolved_symbols,
                                )
                            )
                            consumed_as_continuation.add(page_index + 1)
                            continue

                        # Near the bottom, but the other two signals
                        # didn't confirm a continuation — an honest
                        # "might be incomplete" flag, not silently
                        # emitted as if it were certainly whole.
                        text_serialization = _strip_html_markup(snap.markdown)
                        results.append(
                            ExtractedTable(
                                raw_json=[dict(zip(snap.header_names, row)) for row in snap.body_rows],
                                text_serialization=text_serialization,
                                page_number=page_number,
                                section_header=section_header,
                                asset_hash=hash_text(text_serialization),
                                possibly_truncated=True,
                                has_unresolved_symbols=snap.has_unresolved_symbols,
                            )
                        )
                        continue

                # Not a stitching candidate at all (not last on its page,
                # no next page, or not near the bottom) — current behavior.
                text_serialization = _strip_html_markup(snap.markdown)
                results.append(
                    ExtractedTable(
                        raw_json=[dict(zip(snap.header_names, row)) for row in snap.body_rows],
                        text_serialization=text_serialization,
                        page_number=page_number,
                        section_header=section_header,
                        asset_hash=hash_text(text_serialization),
                        possibly_truncated=False,
                        has_unresolved_symbols=snap.has_unresolved_symbols,
                    )
                )

        return results
    finally:
        doc.close()

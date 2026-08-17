"""
app/ingestion/extract_diagrams.py

Diagram/flowchart extraction, per §8.2's `diagram_graphs` row: flowchart
content (error-resolution decision flow, incident lifecycle stages,
escalation hierarchy) parsed into a structured node-edge graph.

Investigated before writing this file (not assumed): all 7 course PDFs
have zero embedded raster images (confirmed in extract_images.py's own
testing), so any flowcharts here are native PDF vector graphics —
page.get_images() can't find them. Confirmed via page.get_drawings(),
against the real corpus, that they ARE real vector-drawn diagrams, not a
hypothetical: 9 diagrams found across all 7 documents, 3 of them matching
§8.2's own named examples exactly (the error-resolution decision flow in
API_Error_Codes_Troubleshooting_Handbook.pdf p1, the incident lifecycle
in ITIL_Incident_Management_Summary.pdf p1, the escalation hierarchy in
Security_Vulnerability_Response_Policy.pdf p4).

Detection signal (verified against real rendered pixmaps, not asserted):
a diagram region is a spatially-clustered group of page.get_drawings()
paths that (a) doesn't overlap any page.find_tables() bounding box — a
table region is flat rect fills with zero curves — and (b) contains at
least one curve-based path (a rounded node/circle) or one small
closed-triangle path (an arrowhead) as positive evidence it's really a
diagram and not, say, a decorative rounded callout box or a header bar.
"""

from dataclasses import dataclass

import fitz  # PyMuPDF
from pydantic import BaseModel, ConfigDict

from app.ingestion.extract_text import split_into_sections
from app.ingestion.extract_tables import _section_header_for_page
from app.llm.structured_output import call_llm_structured_vision
from app.ingestion.hashing import hash_bytes

# Two connected shapes belonging to the same diagram are rarely more than
# this far apart on these documents' typical node/connector spacing (see
# the SLA lifecycle diagram: circles ~40pt apart, connectors span the gap
# exactly). Tunable if a future document's diagram is drawn more sparsely.
_CLUSTER_GAP_PT = 12.0

# A closed path made only of short line segments within roughly this
# bounding box is an arrowhead, not a real shape — verified against the
# actual triangle paths PyMuPDF emits for connector arrowheads (a tight
# ~5x8pt rect in every real example checked).
_ARROWHEAD_MAX_SIDE_PT = 15.0

# How far outside the drawing-only cluster bbox to look for the diagram's
# own text labels (node text, numbers, "Yes"/"No" branch labels, a
# legend) before rendering — verified against the real corpus: labels
# sit a few points from their shape, never far enough to accidentally
# pull in unrelated body prose at typical paragraph spacing.
_TEXT_LABEL_MARGIN_PT = 30.0

DIAGRAM_RENDER_DPI = 150  # matches the resolution already used elsewhere for visual clarity


@dataclass
class ExtractedDiagram:
    image_bytes: bytes  # rendered region — NOT persisted to disk. §21's
    # diagram_graphs table has no blob_ref column (unlike images): the
    # persisted value is graph_json/caption, not the pixels, so there's
    # nothing to save a reference to once parse_diagram() has run.
    graph_json: dict | None  # {"nodes": [...], "edges": [...]} — None until parse_diagram()
    caption: str | None  # None until parse_diagram()
    diagram_type: str | None  # None until parse_diagram()
    page_number: int
    section_header: str | None
    asset_hash: str  # hash_bytes(image_bytes) — computed before any LLM call, §8.3


def _has_curve(d: dict) -> bool:
    return any(item[0] == "c" for item in d["items"])


def _is_small_closed_triangle(d: dict) -> bool:
    """Arrowhead signature: 2-3 straight-line segments forming a tight
    closed shape. Confirmed against real connector arrowheads in the SLA
    lifecycle diagram — each is exactly 3 'l' items in one drawing dict,
    rect ~5x8pt."""
    items = d["items"]
    if not (2 <= len(items) <= 3):
        return False
    if not all(item[0] == "l" for item in items):
        return False
    rect = d["rect"]
    return rect.width < _ARROWHEAD_MAX_SIDE_PT and rect.height < _ARROWHEAD_MAX_SIDE_PT


def _is_diagram_signal(d: dict) -> bool:
    return _has_curve(d) or _is_small_closed_triangle(d)


def _cluster_drawing_dicts(dicts: list[dict], gap: float = _CLUSTER_GAP_PT) -> list[list[dict]]:
    """Groups drawing dicts into spatially-connected clusters (each
    cluster = one candidate diagram, or one unrelated decoration) via
    union-find over pairwise bbox proximity. O(n^2) pairwise check is
    fine — n is a few dozen drawing paths per page at most."""
    n = len(dicts)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    def expanded(rect: fitz.Rect, g: float) -> fitz.Rect:
        return fitz.Rect(rect.x0 - g, rect.y0 - g, rect.x1 + g, rect.y1 + g)

    for i in range(n):
        for j in range(i + 1, n):
            # Both sides expanded, not just one: a straight connector
            # line has a zero-area (empty) rect by construction, and
            # fitz.Rect.intersects() always returns False against an
            # empty rect regardless of coordinate overlap — expanding
            # only dicts[i] left every connector line unable to bridge
            # anything, which is what silently fragmented one diagram
            # into several disconnected node clusters during testing.
            if expanded(dicts[i]["rect"], gap).intersects(expanded(dicts[j]["rect"], gap)):
                union(i, j)

    groups: dict[int, list[dict]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(dicts[i])
    return list(groups.values())


def _cluster_bbox(cluster: list[dict]) -> fitz.Rect:
    rect = fitz.Rect(cluster[0]["rect"])
    for d in cluster[1:]:
        rect |= d["rect"]
    return rect


def _detect_diagram_regions(page: fitz.Page) -> list[fitz.Rect]:
    """Returns one bbox per detected diagram region on this page (usually
    zero or one in this corpus, but a page could genuinely have more than
    one, so this doesn't assume exactly one)."""
    drawings = page.get_drawings()
    table_bboxes = [fitz.Rect(t.bbox) for t in page.find_tables().tables]

    def overlaps_any_table(rect: fitz.Rect) -> bool:
        return any(rect.intersects(tb) for tb in table_bboxes)

    # NOT filtered by rect area > 0: a pure horizontal or vertical
    # connector line has zero-area bbox by construction (width or height
    # is exactly 0), and these are exactly the links that bridge separate
    # node clusters into one connected diagram — dropping them here was a
    # real bug caught during testing (it fragmented one diagram into
    # several disconnected node-only clusters).
    non_table = [d for d in drawings if not overlaps_any_table(d["rect"])]
    if not non_table:
        return []

    regions: list[fitz.Rect] = []
    for cluster in _cluster_drawing_dicts(non_table):
        if any(_is_diagram_signal(d) for d in cluster):
            regions.append(_cluster_bbox(cluster))
    return regions


def _expand_with_nearby_text(page: fitz.Page, rect: fitz.Rect, margin: float = _TEXT_LABEL_MARGIN_PT) -> fitz.Rect:
    """Drawing commands alone don't include text — a node's label almost
    always sits just outside (or inside) the shape's own bbox, so the
    render region is widened to include any text span within `margin` of
    the drawing cluster, or the vision model would see unlabeled shapes."""
    search_area = fitz.Rect(rect.x0 - margin, rect.y0 - margin, rect.x1 + margin, rect.y1 + margin)
    result = fitz.Rect(rect)
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = fitz.Rect(span["bbox"])
                if search_area.intersects(span_rect):
                    result |= span_rect
    return result


def _render_region(page: fitz.Page, rect: fitz.Rect) -> bytes:
    pix = page.get_pixmap(clip=rect, dpi=DIAGRAM_RENDER_DPI)
    return pix.tobytes("png")


def extract_diagram_assets(pdf_path: str) -> list[ExtractedDiagram]:
    """
    Pure detection + rendering: no vision/LLM call in this function at
    all — graph_json/caption/diagram_type are always None here, exactly
    like extract_images.py's caption stays None in
    extract_image_assets(). That's parse_diagram()'s job, invoked
    separately and only for assets dedup_engine.diff_assets() has
    flagged as new/changed (§8.3) — captioning/graph-parsing is a real,
    costed vision call, so re-running it on every ingestion pass for
    unchanged diagrams would be pure waste.

    section_header reuses the exact page-range attribution
    extract_tables.py already established
    (extract_tables._section_header_for_page against
    extract_text.split_into_sections()'s output) — the same reuse
    extract_images.py already does, rather than a third/fourth
    reimplementation of the same lookup.
    """
    doc = fitz.open(pdf_path)
    try:
        sections = split_into_sections(doc)

        results: list[ExtractedDiagram] = []
        for page_index, page in enumerate(doc, start=1):
            for region in _detect_diagram_regions(page):
                expanded = _expand_with_nearby_text(page, region)
                image_bytes = _render_region(page, expanded)

                results.append(
                    ExtractedDiagram(
                        image_bytes=image_bytes,
                        graph_json=None,
                        caption=None,
                        diagram_type=None,
                        page_number=page_index,
                        section_header=_section_header_for_page(sections, page_index),
                        asset_hash=hash_bytes(image_bytes),
                    )
                )

        return results
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Costed step — separate from extract_diagram_assets() on purpose (§8.3)
# ---------------------------------------------------------------------------

_DIAGRAM_TYPES = (
    "decision_flow",
    "sequence_diagram",
    "lifecycle_stages",
    "architecture_diagram",
    "escalation_hierarchy",
    "other",
)


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="forbid")  # strict-mode requirement, §39.1 — every nested model needs this individually
    id: str
    label: str


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    label: str | None = None  # e.g. "Yes" / "No" on a decision branch


class DiagramGraph(BaseModel):
    """Structured-output schema for parse_diagram(). diagram_type
    classification happens in the SAME call as graph extraction, not a
    separate pass — one vision call, not two."""

    model_config = ConfigDict(extra="forbid")
    diagram_type: str  # one of _DIAGRAM_TYPES — see _DEFAULT_DIAGRAM_PROMPT; Literal wasn't
    # used here so an unfamiliar diagram shape degrades to a validatable
    # string rather than a hard schema-validation failure
    caption: str
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]

    @property
    def graph_json(self) -> dict[str, list[dict]]:
        """§21's diagram_graphs.graph_json column — {nodes, edges} only,
        separate from caption/diagram_type which are their own columns."""
        return {
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
        }


_DEFAULT_DIAGRAM_PROMPT = (
    "This image is a flowchart or diagram from a software support technical "
    "document. Extract it as a structured graph:\n"
    "- nodes: every distinct shape (box, diamond, circle) with a short id "
    "(e.g. 'n1') and its label text exactly as shown.\n"
    "- edges: every directed connection between two node ids, with the "
    "edge's own label if one is shown (e.g. 'Yes'/'No' on a decision "
    "branch, or a step number on a sequence arrow). Omit label if the "
    "connector has no text on it.\n"
    "- diagram_type: classify the overall diagram as one of "
    f"{', '.join(_DIAGRAM_TYPES)}.\n"
    "- caption: a 1-2 sentence description of what the diagram shows, "
    "written for embedding and search — describe what it means, not its "
    "visual styling."
)


async def parse_diagram(image_bytes: bytes, prompt: str | None = None) -> DiagramGraph:
    """
    The costed step, kept separate from extract_diagram_assets() (§8.3):
    calls the configured vision-capable LLM client via
    call_llm_structured_vision() — real Azure client with provider-level
    structured output + Pydantic validation + one retry, or
    MockLLMClient under LLM_PROVIDER=mock, no network call — to extract
    a validated {nodes, edges} graph plus caption/diagram_type from one
    rendered diagram region. pipeline.py should call this only for
    assets dedup_engine.diff_assets() has determined are new/changed.
    """
    return await call_llm_structured_vision(image_bytes, prompt or _DEFAULT_DIAGRAM_PROMPT, DiagramGraph)

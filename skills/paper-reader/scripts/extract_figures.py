#!/usr/bin/env python3
"""extract_figures.py — Smart figure extraction from academic PDFs.

Uses PyMuPDF (fitz) to:
1. Detect figure captions ("Fig. N:" / "Figure N:" / "Figure N text") with precise positions
2. Find associated image blocks above each caption
3. Render just the figure region at high DPI — not the entire page

This avoids the problems of pdfimages (fragmented sub-images, missing vector
graphics) and full-page rendering (includes surrounding text).

Usage:
    python3 extract_figures.py <pdf_path> <output_dir> [--dpi 300] [--padding 10]

Dependencies: pymupdf (pip install pymupdf)
"""

import argparse
import json
import os
import re
import sys

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)


# Common figure caption patterns in academic papers:
#   "Fig. 1:"          — Springer LNCS, many CS venues
#   "Figure 1:"        — IEEE, ACM
#   "Figure 1."        — some journals
#   "Figure 1 |"       — arXiv/NVIDIA style
#   "Fig. 1."          — Springer variants
#   "FIGURE 1"         — all-caps journals
#   "Figure 1 Text"    — space-only (Xiaomi/PKU arXiv style, no delimiter)
CAPTION_PATTERN = re.compile(
    r"(?:Fig\.?\s*(\d+)|Figure\s+(\d+)|FIGURE\s+(\d+))"
    r"\s*(?:[a-z]|\([a-z]\))?"  # optional subfigure label: "1a", "1(a)"
    r"\s*[:.|]",               # delimiter: colon, period, or pipe
    re.IGNORECASE,
)

# Loose pattern: space-only delimiter — no punctuation after the figure number.
# Only used when the strict pattern fails, with extra guards (short block, few lines)
# to reject in-text references like "Figure 1 shows that...".
CAPTION_PATTERN_LOOSE = re.compile(
    r"^(?:Fig\.?\s*(\d+)|Figure\s+(\d+)|FIGURE\s+(\d+))"
    r"\s*(?:[a-z]|\([a-z]\))?"  # optional subfigure label
    r"\s+\S",                   # space then a non-whitespace character
    re.IGNORECASE,
)

# Table caption pattern — used to detect table boundaries so they don't bleed into figures.
# Matches "Table 1:", "Table 1.", "Tab. 1:", "TABLE 1" etc.
TABLE_CAPTION_PATTERN = re.compile(
    r"^(?:Tab(?:le)?\.?\s*(\d+)|TABLE\s+(\d+))\s*[:.|]?",
    re.IGNORECASE,
)

# Guards for the loose pattern — short standalone caption blocks only.
# These guards are relaxed when the matched line is the FIRST line of the block
# (line_idx == 0), because some PDFs merge the caption with the following body
# paragraph into a single block (so nlines may exceed the limit even though the
# caption itself is only 1-2 lines).
_LOOSE_MAX_LINES = 4    # captions are compact; body paragraphs are longer
_LOOSE_MAX_CHARS = 500  # captions are short; body paragraphs are much longer

# Regex that identifies the start of a body-text sentence within a merged block.
# Used to trim the caption bbox when a caption and body text share one block.
_BODY_SENTENCE_RE = re.compile(
    r"^(?:[A-Z]{2,}[\.!?]|[A-Z][a-z]{2,}\s+\w+\s+\w)",  # "ACT. We..." or "Notably, we..."
)

# Subfigure-intro words that appear INSIDE a multi-line caption.  Lines
# starting with these belong to the same caption and must not trip the
# "looks like body text" early-stop in _caption_bbox_from_block.
_SUBFIG_INTRO_RE = re.compile(
    r"^(?:Left|Right|Top|Bottom|Middle|Centre|Center|Upper|Lower|Above|Below)\b"
    r"|^\([a-z]\)|^\([ivx]+\)|^[A-Z]\)",
    re.IGNORECASE,
)


def _caption_bbox_from_block(block, match_line_idx):
    """Compute a tight caption bbox and joined text, stopping before body-text lines.

    When a PDF renderer merges a caption with the following body paragraph,
    block["bbox"] covers too much.  This function unions the bboxes of only
    the caption lines (starting at match_line_idx), stopping at the first line
    that looks like the start of a new body-text sentence.

    Returns ((x0, y0, x1, y1), full_text) where full_text is the joined caption
    spans (collapsed whitespace).
    """
    lines = block["lines"]
    caption_lines = [lines[match_line_idx]]
    spans = list(lines[match_line_idx]["spans"])

    for j in range(match_line_idx + 1, len(lines)):
        lt = "".join(s["text"] for s in lines[j]["spans"]).strip()
        # Stop if this line looks like the start of a body-text paragraph:
        # either it's long and starts with an uppercase word, or it matches
        # the body-sentence pattern. EXCEPT when the line starts with a
        # subfigure intro ("Left:", "Right:", "(a)", etc.) — those are
        # part of the caption, not body text.
        if (len(lt) > 40 and lt[0].isupper()
                and not re.match(r"^(?:Fig\.?|Figure)\s+\d+", lt, re.IGNORECASE)
                and not _SUBFIG_INTRO_RE.match(lt)):
            if _BODY_SENTENCE_RE.match(lt) or len(lt) > 60:
                break
        caption_lines.append(lines[j])
        spans.extend(lines[j]["spans"])

    # Defensive guard: if the matched line had no spans (rare malformed PDF),
    # fall back to the block bbox so callers always get a valid rectangle.
    if not spans:
        return tuple(block["bbox"]), ""

    x0 = min(s["bbox"][0] for s in spans)
    y0 = min(s["bbox"][1] for s in spans)
    x1 = max(s["bbox"][2] for s in spans)
    y1 = max(s["bbox"][3] for s in spans)

    # Join the caption text across all included lines, collapsing whitespace.
    line_strs = []
    for cl in caption_lines:
        s = "".join(span["text"] for span in cl["spans"]).strip()
        if s:
            line_strs.append(s)
    full_text = re.sub(r"\s+", " ", " ".join(line_strs)).strip()

    return (x0, y0, x1, y1), full_text


def _detect_body_font_size(doc):
    """Detect the dominant body text font size from the document.

    Scans all text spans across all pages, bins font sizes to the nearest
    0.5pt, and returns the size with the highest total character count.
    Returns None if detection fails (no text or ambiguous distribution).
    """
    size_chars = {}  # {rounded_size: total_char_count}
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=0)["blocks"]
        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    n = len(span["text"].strip())
                    if n > 0:
                        binned = round(span["size"] * 2) / 2
                        size_chars[binned] = size_chars.get(binned, 0) + n
                        total_chars += n

    if not size_chars or total_chars == 0:
        return None

    dominant_size = max(size_chars, key=size_chars.get)

    # Sanity check: dominant size should account for a meaningful share
    if size_chars[dominant_size] < total_chars * 0.20:
        return None

    return dominant_size


def _block_font_size(block):
    """Return the dominant font size (in points) of a text block.

    Uses the font size with the most characters in the block, which is
    robust against mixed sizes from math subscripts/superscripts.
    """
    size_chars = {}
    for line in block["lines"]:
        for span in line["spans"]:
            n = len(span["text"].strip())
            if n > 0:
                size_chars[span["size"]] = size_chars.get(span["size"], 0) + n
    if not size_chars:
        return None
    return max(size_chars, key=size_chars.get)


def _is_body_or_header(block, content_width, body_font_size=None):
    """Check if a text block is body text or section header (not figure content).

    Body text and headers should be excluded from figure regions. Figure
    annotations (axis labels, legends, short labels) are typically narrow
    and short, so they won't match these heuristics.

    When body_font_size is provided, font size is used as the primary signal:
    blocks significantly smaller than body text are figure annotations,
    blocks significantly larger are section headers.
    """
    bbox = block["bbox"]
    b_width = bbox[2] - bbox[0]
    width_ratio = b_width / content_width if content_width > 0 else 0

    # Join LINES with a space so visually-separated tokens like "4.1.1" and
    # "Algorithm" (rendered on consecutive lines without an explicit space
    # character) are seen as space-separated by the regex rules below.
    # Spans within a line are joined as-is (PyMuPDF preserves intra-line
    # whitespace within span boundaries).
    text = " ".join(
        "".join(span["text"] for span in line["spans"])
        for line in block["lines"]
    ).strip()
    n_lines = len(block["lines"])

    # Never classify figure captions as body text
    if CAPTION_PATTERN.match(text):
        return False

    # --- Font-size-based classification (primary signal) ---
    if body_font_size is not None:
        blk_size = _block_font_size(block)
        if blk_size is not None:
            ratio = blk_size / body_font_size
            # Significantly smaller than body text → figure annotation.
            # Multi-line tables may use a slightly smaller font and must
            # fall through to the width/nlines checks below, so the
            # early-return guards against width_ratio: tables are wide
            # (>0.5), figure annotations (chart axis label clusters,
            # math matrices, dense legends) are narrow (<0.5).
            # Very small font (ratio < 0.70) is always a figure annotation.
            #
            # Conditions for early-return as figure annotation:
            #   - few lines (1-3): always
            #   - very small font (ratio < 0.70): always
            #   - narrow block (width < 0.5 of content): always
            #   - all-numeric content (chart axis label clusters): always
            tokens = text.split()
            all_numeric = (
                len(tokens) >= 3
                and all(re.match(r"^[\d]+\.?[\d]*%?$", t) for t in tokens)
            )
            if ratio < 0.85 and (
                n_lines < 4
                or ratio < 0.70
                or width_ratio < 0.5
                or all_numeric
            ):
                return False
            # Significantly larger than body text → section header
            # Guard: real headers are 1-3 lines (~60pt max height).
            # Very tall blocks (>60pt) are rotated margin text or
            # watermarks (e.g., "arXiv:2512.02556v1 [cs.CL] ...").
            block_height = bbox[3] - bbox[1]
            if ratio > 1.15 and block_height < 60:
                return True

    # Multi-line blocks spanning significant width are body text
    if n_lines >= 2 and width_ratio > 0.5 and len(text) > 30:
        return True

    # Narrow multi-line blocks — algorithm blocks, two-column body text.
    # Safe: figure annotations already return False via ratio<0.85 check above.
    if n_lines >= 5 and width_ratio > 0.15 and len(text) > 30:
        return True

    # Single-line but very wide with substantial text
    if width_ratio > 0.75 and len(text) > 40:
        return True

    # Section/subsection headers: "N. Title" or "N.N. Title" (with trailing period)
    # Require significant width (>40% content width) to avoid matching
    # numbered items inside figures (e.g., "1. Query and Checkitem")
    if re.match(r"^\d+(\.\d+)*\.\s+\S", text) and len(text) >= 8 and width_ratio > 0.4:
        return True

    # Multi-level section headers without trailing period: "4.1 Title" / "4.1.2 Title"
    # Matches two+ level headers (e.g. "4.1.2 Theoretical Results") that lack a dot.
    # Require uppercase+lowercase start to avoid matching numbers like "1.5 GHz".
    if re.match(r"^\d+\.\d+(\.\d+)?\s+[A-Z][a-z]", text) and width_ratio > 0.35:
        return True

    # Lettered section headers: "A. Title", "B. Title" (appendices)
    if re.match(r"^[A-Z]\.\s+\S", text) and len(text) >= 8 and width_ratio > 0.4:
        return True

    # Common single-word section headers (fallback when font size unavailable)
    if re.match(r"^(Appendices|Appendix|References|Acknowledgments?|Bibliography)\s*$",
                text, re.IGNORECASE) and width_ratio > 0.2:
        return True

    # Table data rows: single-line, moderately wide, multiple tokens with ≥2 numbers.
    # Catches comparison table rows like "Model  85.2  71.3  88.4  62.1  72.4"
    # that may appear between a table caption and the figure below.
    if n_lines == 1 and width_ratio > 0.50 and len(text) > 15:
        tokens = text.split()
        if len(tokens) >= 4:
            num_tokens = sum(1 for t in tokens
                             if re.match(r"^[\d]+\.?[\d]*%?$", t))
            if num_tokens >= 2:
                return True

    return False


def _detect_page_header_bottom(page):
    """Detect the bottom of the running page header (title + rule).

    Academic PDFs often have a running header (paper title + thin horizontal
    rule) at the top of each page. Returns the y position below the header
    where actual content starts, or a default margin if no header is found.
    """
    try:
        drawings = page.get_drawings()
    except Exception as e:
        print(
            f"WARNING: page.get_drawings() failed on page {page.number}: {e} — "
            f"falling back to default header bottom (40pt)",
            file=sys.stderr,
        )
        return 40

    # Look for a thin horizontal rule near the top spanning most of the page.
    # Threshold is adaptive: headers appear in top 10% of page height.
    # This handles PDFs where header rules appear at y=65 on 841pt pages.
    header_threshold = page.rect.height * 0.10  # top 10% of page

    for d in drawings:
        r = d["rect"]
        if r.y0 < header_threshold and r.height < 3 and r.width > page.rect.width * 0.6:
            return r.y1 + 2

    return 40


def find_figure_captions(page, page_num):
    """Find figure caption blocks on a page.

    Returns list of dicts with fig_num, bbox, text, page.
    Supports two caption styles:
      - Strict (delimiter required): "Figure N:" / "Figure N." / "Figure N |"
      - Loose (space-only): "Figure N Text..." — used when no delimiter follows
        the figure number; requires the block to be compact (≤ 4 lines, ≤ 500
        chars) to avoid misfiring on body text.
    In both cases, accepts captions whose "Figure N" line is not the first line
    in the block when all preceding lines are short subfigure labels (≤ 30 chars),
    which handles PDFs that merge "(a) Label" lines into the caption block.
    """
    captions = []
    blocks = page.get_text("dict", flags=0)["blocks"]

    for block in blocks:
        if block["type"] != 0:  # text blocks only
            continue

        # Collect full block text for length guard (loose pattern only)
        block_text = "".join(
            span["text"] for bl_line in block["lines"] for span in bl_line["spans"]
        ).strip()

        for line_idx, line in enumerate(block["lines"]):
            line_text = "".join(span["text"] for span in line["spans"]).strip()

            m = CAPTION_PATTERN.match(line_text)
            loose_match = False

            if not m:
                # Try the loose (space-only) pattern.
                m = CAPTION_PATTERN_LOOSE.match(line_text)
                if not m:
                    continue
                # Guards: reject body paragraphs that happen to start "Figure N
                # shows...".  When the matched line is the FIRST line of the
                # block (line_idx == 0) the guards are relaxed, because some
                # PDFs merge the caption with the following body paragraph into
                # a single block — the caption itself is still genuine.
                if line_idx > 0:
                    if (len(block["lines"]) > _LOOSE_MAX_LINES
                            or len(block_text) > _LOOSE_MAX_CHARS):
                        continue
                loose_match = True

            fig_num = int(m.group(1) or m.group(2) or m.group(3))

            # Reject in-text references.  A genuine caption line may not be the
            # first in its block: some PDF renderers merge short subfigure labels
            # (e.g. "(a) Existing", "(d)") into the same block as the caption.
            # Accept if every preceding line in the block is a short label
            # (≤ 30 chars).  Body paragraphs that happen to wrap a "Figure N"
            # mention onto its own line will have a longer preceding line.
            # Also reject if a preceding line looks like a section header
            # (e.g., "Qualitative Results." — all caps or title case ending with period).
            preceding_ok = True
            for prev in block["lines"][:line_idx]:
                prev_text = "".join(s["text"] for s in prev["spans"]).strip()
                prev_len = len(prev_text)
                if prev_len > 30:
                    preceding_ok = False
                    break
                # Reject if preceding line looks like a section header:
                # ends with period, contains no lowercase letters (all CAPS)
                # or matches title case pattern (Word.).
                if (prev_text.endswith(".") and prev_len >= 4 and
                    (prev_text.isupper() or re.match(r"^[A-Z][a-z]+\s+[A-Z]", prev_text))):
                    preceding_ok = False
                    break
            if not preceding_ok:
                continue

            # Compute caption bbox + full text.  Use a tight bbox that stops
            # before any body-text lines when the PDF has merged caption + body
            # into one block (common when the figure is at the bottom of a
            # column).
            bbox, full_text = _caption_bbox_from_block(block, line_idx)

            captions.append({
                "fig_num": fig_num,
                "bbox": bbox,
                "text": full_text[:250],
                "page": page_num,
                "is_loose": loose_match,
            })
            break  # one caption per block

    return captions


def find_table_captions(page, page_num):
    """Find table caption blocks on a page.

    Returns list of dicts with bbox and page — used as additional upper
    boundaries when extracting figures, so standalone tables don't bleed
    into the figure region above them.
    """
    captions = []
    blocks = page.get_text("dict", flags=0)["blocks"]
    for block in blocks:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if TABLE_CAPTION_PATTERN.match(line_text):
                captions.append({
                    "bbox": block["bbox"],
                    "page": page_num,
                })
                break  # one caption per block
    return captions


def detect_content_margins(page):
    """Detect the content area margins from text blocks on the page.

    Returns (left_margin, right_margin) in PDF points.
    """
    blocks = page.get_text("dict", flags=0)["blocks"]
    text_blocks = [b for b in blocks if b["type"] == 0]
    if not text_blocks:
        return 50, page.rect.width - 50

    # Use the 5th/95th percentile of text block edges to be robust against outliers
    lefts = sorted(b["bbox"][0] for b in text_blocks)
    rights = sorted(b["bbox"][2] for b in text_blocks)

    # Pick the typical left margin (most text blocks start near this x)
    left = lefts[len(lefts) // 10] if len(lefts) > 5 else lefts[0]
    right = rights[-(len(rights) // 10 + 1)] if len(rights) > 5 else rights[-1]

    return left, right


# Column-detection constants. We measure the gap as
#   `next_cluster.min_left - this_cluster.max_left`
# which is "deepest indent in column 1" → "start of column 2". On real
# 2-column academic PDFs this gap is consistently ~140–170pt because
# column-1 paragraph indents reach ~130pt and column 2 starts at ~270pt.
# False positives (single-column pages with subfigure labels or short
# trailing fragments creating a fake second cluster) typically gap by
# only 25–60pt. 100pt cleanly separates the two regimes in our corpus.
_COLUMN_GAP_PT = 100.0


def detect_columns(page):
    """Detect column x-ranges from text-block left edges.

    Returns a list of (x_left, x_right) tuples, one per column, ordered
    left-to-right. Single-column pages return one tuple equal to the
    detected content margins.

    Algorithm: 1-D clustering on text-block left edges. Sort the lefts,
    walk in order, split into a new cluster wherever consecutive lefts
    are more than `_COLUMN_GAP_PT` apart. Column right edges are computed
    via the GUTTER between consecutive clusters (midpoint between this
    cluster's max-left and the next cluster's min-left), not `max(right)`,
    because some blocks in column 1 (full-width tables, footers, paper-
    title headers) legitimately span both columns and would otherwise
    pull the column boundary across the gutter.

    Notes:
    - Caps at 2 columns (academic CS papers virtually never use 3+).
    - Tiny clusters (< 2 blocks) are dropped as marginalia.
    """
    content_left, content_right = detect_content_margins(page)

    blocks = page.get_text("dict", flags=0)["blocks"]
    text_blocks = [b for b in blocks if b["type"] == 0]
    if len(text_blocks) < 4:
        return [(content_left, content_right)]

    # Pair up (left, right) per block, sort by left.
    edges = sorted((b["bbox"][0], b["bbox"][2]) for b in text_blocks)

    # Walk in order, split where consecutive lefts gap by >_COLUMN_GAP_PT.
    clusters = [[edges[0]]]
    for left, right in edges[1:]:
        prev_left = clusters[-1][-1][0]
        if left - prev_left > _COLUMN_GAP_PT:
            clusters.append([(left, right)])
        else:
            clusters[-1].append((left, right))

    # Drop tiny clusters (single-block marginalia, footnote lines).
    big = [c for c in clusters if len(c) >= 2]
    if not big:
        return [(content_left, content_right)]

    # Cap at 2 columns: if 3+ big clusters, merge adjacent pairs by
    # smallest left-gap until 2 remain.
    while len(big) > 2:
        gaps = [(big[i + 1][0][0] - big[i][-1][0], i) for i in range(len(big) - 1)]
        _, idx = min(gaps)
        big[idx] = big[idx] + big[idx + 1]
        del big[idx + 1]

    # Build columns using GUTTER-based right edges. For column i, the right
    # edge is halfway between cluster i's max-left and cluster i+1's
    # min-left. The rightmost column extends to content_right.
    columns = []
    for i, cluster in enumerate(big):
        col_left = min(l for l, _ in cluster)
        if i + 1 < len(big):
            this_max_left = max(l for l, _ in cluster)
            next_min_left = min(l for l, _ in big[i + 1])
            col_right = (this_max_left + next_min_left) / 2
        else:
            col_right = content_right
        columns.append((col_left, col_right))

    return columns


def detect_doc_columns(doc):
    """Detect the document's dominant column layout.

    Walks every page, runs `detect_columns()`, and only declares the
    document 2-column if BOTH:
      (a) The median gutter midpoint across 2-column-detected pages is
          within ±60 pt of the page midline. Real 2-column templates put
          the gutter at the page center; false-positive 2-column
          detections (e.g., a single-column page where subfigure labels
          create scattered clusters) drift the "gutter" off-center.
      (b) ≥ 50 % of the 2-column-detected pages agree on the gutter
          position (within ±40 pt of the median). Consistency across
          pages is the signature of a template-defined gutter.

    Returns the median 2-column boundaries if both criteria met; None
    otherwise (caller falls back to per-page detection or single-col).
    """
    import statistics

    if len(doc) == 0:
        return None
    page_width = doc[0].rect.width
    page_midline = page_width / 2

    per_page = []
    for page_num in range(len(doc)):
        per_page.append(detect_columns(doc[page_num]))

    two_col_pages = [c for c in per_page if len(c) == 2]
    # Need at least 3 confirming pages to call it a 2-column document.
    if len(two_col_pages) < 3:
        return None

    gutters = [(c[0][1] + c[1][0]) / 2 for c in two_col_pages]
    median_gutter = statistics.median(gutters)

    # Criterion (a): median gutter near page midline
    if abs(median_gutter - page_midline) > 60:
        return None

    # Criterion (b): majority of 2-col pages agree on gutter
    near_median = sum(1 for g in gutters if abs(g - median_gutter) <= 40)
    if near_median < len(two_col_pages) * 0.5:
        return None

    return [
        (statistics.median(c[0][0] for c in two_col_pages),
         statistics.median(c[0][1] for c in two_col_pages)),
        (statistics.median(c[1][0] for c in two_col_pages),
         statistics.median(c[1][1] for c in two_col_pages)),
    ]


def column_of(x0, x1, columns):
    """Return the index of the column containing the bbox center, or None.

    None means the bbox spans more than one column (full-width caption,
    spanning header, etc.). The caller should treat None as "all columns".
    """
    if not columns or len(columns) == 1:
        # Single-column page: every bbox is in column 0
        return 0 if columns else None

    bbox_width = x1 - x0
    page_span_left = min(c[0] for c in columns)
    page_span_right = max(c[1] for c in columns)
    page_span = page_span_right - page_span_left
    # If the bbox covers > 65% of the total column span, it's full-width.
    if page_span > 0 and bbox_width / page_span > 0.65:
        return None

    center = (x0 + x1) / 2
    for idx, (cl, cr) in enumerate(columns):
        # Allow a small tolerance — drawings can extend slightly past
        # the detected column edge (axis labels, etc.).
        if cl - 5 <= center <= cr + 5:
            return idx

    # Center fell in a gutter — pick the nearer column.
    distances = [
        (min(abs(center - cl), abs(center - cr)), idx)
        for idx, (cl, cr) in enumerate(columns)
    ]
    return min(distances)[1]


def find_figure_region(page, caption, prev_caption_bottom, padding=10,
                       body_font_size=None):
    """Compute the figure's bounding box above a caption.

    Strategy:
    1. Detect page content margins (left/right) from text layout
    2. Exclude body text and section headers above the figure
    3. Find image blocks / vector drawings in the figure-only zone
    4. Always use full content-area width (figures may have vector elements
       beyond image block bounds)
    """
    page_rect = page.rect
    cap_bbox = caption["bbox"]
    cap_top_y = cap_bbox[1]
    cap_bottom_y = cap_bbox[3]
    cap_x0 = cap_bbox[0]
    cap_x1 = cap_bbox[2]

    # Detect content area width from text layout
    content_left, content_right = detect_content_margins(page)
    content_width = content_right - content_left

    # Determine column membership using real per-page column detection.
    # cap_col is the index of the column the caption belongs to, or None
    # for full-width captions that span more than one column. Detected
    # columns are passed in by the caller so they're cached per-page.
    # Determine full-vs-partial width from the caption's geometry alone.
    # We tried per-page and doc-wide column detection (commit history),
    # but heuristic column detection breaks on figure-heavy pages with
    # dense block lefts. The simpler and more robust signal is the
    # caption itself: a caption that spans most of the content area or
    # is centered within it is full-width; a narrow off-center caption
    # belongs to a partial-width figure (one column of a 2-column page).
    cap_width_ratio = (cap_x1 - cap_x0) / content_width if content_width > 0 else 1.0
    is_full_width = cap_width_ratio > 0.65
    if not is_full_width and content_width > 0:
        cap_center = (cap_x0 + cap_x1) / 2
        content_center = (content_left + content_right) / 2
        offset_ratio = abs(cap_center - content_center) / content_width
        if offset_ratio < 0.15:
            is_full_width = True

    # Column filter for body text and annotation expansion. For partial-
    # width captions, only blocks whose x-range overlaps the caption x-
    # range matter — blocks in the OTHER column belong to a different
    # text flow and must not influence upper_limit. No-op for full-width
    # captions and single-column pages.
    def _in_caption_column(b):
        if is_full_width:
            return True
        bx0, bx1 = b["bbox"][0], b["bbox"][2]
        return not (bx1 < cap_x0 - 5 or bx0 > cap_x1 + 5)

    # Body classifier width. Use caption width for partial-width figures
    # so narrow-column section headers (e.g., "4.1.1 Algorithm" at 95pt)
    # read as a meaningful fraction of the relevant flow width and trigger
    # the section-header rules. Full-width figures use page content width.
    if is_full_width:
        classifier_width = content_width
    else:
        classifier_width = (cap_x1 - cap_x0) + 30  # slight tolerance

    # Base search zone: from previous content to this caption
    base_upper = prev_caption_bottom + 2

    # Get all blocks on the page (text + images)
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_IMAGES)["blocks"]

    # --- Exclude body text and section headers from the figure region ---
    # Strategy: first find the topmost visual element (image block or
    # significant drawing) in the zone. Only exclude body text that is
    # ABOVE this topmost visual — text at the same level or below is
    # likely figure content (labels, annotations, legends).

    # Pre-scan: find topmost IMAGE BLOCK in the full zone.
    # Only image blocks (type=1) are used here — not drawings, because
    # drawings include table rules, decorative lines, etc. that would
    # incorrectly disable body text exclusion for the entire page.
    # Also skip small decorative images (logos, icons, bullet graphics)
    # that appear in title/header areas — these can anchor
    # topmost_visual_y too high, disabling body text exclusion for
    # the entire page (e.g., a "K" logo in the paper title on page 1).
    MIN_IMG_DIM = 80  # points (~1.1 inches) — real figure content is larger
    MIN_IMG_THIN = 30  # minimum short dimension — filters thin banners (arXiv logo 90×14pt)
    topmost_visual_y = cap_top_y  # default: right above caption
    for b in blocks:
        if b["type"] != 1:
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        b_width = b["bbox"][2] - b["bbox"][0]
        b_height = b_bottom - b_top
        # Skip small decorative images (logos, icons, inline graphics)
        if b_width < MIN_IMG_DIM and b_height < MIN_IMG_DIM:
            continue
        # Skip thin banner images (e.g., arXiv logo 90×14pt bypasses AND filter above)
        if min(b_width, b_height) < MIN_IMG_THIN:
            continue
        if b_bottom <= cap_top_y + 5 and b_top >= base_upper - 5:
            topmost_visual_y = min(topmost_visual_y, b_top)

    # For vector-only figures (no image blocks found), also scan vector
    # drawings to set topmost_visual_y.  Find the main drawing cluster
    # by looking for the largest gap in sorted y-positions — the gap
    # separates page header decorations from the figure content.
    if topmost_visual_y == cap_top_y:
        try:
            pre_drawings = page.get_drawings()
        except Exception:
            pre_drawings = []

        draw_y0s = []
        for d in pre_drawings:
            r = d["rect"]
            if r.y0 < base_upper + 10 or r.y1 > cap_top_y + 5:
                continue
            if r.width < 2 and r.height < 2:
                continue
            if r.height < 2 and r.width > page_rect.width * 0.8:
                continue
            draw_y0s.append(r.y0)

        if len(draw_y0s) >= 10:
            draw_y0s.sort()
            best_gap = 0
            cluster_idx = 0
            search_limit = min(len(draw_y0s) - 1, 20)
            for i in range(search_limit):
                gap = draw_y0s[i + 1] - draw_y0s[i]
                if gap > best_gap:
                    best_gap = gap
                    cluster_idx = i + 1
            if best_gap > 50:
                topmost_visual_y = draw_y0s[cluster_idx]

    # Now exclude body text, but only above the topmost visual element.
    # Use b_top (not b_bottom) so text blocks starting above the visual
    # zone are eligible for exclusion even if their bbox extends into it
    # (e.g., an abstract whose bottom edge overlaps with chart elements).
    upper_limit = base_upper
    for b in blocks:
        if b["type"] != 0:
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        # Skip blocks that start before the search zone
        if b_top < base_upper - 5:
            continue
        # Column-aware: for partial-width captions, blocks in the opposite
        # column are irrelevant to upper_limit (they belong to a different
        # text flow).
        if not _in_caption_column(b):
            continue
        # For blocks starting below the topmost visual, only include tall
        # multi-line blocks with body-like font — these are algorithm or code
        # environments that gap detection may have missed as the cluster boundary.
        if b_top > topmost_visual_y:
            n_lines_b = len(b["lines"])
            if body_font_size is not None:
                blk_size = _block_font_size(b)
                is_body_font = blk_size is not None and blk_size / body_font_size >= 0.85
            else:
                is_body_font = False
            if not (n_lines_b >= 4 and is_body_font and b_top < cap_top_y):
                continue
        if _is_body_or_header(b, classifier_width, body_font_size):
            upper_limit = max(upper_limit, b_bottom + 5)

    # Guard: don't push so close to caption that no figure region remains
    if upper_limit > cap_top_y - 15:
        upper_limit = base_upper

    # Find image blocks in the zone above this caption
    # Clamp lower bound to base_upper: the -5 tolerance must never
    # reach above the hard boundary (page header or previous caption).
    img_lower = max(upper_limit - 5, base_upper)
    fig_images = []
    for b in blocks:
        if b["type"] != 1:  # image blocks only
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        b_w = b["bbox"][2] - b["bbox"][0]
        b_h = b_bottom - b_top
        # Skip decorative images (same filters as prescan above)
        if b_w < MIN_IMG_DIM and b_h < MIN_IMG_DIM:
            continue
        if min(b_w, b_h) < MIN_IMG_THIN:
            continue
        if b_bottom <= cap_top_y + 5 and b_top >= img_lower:
            fig_images.append(b)

    # Determine x-extent based on full/partial width (is_full_width was
    # determined up front, before the body-text loop).
    if is_full_width:
        fig_x0 = content_left
        fig_x1 = content_right
    else:
        fig_x0 = cap_x0
        fig_x1 = cap_x1
        if fig_images:
            fig_x0 = min(fig_x0, min(b["bbox"][0] for b in fig_images))
            fig_x1 = max(fig_x1, max(b["bbox"][2] for b in fig_images))

    # Use vector drawings to refine both x and y extent
    # This catches plot lines, bars, axes that aren't raster images
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []

    # Clamp drawing lower bound: the -5 tolerance must never reach
    # above the hard boundary (page header bottom or previous caption).
    # Without this clamp, header decoration rules (which sit just above
    # base_upper) can leak through the tolerance and pull fig_y0 up
    # into the page header area.
    draw_lower = max(upper_limit - 5, base_upper)

    fig_drawings = []
    for d in drawings:
        r = d["rect"]
        # Drawing must be above the caption and below the upper limit
        if r.y1 > cap_top_y + 5 or r.y0 < draw_lower:
            continue
        # Drawing must overlap with the figure's x-range
        if r.x1 < fig_x0 - 20 or r.x0 > fig_x1 + 20:
            continue
        # Skip very tiny drawings (tick marks, dots) for boundary detection
        if r.width < 2 and r.height < 2:
            continue
        # Skip page-wide horizontal rules (running header/footer decoration)
        if r.height < 2 and r.width > page_rect.width * 0.8:
            continue
        fig_drawings.append(d)

    # Compute vertical extent from ALL visual elements (images + drawings)
    y_candidates = []
    if fig_images:
        y_candidates.extend(b["bbox"][1] for b in fig_images)
    if fig_drawings:
        y_candidates.extend(d["rect"].y0 for d in fig_drawings)

    if y_candidates:
        fig_y0 = min(y_candidates)
    else:
        # No visual elements found; start figure region at upper_limit
        fig_y0 = upper_limit

    # Also expand x-extent if drawings extend beyond current bounds.
    # CAP the expansion for partial-width figures at the page midline:
    # a figure whose caption sits in the left column shouldn't extend
    # past the midline (sibling content lives there), and vice versa.
    # This prevents sibling-table drawings from pulling fig_x0 across
    # the gutter (e.g., attention_residuals/fig 6 + Table 4) while still
    # allowing legitimate axis labels and annotations to extend into the
    # gutter. Single-column figures have is_full_width=True and skip this.
    if fig_drawings:
        draw_x0 = min(d["rect"].x0 for d in fig_drawings)
        draw_x1 = max(d["rect"].x1 for d in fig_drawings)
        if not is_full_width:
            page_midline = page_rect.width / 2
            cap_center = (cap_x0 + cap_x1) / 2
            if cap_center < page_midline:
                draw_x1 = min(draw_x1, page_midline)
            else:
                draw_x0 = max(draw_x0, page_midline)
        fig_x0 = min(fig_x0, draw_x0)
        fig_x1 = max(fig_x1, draw_x1)

    # --- Annotation text expansion ---
    # Figure annotations (subplot titles, axis labels, legends) are text
    # blocks that sit above the drawing/image cluster but are NOT body text.
    # The gap detection may miss them because they're above the cluster.
    # Scan for non-body text blocks between upper_limit and fig_y0 and
    # expand fig_y0 upward to include them.
    annot_y0 = fig_y0
    for b in blocks:
        if b["type"] != 0:
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        # Only consider blocks between upper_limit and current fig_y0
        if b_top < upper_limit or b_top >= fig_y0:
            continue
        # Column-aware: don't pull annotations from the opposite column.
        if not _in_caption_column(b):
            continue
        txt = "".join(
            s["text"] for l in b["lines"] for s in l["spans"]
        ).strip()
        if len(txt) < 2:
            continue
        if not _is_body_or_header(b, classifier_width, body_font_size):
            annot_y0 = min(annot_y0, b_top)

    if annot_y0 < fig_y0:
        # Re-collect drawings in the newly-exposed zone
        expanded_lower = max(annot_y0 - 5, base_upper)
        for d in drawings:
            r = d["rect"]
            if r.y0 < expanded_lower or r.y1 > cap_top_y + 5:
                continue
            if r.y0 >= draw_lower:  # already collected
                continue
            if r.x1 < fig_x0 - 20 or r.x0 > fig_x1 + 20:
                continue
            if r.width < 2 and r.height < 2:
                continue
            if r.height < 2 and r.width > page_rect.width * 0.8:
                continue
            fig_drawings.append(d)
        fig_y0 = annot_y0
        # Re-expand x-extent with newly added drawings (same midline cap
        # as above to keep sibling drawings out).
        if fig_drawings:
            draw_x0 = min(d["rect"].x0 for d in fig_drawings)
            draw_x1 = max(d["rect"].x1 for d in fig_drawings)
            if not is_full_width:
                page_midline = page_rect.width / 2
                cap_center = (cap_x0 + cap_x1) / 2
                if cap_center < page_midline:
                    draw_x1 = min(draw_x1, page_midline)
                else:
                    draw_x0 = max(draw_x0, page_midline)
            fig_x0 = min(fig_x0, draw_x0)
            fig_x1 = max(fig_x1, draw_x1)

    fig_y1 = cap_bottom_y

    # Guard: cap figure height to 70% of page to avoid rendering full pages.
    # When triggered, surface a warning so the caller can mark the figure as
    # suspect — the top of the figure was silently cropped.
    max_height = page_rect.height * 0.70
    height_capped = False
    if (fig_y1 - fig_y0) > max_height:
        fig_y0 = fig_y1 - max_height
        height_capped = True

    # Apply padding and clamp to page bounds
    # Note: no padding below fig_y1 (caption bottom) — padding there
    # bleeds into the next paragraph's body text.
    # Clamp clip_y0 to upper_limit: top padding must never bleed back into
    # excluded body text when body text ends just a few pts above the figure.
    clip_y0 = max(max(0, fig_y0 - padding), upper_limit)
    # Defensive: clip_y0 must stay strictly below fig_y1 — otherwise we
    # produce an inverted (zero- or negative-area) clip rect. Can happen
    # when upper_limit is set very close to the caption by aggressive body
    # text exclusion, leaving no room above.
    if clip_y0 >= fig_y1:
        clip_y0 = max(0, fig_y1 - 1)
    clip = fitz.Rect(
        max(0, fig_x0 - padding),
        clip_y0,
        min(page_rect.width, fig_x1 + padding),
        min(page_rect.height, fig_y1 + 2),  # minimal bottom margin
    )

    return clip, len(fig_images), len(fig_drawings), height_capped


def extract_figures(pdf_path, output_dir, dpi=300, padding=10):
    """Extract all figures from a PDF.

    Returns a list of figure info dicts (fig_num, filename, caption, page, size).
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"ERROR: Cannot open PDF: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    # Detect dominant body text font size for figure/body classification
    body_font_size = _detect_body_font_size(doc)
    if body_font_size is not None:
        print(f"Detected body font size: {body_font_size:.1f}pt")

    # Phase 1: Collect all figure captions across all pages
    all_captions = []
    all_table_captions = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        captions = find_figure_captions(page, page_num)
        all_captions.extend(captions)
        all_table_captions.extend(find_table_captions(page, page_num))

    # Deduplicate by fig_num — prefer STRICT (delimiter) matches over LOOSE
    # (space-only) matches. In-text references like "Figure 10 visualizes..."
    # are LOOSE matches that may appear before the real caption "Figure 10:".
    seen = {}  # {fig_num: index in unique_captions}
    unique_captions = []
    for cap in all_captions:
        fn = cap["fig_num"]
        if fn not in seen:
            seen[fn] = len(unique_captions)
            unique_captions.append(cap)
        elif cap.get("is_loose") is False and unique_captions[seen[fn]].get("is_loose"):
            # Replace LOOSE match with STRICT match
            unique_captions[seen[fn]] = cap

    print(f"Found {len(unique_captions)} figure captions:")
    for cap in unique_captions:
        loose_tag = " [LOOSE — may be in-text reference]" if cap.get("is_loose") else ""
        print(f"  Fig. {cap['fig_num']} on page {cap['page']+1}: {cap['text'][:70]}...{loose_tag}")
        if cap.get("is_loose"):
            print(
                f"    WARNING: Fig. {cap['fig_num']} matched only the LOOSE pattern "
                f"(no ':' or '|' delimiter). The caption text may be an in-text "
                f"reference rather than the official caption.",
                file=sys.stderr,
            )

    # All boundary markers: figure captions + table captions.
    # Table captions are included so that a table sitting between Figure N-1
    # and Figure N doesn't bleed into Figure N's extracted region.
    all_boundaries = unique_captions + all_table_captions

    # Phase 2: Extract each figure.  Cache content margins per page so we
    # don't recompute them for every figure on a multi-figure page.
    page_margins = {}  # {page_num: (content_left, content_right)}

    figures = []
    for cap in unique_captions:
        page = doc[cap["page"]]

        if cap["page"] not in page_margins:
            page_margins[cap["page"]] = detect_content_margins(page)
        content_left, content_right = page_margins[cap["page"]]
        content_width = content_right - content_left

        # Find previous boundary on the same page (for upper limit).
        # Includes both figure captions and table captions above this figure.
        # Boundaries that don't horizontally overlap with the current
        # caption (other-column boundaries on a 2-column page) are irrelevant
        # — but full-width boundaries always apply.
        cap_x0, cap_x1 = cap["bbox"][0], cap["bbox"][2]

        def _is_relevant_boundary(c):
            if c["page"] != cap["page"]:
                return False
            if c["bbox"][3] >= cap["bbox"][1]:
                return False
            bx0, bx1 = c["bbox"][0], c["bbox"][2]
            # Full-width boundaries always apply (they occupy both columns).
            if content_width > 0 and (bx1 - bx0) / content_width > 0.65:
                return True
            # Otherwise require x-overlap with the caption column.
            return not (bx1 < cap_x0 - 5 or bx0 > cap_x1 + 5)

        same_page_caps = [c for c in all_boundaries if _is_relevant_boundary(c)]
        if same_page_caps:
            prev_bottom = max(c["bbox"][3] for c in same_page_caps)
        else:
            prev_bottom = _detect_page_header_bottom(page)

        clip, n_images, n_drawings, height_capped = find_figure_region(
            page, cap, prev_bottom, padding, body_font_size
        )

        # Render at high DPI
        pix = page.get_pixmap(clip=clip, dpi=dpi)

        filename = f"fig{cap['fig_num']}.png"
        filepath = os.path.join(output_dir, filename)
        pix.save(filepath)

        # Pseudo-figure detection: a render with no image blocks, no
        # drawings, and an extreme aspect ratio (or tiny clip area) almost
        # always means we captured only the caption text or a stray legend
        # strip — the actual figure was excluded by the upper boundary.
        page_area = page.rect.width * page.rect.height
        clip_area = (clip.x1 - clip.x0) * (clip.y1 - clip.y0)
        aspect = (pix.width / pix.height) if pix.height > 0 else 0
        suspect = False
        suspect_reason = None
        if n_images == 0 and n_drawings == 0:
            if aspect > 6 or aspect < (1 / 6):
                suspect = True
                suspect_reason = f"extreme aspect ratio ({aspect:.2f}) with no visual elements"
            elif page_area > 0 and clip_area / page_area < 0.01:
                suspect = True
                suspect_reason = f"tiny clip area ({100 * clip_area / page_area:.2f}% of page) with no visual elements"
        # Height-cap is a separate suspect signal: the top of the figure was
        # silently cropped to fit within 70% of page height. The render may
        # be missing important content above.
        if height_capped:
            suspect = True
            cap_reason = "figure height capped at 70% of page (top may be cropped)"
            suspect_reason = (
                f"{suspect_reason}; {cap_reason}" if suspect_reason else cap_reason
            )

        fig_info = {
            "fig_num": cap["fig_num"],
            "filename": filename,
            "caption": cap["text"],
            "page": cap["page"] + 1,
            "width": pix.width,
            "height": pix.height,
            "n_image_blocks": n_images,
            "n_drawings": n_drawings,
            "render_type": "raster+vector" if n_images > 0 else "vector-only",
            "clip_rect": [round(clip.x0, 2), round(clip.y0, 2),
                          round(clip.x1, 2), round(clip.y1, 2)],
            "caption_bbox": [round(cap["bbox"][0], 2), round(cap["bbox"][1], 2),
                             round(cap["bbox"][2], 2), round(cap["bbox"][3], 2)],
        }
        if suspect:
            fig_info["suspect"] = True
            fig_info["suspect_reason"] = suspect_reason
        figures.append(fig_info)
        print(f"  Extracted {filename}: {pix.width}x{pix.height}px "
              f"({n_images} image blocks, {n_drawings} drawings, page {cap['page']+1})")
        if suspect:
            print(f"    WARNING: {filename} looks suspect — {suspect_reason}",
                  file=sys.stderr)

    # Write manifest
    manifest_path = os.path.join(output_dir, "figures_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(figures, f, ensure_ascii=False, indent=2)

    doc.close()

    print(f"\nExtracted {len(figures)} figures to {output_dir}/")
    print(f"Manifest: {manifest_path}")

    return figures


def main():
    parser = argparse.ArgumentParser(
        description="Extract figures from academic PDFs using caption detection"
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("output_dir", help="Output directory (figures saved here)")
    parser.add_argument("--dpi", type=int, default=300, help="Render DPI (default: 300)")
    parser.add_argument("--padding", type=int, default=10,
                        help="Padding around figure region in PDF points (default: 10)")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf_path):
        print(f"ERROR: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    extract_figures(args.pdf_path, args.output_dir, args.dpi, args.padding)


if __name__ == "__main__":
    main()

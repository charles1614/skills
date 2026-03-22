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


def _caption_bbox_from_block(block, match_line_idx):
    """Compute a tight caption bbox, stopping before any body-text lines.

    When a PDF renderer merges a caption with the following body paragraph,
    block["bbox"] covers too much.  This function unions the bboxes of only
    the caption lines (starting at match_line_idx), stopping at the first line
    that looks like the start of a new body-text sentence.
    """
    lines = block["lines"]
    spans = list(lines[match_line_idx]["spans"])

    for j in range(match_line_idx + 1, len(lines)):
        lt = "".join(s["text"] for s in lines[j]["spans"]).strip()
        # Stop if this line looks like the start of a body-text paragraph:
        # either it's long and starts with an uppercase word, or it matches
        # the body-sentence pattern.
        if len(lt) > 40 and lt[0].isupper() and not re.match(
            r"^(?:Fig\.?|Figure)\s+\d+", lt, re.IGNORECASE
        ):
            if _BODY_SENTENCE_RE.match(lt) or len(lt) > 60:
                break
        spans.extend(lines[j]["spans"])

    x0 = min(s["bbox"][0] for s in spans)
    y0 = min(s["bbox"][1] for s in spans)
    x1 = max(s["bbox"][2] for s in spans)
    y1 = max(s["bbox"][3] for s in spans)
    return (x0, y0, x1, y1)


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

    text = ""
    for line in block["lines"]:
        for span in line["spans"]:
            text += span["text"]
    text = text.strip()
    n_lines = len(block["lines"])

    # Never classify figure captions as body text
    if CAPTION_PATTERN.match(text):
        return False

    # --- Font-size-based classification (primary signal) ---
    if body_font_size is not None:
        blk_size = _block_font_size(block)
        if blk_size is not None:
            ratio = blk_size / body_font_size
            # Significantly smaller than body text → figure annotation
            if ratio < 0.85:
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

    # Single-line but very wide with substantial text
    if width_ratio > 0.75 and len(text) > 40:
        return True

    # Section/subsection headers: "N. Title" or "N.N. Title"
    # Require significant width (>40% content width) to avoid matching
    # numbered items inside figures (e.g., "1. Query and Checkitem")
    if re.match(r"^\d+(\.\d+)*\.\s+\S", text) and len(text) >= 8 and width_ratio > 0.4:
        return True

    # Lettered section headers: "A. Title", "B. Title" (appendices)
    if re.match(r"^[A-Z]\.\s+\S", text) and len(text) >= 8 and width_ratio > 0.4:
        return True

    # Common single-word section headers (fallback when font size unavailable)
    if re.match(r"^(Appendices|Appendix|References|Acknowledgments?|Bibliography)\s*$",
                text, re.IGNORECASE) and width_ratio > 0.2:
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
    except Exception:
        return 40

    # Look for a thin horizontal rule near the top spanning most of the page.
    # Threshold is adaptive: headers appear in top 10% of page height.
    # This handles PDFs where header rules appear at y=65 on 841pt pages.
    header_threshold = page.rect.height * 0.10  # top 10% of page

    for d in drawings:
        r = d["rect"]
        if r.y0 < header_threshold and r.height < 3 and r.width > page.rect.width * 0.7:
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

            # Compute caption bbox.  Use a tight bbox that stops before any
            # body-text lines when the PDF has merged caption + body into one
            # block (common when the figure is at the bottom of a column).
            bbox = _caption_bbox_from_block(block, line_idx)

            captions.append({
                "fig_num": fig_num,
                "bbox": bbox,
                "text": line_text[:120],
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


def find_figure_region(page, caption, prev_caption_bottom, padding=10, body_font_size=None):
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

    # Detect content area width from text layout
    content_left, content_right = detect_content_margins(page)
    content_width = content_right - content_left

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
        # Only consider blocks that START above the topmost visual
        if b_top > topmost_visual_y or b_top < base_upper - 5:
            continue
        if _is_body_or_header(b, content_width, body_font_size):
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
        if b_bottom <= cap_top_y + 5 and b_top >= img_lower:
            fig_images.append(b)

    # Determine if figure is full-width or partial-width (side-by-side)
    cap_x0 = cap_bbox[0]
    cap_x1 = cap_bbox[2]
    cap_width_ratio = (cap_x1 - cap_x0) / content_width if content_width > 0 else 1.0
    is_full_width = cap_width_ratio > 0.65

    # Determine x-extent based on full/partial width
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

    # Also expand x-extent if drawings extend beyond current bounds
    if fig_drawings:
        draw_x0 = min(d["rect"].x0 for d in fig_drawings)
        draw_x1 = max(d["rect"].x1 for d in fig_drawings)
        fig_x0 = min(fig_x0, draw_x0)
        fig_x1 = max(fig_x1, draw_x1)

    fig_y1 = cap_bottom_y

    # Guard: cap figure height to 70% of page to avoid rendering full pages
    max_height = page_rect.height * 0.70
    if (fig_y1 - fig_y0) > max_height:
        fig_y0 = fig_y1 - max_height

    # Apply padding and clamp to page bounds
    # Note: no padding below fig_y1 (caption bottom) — padding there
    # bleeds into the next paragraph's body text.
    clip = fitz.Rect(
        max(0, fig_x0 - padding),
        max(0, fig_y0 - padding),
        min(page_rect.width, fig_x1 + padding),
        min(page_rect.height, fig_y1 + 2),  # minimal bottom margin
    )

    return clip, len(fig_images)


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
    for page_num in range(len(doc)):
        page = doc[page_num]
        captions = find_figure_captions(page, page_num)
        all_captions.extend(captions)

    # Deduplicate by fig_num (keep first occurrence — the actual figure, not references)
    seen = set()
    unique_captions = []
    for cap in all_captions:
        if cap["fig_num"] not in seen:
            seen.add(cap["fig_num"])
            unique_captions.append(cap)

    print(f"Found {len(unique_captions)} figure captions:")
    for cap in unique_captions:
        print(f"  Fig. {cap['fig_num']} on page {cap['page']+1}: {cap['text'][:70]}...")

    # Phase 2: Extract each figure
    figures = []
    for cap in unique_captions:
        page = doc[cap["page"]]

        # Find previous caption on the same page (for upper boundary)
        # Find captions above this one (not side-by-side).
        # Require the previous caption to END above the current caption's top.
        same_page_caps = [c for c in unique_captions
                          if c["page"] == cap["page"]
                          and c["bbox"][3] < cap["bbox"][1]]
        if same_page_caps:
            prev_bottom = max(c["bbox"][3] for c in same_page_caps)
        else:
            prev_bottom = _detect_page_header_bottom(page)

        clip, n_images = find_figure_region(page, cap, prev_bottom, padding, body_font_size)

        # Render at high DPI
        pix = page.get_pixmap(clip=clip, dpi=dpi)

        filename = f"fig{cap['fig_num']}.png"
        filepath = os.path.join(output_dir, filename)
        pix.save(filepath)

        fig_info = {
            "fig_num": cap["fig_num"],
            "filename": filename,
            "caption": cap["text"],
            "page": cap["page"] + 1,
            "width": pix.width,
            "height": pix.height,
            "n_image_blocks": n_images,
            "render_type": "raster+vector" if n_images > 0 else "vector-only",
        }
        figures.append(fig_info)
        print(f"  Extracted {filename}: {pix.width}x{pix.height}px "
              f"({n_images} image blocks, page {cap['page']+1})")

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

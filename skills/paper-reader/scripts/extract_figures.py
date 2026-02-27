#!/usr/bin/env python3
"""extract_figures.py — Smart figure extraction from academic PDFs.

Uses PyMuPDF (fitz) to:
1. Detect figure captions ("Fig. N:" / "Figure N:") with precise positions
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
CAPTION_PATTERN = re.compile(
    r"(?:Fig\.?\s*(\d+)|Figure\s+(\d+)|FIGURE\s+(\d+))"
    r"\s*(?:[a-z]|\([a-z]\))?"  # optional subfigure label: "1a", "1(a)"
    r"\s*[:.|]",               # delimiter: colon, period, or pipe
    re.IGNORECASE,
)


def _is_body_or_header(block, content_width):
    """Check if a text block is body text or section header (not figure content).

    Body text and headers should be excluded from figure regions. Figure
    annotations (axis labels, legends, short labels) are typically narrow
    and short, so they won't match these heuristics.
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

    # Look for a thin horizontal rule near the top spanning most of the page
    for d in drawings:
        r = d["rect"]
        if r.y0 < 60 and r.height < 3 and r.width > page.rect.width * 0.7:
            return r.y1 + 2

    return 40


def find_figure_captions(page, page_num):
    """Find figure caption blocks on a page.

    Returns list of dicts with fig_num, bbox, text, page.
    Distinguishes real captions from in-text references by requiring
    a recognized delimiter after the figure number (colon, period, or pipe).
    """
    captions = []
    blocks = page.get_text("dict", flags=0)["blocks"]

    for block in blocks:
        if block["type"] != 0:  # text blocks only
            continue

        # Collect all text and check each line
        for line in block["lines"]:
            line_text = "".join(span["text"] for span in line["spans"]).strip()

            m = CAPTION_PATTERN.match(line_text)
            if not m:
                continue

            fig_num = int(m.group(1) or m.group(2) or m.group(3))

            # Use the full text block bbox (caption may span multiple lines)
            captions.append({
                "fig_num": fig_num,
                "bbox": block["bbox"],  # (x0, y0, x1, y1)
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


def find_figure_region(page, caption, prev_caption_bottom, padding=10):
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
    topmost_visual_y = cap_top_y  # default: right above caption
    for b in blocks:
        if b["type"] != 1:
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        if b_bottom <= cap_top_y + 5 and b_top >= base_upper - 5:
            topmost_visual_y = min(topmost_visual_y, b_top)

    # Now exclude body text, but only above the topmost image block
    upper_limit = base_upper
    for b in blocks:
        if b["type"] != 0:
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        # Only consider blocks between base_upper and topmost visual
        if b_bottom > topmost_visual_y or b_top < base_upper - 5:
            continue
        if _is_body_or_header(b, content_width):
            upper_limit = max(upper_limit, b_bottom + 5)

    # Guard: don't push so close to caption that no figure region remains
    if upper_limit > cap_top_y - 15:
        upper_limit = base_upper

    # Find image blocks in the zone above this caption
    fig_images = []
    for b in blocks:
        if b["type"] != 1:  # image blocks only
            continue
        b_top = b["bbox"][1]
        b_bottom = b["bbox"][3]
        if b_bottom <= cap_top_y + 5 and b_top >= upper_limit - 5:
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

    fig_drawings = []
    for d in drawings:
        r = d["rect"]
        # Drawing must be above the caption and below the upper limit
        if r.y1 > cap_top_y + 5 or r.y0 < upper_limit - 5:
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
        same_page_caps = [c for c in unique_captions
                          if c["page"] == cap["page"] and c["bbox"][1] < cap["bbox"][1]]
        if same_page_caps:
            prev_bottom = max(c["bbox"][3] for c in same_page_caps)
        else:
            prev_bottom = _detect_page_header_bottom(page)

        clip, n_images = find_figure_region(page, cap, prev_bottom, padding)

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

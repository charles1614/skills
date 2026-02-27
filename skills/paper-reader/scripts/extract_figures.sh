#!/usr/bin/env bash
# extract_figures.sh — Extract figures from an academic PDF
#
# Usage:
#   extract_figures.sh <pdf_path> <output_dir> [page1,page2,...]
#
# Arguments:
#   pdf_path    - Path to the source PDF file
#   output_dir  - Directory for output (a figures/ subdirectory will be created)
#   pages       - Optional comma-separated page numbers for full-page rendering
#                 (use for vector graphics that pdfimages can't extract)
#
# Output:
#   <output_dir>/figures/     - Directory containing extracted images
#   Prints a summary of extracted images to stdout
#
# Dependencies: pdfimages, pdftoppm (poppler-utils), identify (ImageMagick)

set -euo pipefail

MIN_WIDTH=150
MIN_HEIGHT=150

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <pdf_path> <output_dir> [page1,page2,...]"
    exit 1
fi

PDF_PATH="$1"
OUTPUT_DIR="$2"
RENDER_PAGES="${3:-}"

if [[ ! -f "$PDF_PATH" ]]; then
    echo "ERROR: PDF file not found: $PDF_PATH"
    exit 1
fi

FIGURES_DIR="${OUTPUT_DIR}/figures"
mkdir -p "$FIGURES_DIR"

echo "=== Figure Extraction ==="
echo "Source: $PDF_PATH"
echo "Output: $FIGURES_DIR"
echo ""

# -------------------------------------------------------
# Phase 1: List embedded images
# -------------------------------------------------------
echo "--- Phase 1: Image inventory ---"
pdfimages -list "$PDF_PATH" 2>/dev/null || true
echo ""

# -------------------------------------------------------
# Phase 2: Extract embedded raster images as PNG
# -------------------------------------------------------
echo "--- Phase 2: Extracting embedded images ---"
pdfimages -png "$PDF_PATH" "${FIGURES_DIR}/img" 2>/dev/null

EXTRACTED_COUNT=$(find "$FIGURES_DIR" -name "img-*.png" 2>/dev/null | wc -l)
echo "Extracted $EXTRACTED_COUNT raw images"

# -------------------------------------------------------
# Phase 3: Filter out small images and alpha masks
# -------------------------------------------------------
echo "--- Phase 3: Filtering small images and alpha masks ---"
REMOVED=0
for img in "${FIGURES_DIR}"/img-*.png; do
    [[ -f "$img" ]] || continue

    # Get dimensions and color info
    if command -v identify &>/dev/null; then
        INFO=$(identify -format "%w %h %[channels]" "$img" 2>/dev/null) || continue
        W=$(echo "$INFO" | awk '{print $1}')
        H=$(echo "$INFO" | awk '{print $2}')
        CHANNELS=$(echo "$INFO" | awk '{print $3}')
    else
        # Fallback: read PNG header with python
        INFO=$(python3 -c "
from PIL import Image
im = Image.open('$img')
print(im.width, im.height, im.mode)
" 2>/dev/null) || continue
        W=$(echo "$INFO" | awk '{print $1}')
        H=$(echo "$INFO" | awk '{print $2}')
        CHANNELS=$(echo "$INFO" | awk '{print $3}')
    fi

    # Remove alpha mask images (grayscale single-channel from pdfimages smask)
    if [[ "$CHANNELS" == "gray" || "$CHANNELS" == "L" ]]; then
        rm "$img"
        REMOVED=$((REMOVED + 1))
        continue
    fi

    # Remove images below minimum dimensions
    if [[ "$W" -lt "$MIN_WIDTH" || "$H" -lt "$MIN_HEIGHT" ]]; then
        rm "$img"
        REMOVED=$((REMOVED + 1))
    fi
done
echo "Removed $REMOVED images (small or alpha masks)"

# -------------------------------------------------------
# Phase 4: Render specific pages (for vector graphics)
# -------------------------------------------------------
if [[ -n "$RENDER_PAGES" ]]; then
    echo "--- Phase 4: Rendering pages as full images ---"
    IFS=',' read -ra PAGES <<< "$RENDER_PAGES"
    for page in "${PAGES[@]}"; do
        page=$(echo "$page" | tr -d ' ')
        echo "  Rendering page $page at 300 DPI..."
        pdftoppm -png -r 300 -f "$page" -l "$page" "$PDF_PATH" "${FIGURES_DIR}/page"
        # pdftoppm names output as page-<padded_number>.png
    done
fi

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
echo ""
echo "=== Extraction Summary ==="
FINAL_COUNT=$(find "$FIGURES_DIR" -name "*.png" 2>/dev/null | wc -l)
echo "Total figures available: $FINAL_COUNT"
echo ""

if [[ "$FINAL_COUNT" -gt 0 ]]; then
    echo "Files:"
    for img in "${FIGURES_DIR}"/*.png; do
        [[ -f "$img" ]] || continue
        BASENAME=$(basename "$img")
        if command -v identify &>/dev/null; then
            DIMS=$(identify -format "%wx%h" "$img" 2>/dev/null) || DIMS="unknown"
        else
            DIMS=$(python3 -c "
from PIL import Image
im = Image.open('$img')
print(f'{im.width}x{im.height}')
" 2>/dev/null) || DIMS="unknown"
        fi
        SIZE=$(du -h "$img" | cut -f1)
        echo "  $BASENAME  ${DIMS}  ${SIZE}"
    done
fi

echo ""
echo "=== Done ==="

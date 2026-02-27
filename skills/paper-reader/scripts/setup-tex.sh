#!/usr/bin/env bash
# setup-tex.sh — Install required TeX packages for paper-reader skill
# Run once before first use.
set -euo pipefail

echo "=== Paper Reader: TeX Environment Setup ==="

if ! command -v tlmgr &>/dev/null; then
    echo "ERROR: tlmgr not found. Please install TinyTeX or TeX Live first."
    exit 1
fi

PACKAGES=(
    # CJK support
    xecjk
    ctex
    zhnumber
    # Algorithms
    algorithm2e
    algorithmicx
    algorithms
    ifoddpage
    relsize
    # Typography & layout
    tex-gyre
    tex-gyre-math
    titlesec
    fancyhdr
    geometry
    setspace
    enumitem
    # Tables
    booktabs
    tabularx
    longtable
    multirow
    makecell
    # Colors & boxes
    xcolor
    tcolorbox
    environ
    trimspaces
    etoolbox
    pgf
    # Math
    amsmath
    amssymb
    amsthm
    # Code listings
    listings
    # Hyperlinks & PDF
    hyperref
    # Graphics
    graphicx
    float
    subcaption
    caption
    # Fonts
    fontspec
)

echo "Installing required TeX packages..."
for pkg in "${PACKAGES[@]}"; do
    if kpsewhich "${pkg}.sty" &>/dev/null 2>&1 || kpsewhich "${pkg}.cls" &>/dev/null 2>&1; then
        echo "  [OK] ${pkg}"
    else
        echo "  [INSTALLING] ${pkg}..."
        tlmgr install "${pkg}" 2>&1 | tail -1 || echo "  [WARN] Failed: ${pkg}"
    fi
done

echo ""
echo "Verifying critical packages..."

for sty in xeCJK.sty fontspec.sty tcolorbox.sty booktabs.sty titlesec.sty; do
    if kpsewhich "$sty" &>/dev/null; then
        echo "  [OK] $sty"
    else
        echo "  [MISSING] $sty"
    fi
done

echo ""
echo "Checking Chinese fonts..."
for font in "Noto Serif CJK SC" "Noto Sans CJK SC" "Noto Sans Mono CJK SC"; do
    if fc-list :lang=zh family 2>/dev/null | grep -q "$font"; then
        echo "  [OK] $font"
    else
        echo "  [WARN] $font not found"
    fi
done

echo ""
echo "=== Setup complete ==="

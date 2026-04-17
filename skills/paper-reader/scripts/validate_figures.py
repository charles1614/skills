#!/usr/bin/env python3
"""validate_figures.py — PDF-structure-based validation of extracted figures.

Uses PyMuPDF to inspect the original PDF at the extraction coordinates,
detecting quality issues that visual inspection would catch:
  1. Body text leaking into figure top/bottom
  2. Page header artifacts (running title + horizontal rule)
  3. Caption-figure number mismatch (in-text reference vs real caption)
  4. Partial figure capture (missing subfigures)
  5. Aspect ratio anomalies
  6. Figure numbering gaps

Usage:
    python3 validate_figures.py <paper_dir>
    python3 validate_figures.py <paper_dir> --json
    python3 validate_figures.py <paper_dir> [paper_dir2 ...]  # batch mode

Dependencies: pymupdf (pip install pymupdf)
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)

# Import utilities from extract_figures.py (same directory)
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
from extract_figures import (
    CAPTION_PATTERN,
    CAPTION_PATTERN_LOOSE,
    _detect_body_font_size,
    _block_font_size,
    _is_body_or_header,
    _detect_page_header_bottom,
    detect_content_margins,
    find_figure_captions,
)

# Verbs that indicate in-text references rather than captions
# Match verb forms only — avoid matching nouns like "Comparison", "Visualization".
# Use specific inflections: base, -s, -es, -ed, -ing (not \w* which catches nouns).
_INTEXT_VERBS = re.compile(
    r"(?:Fig\.?\s*\d+|Figure\s+\d+)\s*"
    r"(?:\([a-z]\)\s*)?"  # optional subfigure ref
    r"(shows?\b|showing\b|illustrated?s?\b|illustrating\b|demonstrates?\b|demonstrating\b|"
    r"presents?\b|presenting\b|compares?\b|comparing\b|depicts?\b|depicting\b|"
    r"displays?\b|displaying\b|visualizes?\b|visualizing\b|plots?\b|plotting\b|"
    r"summarizes?\b|summarizing\b|indicates?\b|indicating\b|reveals?\b|revealing\b|"
    r"reports?\b|reporting\b|describes?\b|describing\b|provides?\b|providing\b|"
    r"highlights?\b|highlighting\b|outlines?\b|outlining\b|captures?\b|capturing\b|"
    r"contains?\b|containing\b|gives?\b|giving\b|lists?\b|listing\b|"
    r"details?\b|detailing\b|explains?\b|explaining\b|represents?\b|representing\b|"
    r"is\s+(?:a|an|the)\b|was\b|are\b|were\b|can\b|"
    r"also\b|that\b|where\b|which\b|how\b|in\s+(?:the|this|our)\b)",
    re.IGNORECASE,
)

# Subfigure label patterns in captions
_SUBFIG_PATTERN = re.compile(r"\(([a-z])\)")


@dataclass
class Issue:
    category: str       # body_text, header, caption_mismatch, partial, aspect_ratio, numbering
    severity: str       # CRITICAL, HIGH, MEDIUM, INFO
    fig_num: int
    description: str
    evidence: str = ""  # text/data that triggered the flag


@dataclass
class ValidationReport:
    paper_dir: str
    total_figures: int
    issues: list = field(default_factory=list)
    clean_figures: list = field(default_factory=list)


class FigureValidator:
    def __init__(self, paper_dir):
        self.paper_dir = Path(paper_dir)
        self.manifest = self._load_manifest()
        self.doc = self._open_pdf()
        self.body_font_size = _detect_body_font_size(self.doc)
        self.paper_title = self._detect_paper_title()

    def _load_manifest(self):
        manifest_path = self.paper_dir / "figures" / "figures_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest at {manifest_path}")
        with open(manifest_path) as f:
            return json.load(f)

    def _open_pdf(self):
        pdf_path = self.paper_dir / "paper.pdf"
        if not pdf_path.exists():
            raise FileNotFoundError(f"No PDF at {pdf_path}")
        return fitz.open(str(pdf_path))

    def _detect_paper_title(self):
        """Extract paper title from page 1 (largest font, substantial text)."""
        if len(self.doc) == 0:
            return ""
        page = self.doc[0]
        blocks = page.get_text("dict", flags=0)["blocks"]
        best_text, best_size = "", 0
        for b in blocks:
            if b["type"] != 0:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if len(t) > 10 and span["size"] > best_size:
                        best_size = span["size"]
                        best_text = t
        return best_text

    def _get_text_blocks_in_rect(self, page, rect):
        """Get text blocks that overlap with the given rect."""
        blocks = page.get_text("dict", flags=0)["blocks"]
        result = []
        for b in blocks:
            if b["type"] != 0:
                continue
            bb = b["bbox"]
            # Check overlap
            if bb[2] <= rect[0] or bb[0] >= rect[2]:
                continue
            if bb[3] <= rect[1] or bb[1] >= rect[3]:
                continue
            result.append(b)
        return result

    def _block_text(self, block):
        """Extract full text from a text block."""
        return "".join(
            span["text"] for line in block["lines"] for span in line["spans"]
        ).strip()

    def _is_algorithm_figure(self, fig):
        """Check if a figure is an algorithm/pseudocode figure based on caption."""
        caption = fig.get("caption", "").lower()
        return any(kw in caption for kw in (
            "algorithm", "pseudocode", "pseudo-code", "pseudo code",
            "procedure", "subroutine",
        ))

    def _is_algorithm_text(self, text):
        """Check if text looks like algorithm pseudocode, not body text."""
        # Algorithm header: "Algorithm N ..." or "Procedure ..."
        if re.match(r"^(Algorithm|Procedure)\s+\d+", text):
            return True
        # Numbered steps with programming keywords
        keywords = ("function", "return", "for each", "for all", "while", "end for",
                     "end while", "end if", "end function", "require:", "ensure:")
        text_lower = text.lower()
        return sum(1 for kw in keywords if kw in text_lower) >= 2

    def check_body_text_leakage(self, fig):
        """Check for body text leaking into the top or bottom of a figure."""
        issues = []
        clip = fig.get("clip_rect")
        if not clip:
            return issues

        page_idx = fig["page"] - 1
        if page_idx < 0 or page_idx >= len(self.doc):
            return issues
        page = self.doc[page_idx]
        content_left, content_right = detect_content_margins(page)
        content_width = content_right - content_left

        clip_height = clip[3] - clip[1]
        cap_bbox = fig.get("caption_bbox", clip)

        # Skip algorithm figures — their content IS text
        is_algo = self._is_algorithm_figure(fig)

        # Define zones to check
        top_zone_bottom = clip[1] + clip_height * 0.15
        bottom_zone_top = cap_bbox[3]  # below caption

        blocks = self._get_text_blocks_in_rect(page, clip)
        for b in blocks:
            bb = b["bbox"]
            text = self._block_text(b)

            # Skip the caption itself
            if CAPTION_PATTERN.match(text) or CAPTION_PATTERN_LOOSE.match(text):
                continue

            if not _is_body_or_header(b, content_width, self.body_font_size):
                continue

            # Skip text that looks like algorithm pseudocode — it's figure content
            if self._is_algorithm_text(text):
                continue

            # Downgrade severity if block font is smaller than body text
            # (likely a figure annotation that triggered width/length heuristics)
            is_small_font = False
            if self.body_font_size:
                blk_sz = _block_font_size(b)
                if blk_sz and blk_sz / self.body_font_size < 0.92:
                    is_small_font = True

            # Check top zone
            if bb[1] < top_zone_bottom:
                if is_small_font:
                    severity = "MEDIUM"
                else:
                    severity = "HIGH" if len(text) > 40 else "MEDIUM"
                issues.append(Issue(
                    category="body_text",
                    severity=severity,
                    fig_num=fig["fig_num"],
                    description=f"Body text at top of figure (y={bb[1]:.0f}, clip top={clip[1]:.0f})",
                    evidence=text[:100],
                ))

            # Check bottom zone (below caption)
            if bb[1] > bottom_zone_top:
                if is_small_font:
                    severity = "MEDIUM"
                else:
                    severity = "HIGH" if len(text) > 40 else "MEDIUM"
                issues.append(Issue(
                    category="body_text",
                    severity=severity,
                    fig_num=fig["fig_num"],
                    description=f"Body text below caption (y={bb[1]:.0f}, caption bottom={cap_bbox[3]:.0f})",
                    evidence=text[:100],
                ))

        return issues

    def check_page_header_artifacts(self, fig):
        """Check if the figure region includes page header content."""
        issues = []
        clip = fig.get("clip_rect")
        if not clip:
            return issues

        page_idx = fig["page"] - 1
        if page_idx < 0 or page_idx >= len(self.doc):
            return issues
        page = self.doc[page_idx]

        header_bottom = _detect_page_header_bottom(page)

        # Check if clip top is above or very close to header bottom
        if clip[1] < header_bottom - 2:
            issues.append(Issue(
                category="header",
                severity="HIGH",
                fig_num=fig["fig_num"],
                description=f"Figure extends into page header (clip top={clip[1]:.0f}, header bottom={header_bottom:.0f})",
            ))
            return issues

        # Also check for header-like text in the top 50pt of the clip rect
        top_zone = [clip[0], clip[1], clip[2], min(clip[1] + 50, clip[3])]
        blocks = self._get_text_blocks_in_rect(page, top_zone)
        for b in blocks:
            text = self._block_text(b)
            # Check for paper title
            if (self.paper_title and len(self.paper_title) > 15 and
                    self.paper_title[:30].lower() in text.lower()):
                issues.append(Issue(
                    category="header",
                    severity="MEDIUM",
                    fig_num=fig["fig_num"],
                    description="Paper title text found at top of figure",
                    evidence=text[:80],
                ))
            # Check for arXiv identifiers
            if re.search(r"arXiv:\d{4}\.\d{4,5}", text):
                issues.append(Issue(
                    category="header",
                    severity="MEDIUM",
                    fig_num=fig["fig_num"],
                    description="arXiv identifier found at top of figure",
                    evidence=text[:80],
                ))

        # Check for page-spanning horizontal rules at the very top of the clip rect.
        # Must be ABOVE all other visual content (images, text) to be a header rule.
        # Chart axes/grid lines appear among other content and should not be flagged.
        try:
            drawings = page.get_drawings()
            # Find the topmost non-rule visual element in the clip
            topmost_content_y = clip[3]  # default: bottom of clip
            for b in self._get_text_blocks_in_rect(page, clip):
                topmost_content_y = min(topmost_content_y, b["bbox"][1])
            # Also check image blocks
            img_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_IMAGES)["blocks"]
            for b in img_blocks:
                if b["type"] == 1:
                    bb = b["bbox"]
                    if bb[3] > clip[1] and bb[1] < clip[3] and bb[2] > clip[0] and bb[0] < clip[2]:
                        topmost_content_y = min(topmost_content_y, bb[1])

            for d in drawings:
                r = d["rect"]
                # Only flag rules that are above all content and span the page
                if (r.y0 >= clip[1] and r.y0 < topmost_content_y - 5 and
                        r.height < 3 and r.width > page.rect.width * 0.6):
                    issues.append(Issue(
                        category="header",
                        severity="HIGH",
                        fig_num=fig["fig_num"],
                        description=f"Page header rule above figure content (y={r.y0:.0f})",
                    ))
        except Exception:
            pass

        return issues

    def check_caption_mismatch(self, fig):
        """Check if the caption is an in-text reference rather than a real caption."""
        issues = []
        caption = fig.get("caption", "")

        # Check for in-text reference verbs
        if _INTEXT_VERBS.match(caption):
            verb_match = _INTEXT_VERBS.match(caption)
            verb = verb_match.group(1) if verb_match else ""
            # Capitalized words after "Figure N" are likely caption titles, not
            # in-text reference verbs. "Figure 3 Showcases of..." (noun/title)
            # vs "Figure 3 shows the..." (in-text reference, lowercase verb).
            if verb and verb[0].isupper():
                pass  # likely a caption title, not an in-text reference
            else:
                issues.append(Issue(
                    category="caption_mismatch",
                    severity="HIGH",
                    fig_num=fig["fig_num"],
                    description=f"Caption looks like an in-text reference (verb: '{verb}')",
                    evidence=caption[:120],
                ))

        # Check for very short caption (real captions usually have description)
        fig_num_str = f"Figure {fig['fig_num']}"
        remaining = caption.replace(fig_num_str, "").strip()
        remaining = re.sub(r"^(Fig\.?\s*\d+|FIGURE\s+\d+)\s*[:.|]?\s*", "", remaining)
        if len(remaining) < 5 and not caption.startswith("Figure") and not caption.startswith("Fig"):
            issues.append(Issue(
                category="caption_mismatch",
                severity="MEDIUM",
                fig_num=fig["fig_num"],
                description="Caption has very little descriptive text",
                evidence=caption[:120],
            ))

        # Cross-validate: check if a STRICT caption exists elsewhere in the PDF
        # when the current match is LOOSE
        page_idx = fig["page"] - 1
        if page_idx >= 0 and page_idx < len(self.doc):
            # Check if current caption would only match the LOOSE pattern
            if not CAPTION_PATTERN.match(caption) and CAPTION_PATTERN_LOOSE.match(caption):
                # Scan all pages for a strict match with this figure number
                fn = fig["fig_num"]
                for pn in range(len(self.doc)):
                    pg = self.doc[pn]
                    text = pg.get_text("text")
                    for line in text.split("\n"):
                        line = line.strip()
                        m = CAPTION_PATTERN.match(line)
                        if m:
                            matched_num = int(m.group(1) or m.group(2) or m.group(3))
                            if matched_num == fn:
                                issues.append(Issue(
                                    category="caption_mismatch",
                                    severity="HIGH",
                                    fig_num=fn,
                                    description=f"LOOSE caption used, but STRICT match exists on page {pn+1}",
                                    evidence=f"Current: {caption[:60]} | STRICT: {line[:60]}",
                                ))
                                break
                    else:
                        continue
                    break

        return issues

    def check_partial_capture(self, fig):
        """Check for missing subfigures in a multi-panel figure."""
        issues = []
        caption = fig.get("caption", "")
        clip = fig.get("clip_rect")
        if not clip:
            return issues

        # Find subfigure labels in caption
        caption_subfigs = _SUBFIG_PATTERN.findall(caption)
        if len(caption_subfigs) < 2:
            return issues  # not a multi-panel figure

        page_idx = fig["page"] - 1
        if page_idx < 0 or page_idx >= len(self.doc):
            return issues
        page = self.doc[page_idx]

        # Find subfigure labels in the clip rect
        blocks = self._get_text_blocks_in_rect(page, clip)
        found_labels = set()
        for b in blocks:
            text = self._block_text(b)
            for label in _SUBFIG_PATTERN.findall(text):
                found_labels.add(label)

        # Check for missing labels
        expected = set(caption_subfigs)
        missing = expected - found_labels
        if missing:
            issues.append(Issue(
                category="partial",
                severity="HIGH",
                fig_num=fig["fig_num"],
                description=f"Caption references subfigures {sorted(expected)} but {sorted(missing)} not found in figure region",
                evidence=f"clip width: {clip[2]-clip[0]:.0f}pt",
            ))

        return issues

    def check_aspect_ratio(self, fig):
        """Check for anomalous aspect ratios indicating extraction issues."""
        issues = []
        w, h = fig.get("width", 0), fig.get("height", 0)
        if w == 0 or h == 0:
            return issues

        ar = w / h

        if ar > 8.0:
            issues.append(Issue(
                category="aspect_ratio",
                severity="MEDIUM",
                fig_num=fig["fig_num"],
                description=f"Extremely wide figure (aspect ratio {ar:.1f}) — may be just a caption or rule",
                evidence=f"{w}x{h}px",
            ))

        if ar < 0.25:
            issues.append(Issue(
                category="aspect_ratio",
                severity="MEDIUM",
                fig_num=fig["fig_num"],
                description=f"Extremely tall figure (aspect ratio {ar:.2f}) — may contain extra content",
                evidence=f"{w}x{h}px",
            ))

        # Check if figure hits the max-height cap (~70% page height at render DPI)
        clip = fig.get("clip_rect")
        if clip:
            page_idx = fig["page"] - 1
            if 0 <= page_idx < len(self.doc):
                page_height = self.doc[page_idx].rect.height
                clip_height = clip[3] - clip[1]
                if clip_height > page_height * 0.68:
                    issues.append(Issue(
                        category="aspect_ratio",
                        severity="MEDIUM",
                        fig_num=fig["fig_num"],
                        description=f"Figure spans {clip_height/page_height*100:.0f}% of page height — extractor may have no good upper boundary",
                        evidence=f"clip height: {clip_height:.0f}pt, page: {page_height:.0f}pt",
                    ))

        return issues

    def check_extractor_suspect_flag(self, fig):
        """Surface the extractor's own suspect flag as a validator issue.

        extract_figures.py marks figures as suspect when they have no visual
        content (likely captured only the caption/legend strip) or when the
        70% page-height cap was triggered (top of figure may be cropped).
        The validator should propagate this, otherwise the warning is buried
        in stderr and the per-paper report doesn't reflect it.
        """
        if not fig.get("suspect"):
            return []
        return [Issue(
            category="extractor_suspect",
            severity="HIGH",
            fig_num=fig["fig_num"],
            description="Extractor flagged this figure as suspect",
            evidence=fig.get("suspect_reason", "(no reason given)"),
        )]

    def check_numbering_gaps(self):
        """Check for gaps in figure numbering sequence."""
        issues = []
        fig_nums = sorted(f["fig_num"] for f in self.manifest)
        if not fig_nums:
            return issues

        # Build a set of figure numbers referenced in the PDF
        pdf_fig_refs = set()
        for pn in range(len(self.doc)):
            text = self.doc[pn].get_text("text")
            for m in re.finditer(r"(?:Fig\.?\s*|Figure\s+|FIGURE\s+)(\d+)", text):
                pdf_fig_refs.add(int(m.group(1)))

        # Check for gaps
        for n in range(fig_nums[0], fig_nums[-1] + 1):
            if n not in fig_nums:
                severity = "HIGH" if n in pdf_fig_refs else "INFO"
                issues.append(Issue(
                    category="numbering",
                    severity=severity,
                    fig_num=n,
                    description=f"Figure {n} missing from extraction (gap in sequence {fig_nums[0]}-{fig_nums[-1]})",
                    evidence="referenced in PDF text" if n in pdf_fig_refs else "not found in PDF text",
                ))

        # Check for duplicates
        from collections import Counter
        counts = Counter(fig_nums)
        for num, count in counts.items():
            if count > 1:
                issues.append(Issue(
                    category="numbering",
                    severity="HIGH",
                    fig_num=num,
                    description=f"Figure {num} appears {count} times in manifest",
                ))

        return issues

    def validate_all(self):
        """Run all checks and return a ValidationReport."""
        report = ValidationReport(
            paper_dir=str(self.paper_dir),
            total_figures=len(self.manifest),
        )

        # Per-figure checks
        flagged_figs = set()
        for fig in self.manifest:
            fig_issues = []
            fig_issues.extend(self.check_body_text_leakage(fig))
            fig_issues.extend(self.check_page_header_artifacts(fig))
            fig_issues.extend(self.check_caption_mismatch(fig))
            fig_issues.extend(self.check_partial_capture(fig))
            fig_issues.extend(self.check_aspect_ratio(fig))
            fig_issues.extend(self.check_extractor_suspect_flag(fig))

            report.issues.extend(fig_issues)
            if fig_issues:
                flagged_figs.add(fig["fig_num"])

        # Whole-document checks
        report.issues.extend(self.check_numbering_gaps())

        # Clean figures
        report.clean_figures = sorted(
            f["fig_num"] for f in self.manifest if f["fig_num"] not in flagged_figs
        )

        return report

    def close(self):
        self.doc.close()


def format_report(report, use_color=True):
    """Format a validation report as human-readable text."""
    lines = []
    severity_colors = {
        "CRITICAL": "\033[91m",  # red
        "HIGH": "\033[93m",      # yellow
        "MEDIUM": "\033[36m",    # cyan
        "INFO": "\033[90m",      # gray
    }
    reset = "\033[0m"

    lines.append(f"=== {report.paper_dir} ===")
    lines.append(f"Total figures: {report.total_figures}")

    if not report.issues:
        lines.append("All figures clean.")
        return "\n".join(lines)

    # Group by severity
    by_severity = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "INFO": []}
    for issue in report.issues:
        by_severity.get(issue.severity, by_severity["INFO"]).append(issue)

    # Count
    counts = {s: len(iss) for s, iss in by_severity.items() if iss}
    lines.append(f"Issues: {', '.join(f'{c} {s}' for s, c in counts.items())}")
    lines.append("")

    for severity in ["CRITICAL", "HIGH", "MEDIUM", "INFO"]:
        issues = by_severity[severity]
        if not issues:
            continue
        color = severity_colors[severity] if use_color else ""
        rst = reset if use_color else ""
        lines.append(f"{color}--- {severity} ---{rst}")
        for issue in sorted(issues, key=lambda i: i.fig_num):
            lines.append(f"  Fig {issue.fig_num}: [{issue.category}] {issue.description}")
            if issue.evidence:
                lines.append(f"           {issue.evidence}")
        lines.append("")

    if report.clean_figures:
        lines.append(f"Clean: fig {', '.join(str(n) for n in report.clean_figures)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate extracted figures against the source PDF"
    )
    parser.add_argument("paper_dirs", nargs="+", help="Paper directory (with figures/ and paper.pdf)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--save", action="store_true",
                        help="Save validation_report.json alongside the manifest")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    args = parser.parse_args()

    all_reports = []
    exit_code = 0

    for paper_dir in args.paper_dirs:
        try:
            validator = FigureValidator(paper_dir)
            report = validator.validate_all()
            validator.close()
        except FileNotFoundError as e:
            print(f"SKIP {paper_dir}: {e}", file=sys.stderr)
            continue

        all_reports.append(report)

        # Check for HIGH/CRITICAL issues
        if any(i.severity in ("CRITICAL", "HIGH") for i in report.issues):
            exit_code = 1

        if args.save:
            save_path = Path(paper_dir) / "figures" / "validation_report.json"
            with open(save_path, "w") as f:
                json.dump(asdict(report), f, indent=2)

    if args.json:
        print(json.dumps([asdict(r) for r in all_reports], indent=2))
    else:
        for report in all_reports:
            print(format_report(report, use_color=not args.no_color))
            print()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

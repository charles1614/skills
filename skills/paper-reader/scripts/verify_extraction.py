#!/usr/bin/env python3
"""
Enhanced Figure Extraction Quality Verification Tool
Part of the paper-reader skill

Identifies boundary detection issues:
- Body text misclassification
- Page header leakage
- Wrong panel/content inclusion
- Text clipping at boundaries
- Caption/body text leakage

Usage:
  python verify_extraction.py <paper_dir>
  python verify_extraction.py /path/to/paper_name/
"""

import os
import sys
import json
from pathlib import Path
from collections import defaultdict

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow", file=sys.stderr)
    sys.exit(1)

try:
    import pytesseract
except ImportError:
    print(
        "ERROR: pytesseract not installed. Run: pip install pytesseract\n"
        "       Also ensure the 'tesseract' binary is on PATH "
        "(e.g., apt install tesseract-ocr).",
        file=sys.stderr,
    )
    sys.exit(1)

class FigureVerifier:
    """Verify extracted figures for boundary detection issues."""

    ISSUE_CATEGORIES = {
        'BODY_TEXT_MISCLASS': 'Body text misclassification',
        'PAGE_HEADER_LEAKAGE': 'Page header leakage',
        'WRONG_PANEL': 'Wrong panel/content inclusion',
        'TEXT_CLIPPING': 'Text clipping at boundaries',
        'CAPTION_LEAKAGE': 'Caption/body text leakage',
    }

    SEVERITY_LEVELS = {
        'CRITICAL': 1,
        'HIGH': 2,
        'MEDIUM': 3,
        'INFO': 4,
    }

    def __init__(self, paper_path):
        self.paper_path = Path(paper_path)
        self.figures_dir = self.paper_path / "figures"
        self.issues = defaultdict(list)
        self.clean_figures = []

    def extract_ocr_text(self, image_path):
        """Extract text from image using OCR."""
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text.strip()
        except Exception as e:
            return f"[OCR Error: {e}]"

    def check_body_text_patterns(self, text):
        """Detect prose paragraphs and body text patterns."""
        body_text_indicators = [
            r'Quantitative experiments',
            r'Qualitative results',
            r'Ablation study',
            r'Main results',
            r'Experimental setup',
            r'^\d+\.\d+\.?\s+[A-Z]',  # Section headers like "4.1 Name"
            r'^(The|We|This|In|For|Abstract|Introduction|Conclusion)',
        ]

        import re
        lines = text.split('\n')
        body_indicators = 0

        for line in lines:
            if len(line.strip()) > 20:  # Only check substantial lines
                for pattern in body_text_indicators:
                    if re.search(pattern, line):
                        body_indicators += 1
                        break

        return body_indicators >= 2

    def check_page_header_patterns(self, text):
        """Detect generic page header / preprint metadata leakage.

        Hardcoding paper-specific titles ("FlashAttention", "DriveLaW", etc.)
        only catches a handful of papers. Use generic patterns that recur
        across academic preprints: arXiv stamps, page numbers, conference
        venues, "Preprint", "Under review", etc.
        """
        import re
        # Each entry: (regex, label). Patterns are case-sensitive where the
        # canonical form is fixed (arXiv) and case-insensitive otherwise.
        header_patterns = [
            (re.compile(r"arXiv:\d{4}\.\d{4,5}(v\d+)?"), "arXiv stamp"),
            (re.compile(r"\bPreprint\b", re.IGNORECASE), "Preprint marker"),
            (re.compile(r"\bUnder review\b", re.IGNORECASE), "Under-review marker"),
            (re.compile(r"\bWork in progress\b", re.IGNORECASE), "WIP marker"),
            (re.compile(r"\bTechnical Report\b", re.IGNORECASE), "Technical Report header"),
            (re.compile(r"\bAccepted (at|to) "), "Acceptance notice"),
            (re.compile(r"\bPublished as a conference paper at "), "Conference notice"),
            (re.compile(r"\bConference on \w+"), "Conference name"),
            (re.compile(r"\bProceedings of "), "Proceedings header"),
            (re.compile(r"^\s*\d+\s*$", re.MULTILINE), "Standalone page number"),
        ]

        # Only consider matches in the top 20% of the OCR'd text.
        cutoff = max(1, int(len(text) * 0.2))
        head = text[:cutoff]
        for pat, label in header_patterns:
            m = pat.search(head)
            if m:
                return True, f"{label}: {m.group(0)[:60]}"

        return False, None

    def check_table_patterns(self, text):
        """Detect table content mixed with figures."""
        lines = text.split('\n')
        table_indicators = 0

        for line in lines:
            if '|' in line and line.count('|') >= 2:
                table_indicators += 1
            tokens = line.split()
            if len(tokens) >= 3 and all(t.replace('.', '').replace('-', '').isdigit() for t in tokens[:3]):
                table_indicators += 1

        return table_indicators >= 3

    def check_text_at_boundaries(self, image_path):
        """Analyze text distribution at image boundaries."""
        try:
            img = Image.open(image_path)
            width, height = img.size

            top_box = (0, 0, width, int(height * 0.15))
            bottom_box = (0, int(height * 0.85), width, height)

            top_img = img.crop(top_box)
            bottom_img = img.crop(bottom_box)

            top_text = pytesseract.image_to_string(top_img)
            bottom_text = pytesseract.image_to_string(bottom_img)

            return {
                'has_top_text': len(top_text.strip()) > 10,
                'has_bottom_text': len(bottom_text.strip()) > 10,
                'top_text': top_text.strip()[:100],
                'bottom_text': bottom_text.strip()[:100],
            }
        except Exception as e:
            return {'error': str(e)}

    def verify_figure(self, fig_file):
        """Verify a single figure for issues."""
        fig_name = fig_file.name
        text = self.extract_ocr_text(fig_file)

        # Check 1: Body text misclassification
        if self.check_body_text_patterns(text):
            self.issues[fig_name].append({
                'category': 'BODY_TEXT_MISCLASS',
                'severity': 'CRITICAL',
                'description': 'Figure contains body text/prose paragraphs',
            })
            return

        # Check 2: Page header leakage
        has_header, pattern = self.check_page_header_patterns(text)
        if has_header:
            self.issues[fig_name].append({
                'category': 'PAGE_HEADER_LEAKAGE',
                'severity': 'HIGH',
                'description': f'Contains page header: {pattern}',
            })
            return

        # Check 3: Table content
        if self.check_table_patterns(text):
            self.issues[fig_name].append({
                'category': 'WRONG_PANEL',
                'severity': 'CRITICAL',
                'description': 'Figure contains table content mixed with other content',
            })
            return

        # Check 4: Boundary text analysis
        boundary_info = self.check_text_at_boundaries(fig_file)

        if 'error' not in boundary_info:
            if boundary_info['has_bottom_text']:
                bottom = boundary_info['bottom_text']
                if any(w in bottom for w in ['Figure', 'The ', 'We ', 'This ', 'In ']):
                    self.issues[fig_name].append({
                        'category': 'CAPTION_LEAKAGE',
                        'severity': 'MEDIUM',
                        'description': 'Figure includes caption or body text at bottom',
                    })
                    return

        # No issues found
        self.clean_figures.append(fig_name)

    def verify_all(self):
        """Verify all figures in the paper."""
        if not self.figures_dir.exists():
            print(f"[ERROR] No figures directory found in {self.paper_path}")
            return False

        figure_files = sorted(self.figures_dir.glob("fig*.png"))

        if not figure_files:
            print(f"[ERROR] No figures found in {self.figures_dir}")
            return False

        print(f"\n{'='*70}")
        print(f"FIGURE EXTRACTION VERIFICATION")
        print(f"Paper: {self.paper_path.name}")
        print(f"{'='*70}")
        print(f"Scanning {len(figure_files)} figures...\n")

        for fig_file in figure_files:
            self.verify_figure(fig_file)

        return True

    def report(self):
        """Generate verification report."""
        total = len(self.clean_figures) + len(self.issues)

        print(f"\n{'='*70}")
        print(f"VERIFICATION RESULTS")
        print(f"{'='*70}\n")

        if self.issues:
            # Group by severity
            by_severity = defaultdict(list)
            for fig, issues_list in self.issues.items():
                for issue in issues_list:
                    severity = issue['severity']
                    by_severity[severity].append((fig, issue))

            # Print by severity
            for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'INFO']:
                if severity in by_severity:
                    symbol = {'CRITICAL': '[CRIT]', 'HIGH': '[HIGH]',
                              'MEDIUM': '[MED] ', 'INFO': '[INFO]'}[severity]
                    print(f"{symbol} {severity}")
                    for fig, issue in by_severity[severity]:
                        print(f"  {fig}: {issue['description']}")
                    print()

        print(f"Clean Figures: {len(self.clean_figures)}/{total}")
        print(f"Issues Found: {len(self.issues)}/{total}")

        if total > 0 and len(self.clean_figures) == total:
            print("\n[OK] All figures passed verification!")

        return {
            'total_figures': total,
            'clean_figures': len(self.clean_figures),
            'issues': len(self.issues),
            'issues_detail': dict(self.issues),
            'clean_list': self.clean_figures,
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_extraction.py <paper_directory>")
        print("Example: python verify_extraction.py /path/to/paper_name/")
        sys.exit(1)

    paper_path = Path(sys.argv[1])

    if not paper_path.exists():
        print(f"[ERROR] Paper directory not found: {paper_path}")
        sys.exit(1)

    verifier = FigureVerifier(paper_path)

    if verifier.verify_all():
        results = verifier.report()

        # Save JSON report
        report_file = paper_path / "verification_report.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nReport saved to: {report_file}")

        # Exit non-zero on issues OR if no figures were checked at all —
        # silent exit 0 with zero figures is a false success signal.
        if results['total_figures'] == 0:
            print("[ERROR] 0 figures verified — extraction likely failed",
                  file=sys.stderr)
            sys.exit(1)
        sys.exit(0 if results['issues'] == 0 else 1)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()

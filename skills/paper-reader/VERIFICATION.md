# Figure Extraction Verification Tool

Part of the paper-reader skill. Systematically verifies extracted figures for boundary detection issues.

## Overview

After extracting figures from a paper using `extract_figures.py`, use this tool to verify extraction quality and identify issues:

- **Body Text Misclassification** - Body text/prose captured as figures
- **Page Header Leakage** - Page headers included in figures
- **Wrong Panel Inclusion** - Multiple unrelated panels (table + plot) mixed
- **Text Clipping** - Important text missing from boundaries
- **Caption Leakage** - Captions or body paragraphs included in figures

## Quick Start

```bash
cd /path/to/paper_reader/skills/paper-reader/scripts
python verify_extraction.py /path/to/paper_name/
```

## Output

The tool generates:
1. **Console report** with issue summary
2. **JSON report** saved to `paper_name/verification_report.json`

### Example Output

```
======================================================================
FIGURE EXTRACTION VERIFICATION
Paper: attention_residuals
======================================================================
Scanning 9 figures...

======================================================================
VERIFICATION RESULTS
======================================================================

🔴 CRITICAL
  fig2.png: Page header: Attention Residuals
  fig4.png: Figure contains table content mixed with other content

🟠 HIGH
  fig9.png: Figure includes caption or body text at bottom

🟡 MEDIUM
  fig5.png: Missing text at top boundary

Clean Figures: 5/9
Issues Found: 4/9

📄 Report saved to: /path/to/paper_name/verification_report.json
```

## Issue Categories

### 🔴 CRITICAL (Stop, Fix Required)
- Body text misclassified as figure
- Multiple unrelated content types mixed (table + plot)
- Caption completely replaces figure content

### 🟠 HIGH (Should Fix)
- Page headers leaked into figures
- Major text blocks at top/bottom included
- Significant boundary misdetection

### 🟡 MEDIUM (Review)
- Minor caption text leakage
- Some text clipping at edges
- Annotation text partially clipped

### 🔵 INFO (Document)
- Cosmetic header decoration
- Minor text variations
- Layout quirks

## Integration with Paper Analysis

### Recommended Workflow

1. **Extract figures** using extract_figures.py
   ```bash
   python extract_figures.py /path/to/paper.pdf /output/dir
   ```

2. **Verify extraction quality**
   ```bash
   python verify_extraction.py /output/dir/paper_name/
   ```

3. **Review results**
   - Check JSON report for issues
   - If CRITICAL or HIGH issues found, investigate manually
   - Document known issues for later analysis

4. **Generate analysis** (only if figures verified clean)
   ```bash
   /paper-reader /path/to/paper.pdf
   ```

## Technical Details

### Check Sequence

1. **Body text patterns** - Regex match for section headers, prose indicators
2. **Page header patterns** - Match known conference/paper header text at top
3. **Table content** - Detect tabular structure (pipes, aligned numbers)
4. **Boundary analysis** - OCR top 15% and bottom 15% of image
5. **Caption detection** - Match "Figure X:" patterns at bottom

### OCR-Based Verification

Uses pytesseract to extract text from images, enabling precise boundary detection without relying on visual inspection alone.

**Requirements:**
```bash
pip install pytesseract pillow
apt-get install tesseract-ocr  # Linux
brew install tesseract        # macOS
```

## Known Limitations

1. **OCR accuracy** - Depends on image quality and text clarity
2. **Language diversity** - Primarily tuned for English papers
3. **Complex layouts** - Figures with mixed text/graphics may have false positives
4. **Special characters** - Math notation and symbols may not OCR reliably

## Extending the Verifier

To add custom checks for your paper:

```python
def check_custom_pattern(self, text):
    """Check for paper-specific issues."""
    if 'CustomPattern' in text:
        return True
    return False

# In verify_figure():
if self.check_custom_pattern(text):
    self.issues[fig_name].append({
        'category': 'CUSTOM_ISSUE',
        'severity': 'HIGH',
        'description': 'Custom pattern detected',
    })
```

## Regression Testing

Use this tool to verify that extract_figures.py fixes don't introduce regressions:

```bash
# Baseline verification
python verify_extraction.py papers/baseline/
# Save baseline results

# After algorithm changes
python verify_extraction.py papers/baseline/
# Compare results
```

## Troubleshooting

**"No figures found"**
- Check figure directory exists: `papers/name/figures/`
- Ensure figures are named `fig1.png`, `fig2.png`, etc.

**"OCR Error: pytesseract not installed"**
- Install: `pip install pytesseract`
- Install tesseract-ocr system package

**"High false positive rate"**
- May indicate extract_figures.py quality issues
- Review manually extracted figures vs. expected content
- Adjust text pattern thresholds as needed

## References

- `extract_figures.py` - Figure extraction implementation
- `MEMORY.md` - Known issues and fixes in extract_figures.py
- `../references/` - PDF extraction documentation

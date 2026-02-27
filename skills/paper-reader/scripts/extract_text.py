#!/usr/bin/env python3
"""extract_text.py — Extract structured text from academic PDFs using PyMuPDF.

Outputs page-delimited plain text for use as searchable ground truth
during paper analysis. The extracted text enables grep-based verification
of factual claims.

Usage:
    python3 extract_text.py <pdf_path> <output_path>

Dependencies: pymupdf (pip install pymupdf)
"""

import sys

try:
    import fitz
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
    sys.exit(1)


def extract_text(pdf_path, output_path):
    doc = fitz.open(pdf_path)
    num_pages = len(doc)
    total_chars = 0

    with open(output_path, "w", encoding="utf-8") as f:
        for page_num in range(num_pages):
            page = doc[page_num]
            text = page.get_text("text").replace("\x00", "")
            f.write(f"=== PAGE {page_num + 1} ===\n")
            f.write(text)
            f.write("\n\n")
            total_chars += len(text)

    doc.close()
    print(f"Extracted text from {num_pages} pages ({total_chars} chars) to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <pdf_path> <output_path>", file=sys.stderr)
        sys.exit(1)

    extract_text(sys.argv[1], sys.argv[2])

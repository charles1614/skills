#!/usr/bin/env python3
"""Ground source references in a wiki export against the scanned codebase.

The structural validator (validate_docs.py) cannot tell whether a
`path/file.py:123` reference points at real code. This script can: it
extracts every inline-code source reference from the export's markdown
(outside fenced code blocks) and errors when the referenced file does not
exist in the repo or the cited line range runs past the end of the file.

It is the deterministic Phase A of SKILL.md Task 7; snippet content
grounding (Phase B) is a model pass on top of this.

Usage:
  python3 verify_source_refs.py <export-dir> --repo <scanned-repo-root>

Output: JSON in the same shape as validate_docs.py
  {"status": "success" | "errors_found", "total_files": N,
   "total_refs": N, "total_errors": N, "errors": [...]}

Exit codes: 0 when all references ground; 1 when errors are found.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# `path/to/file.ext:123` or `path/to/file.ext:123-456` inside inline code.
# Requires a dot-extension and a slash-free or slashed path — bare words
# like `localhost:3000` (no dot before the colon... it has one: localhost
# has no slash and no extension-like ending) are excluded by requiring an
# alphanumeric extension of 1-10 chars right before the colon.
REF_RE = re.compile(
    r"`(?P<path>[\w./-]+\.[A-Za-z0-9]{1,10}):(?P<start>\d+)(?:-(?P<end>\d+))?`"
)

FENCE_RE = re.compile(r"^(```|~~~)")


def strip_code_fences(text: str):
    """Yield (line_number, line) for lines outside fenced code blocks."""
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield i, line


def line_count(path: Path, cache: dict) -> int:
    if path not in cache:
        try:
            with open(path, "rb") as f:
                cache[path] = sum(1 for _ in f)
        except OSError:
            cache[path] = -1
    return cache[path]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export_dir", type=Path, help="wiki export directory (e.g. .deepwiki/<project>/)")
    ap.add_argument("--repo", type=Path, required=True, help="root of the scanned codebase")
    args = ap.parse_args()

    export_dir = args.export_dir.resolve()
    repo = args.repo.resolve()
    if not export_dir.is_dir():
        print(json.dumps({"status": "errors_found", "errors": [
            {"file": str(export_dir), "line": 0, "type": "source_ref",
             "message": "export directory not found"}]}))
        sys.exit(1)
    if not repo.is_dir():
        print(json.dumps({"status": "errors_found", "errors": [
            {"file": str(repo), "line": 0, "type": "source_ref",
             "message": "--repo directory not found"}]}))
        sys.exit(1)

    errors = []
    total_refs = 0
    lc_cache = {}
    md_files = sorted(export_dir.glob("*.md"))

    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in strip_code_fences(text):
            for m in REF_RE.finditer(line):
                total_refs += 1
                rel = m.group("path").lstrip("/")
                start = int(m.group("start"))
                end = int(m.group("end") or start)
                target = repo / rel

                if not target.is_file():
                    errors.append({
                        "file": md.name, "line": lineno, "type": "source_ref",
                        "message": f"referenced file not found in repo: {rel}",
                    })
                    continue
                n = line_count(target, lc_cache)
                if n >= 0 and end > n:
                    errors.append({
                        "file": md.name, "line": lineno, "type": "source_ref",
                        "message": f"{rel}:{start}-{end} out of range (file has {n} lines)",
                    })
                elif start > end:
                    errors.append({
                        "file": md.name, "line": lineno, "type": "source_ref",
                        "message": f"{rel}:{start}-{end} has start > end",
                    })

    print(json.dumps({
        "status": "success" if not errors else "errors_found",
        "total_files": len(md_files),
        "total_refs": total_refs,
        "total_errors": len(errors),
        "errors": errors,
    }, indent=2))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

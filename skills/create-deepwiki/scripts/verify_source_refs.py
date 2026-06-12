#!/usr/bin/env python3
"""Ground source references in a wiki export against the scanned codebase.

The structural validator (validate_docs.py) cannot tell whether a
`path/file.py:123` reference points at real code. This script can: it
extracts every inline-code source reference from the export's markdown
(outside fenced code blocks) and errors when the referenced file does not
exist in the repo or the cited line range runs past the end of the file.

It also grounds attributed code snippets deterministically: a fenced code
block whose first line is an attribution comment (`# From: path/file.py:10-20`,
multi-range `# From: README.md:46-49, :62-63, :79` supported) is checked
line-by-line against the cited range(s) of the real file. Snippets whose
content does not match get a `snippet_mismatch` error; long code fences with
no attribution get a `snippet_unattributed` warning (a review worklist —
warnings do not fail the run).

This is the deterministic core of SKILL.md Task 7 Phases A and B; the model
pass investigates each reported mismatch and unattributed snippet.

Usage:
  python3 verify_source_refs.py <export-dir> --repo <scanned-repo-root> \
      [--snippet-threshold 0.7]

Output: JSON in the same shape as validate_docs.py
  {"status": "success" | "errors_found", "total_files": N, "total_refs": N,
   "total_snippets": N, "total_errors": N, "total_warnings": N,
   "errors": [...], "warnings": [...]}

Exit codes: 0 when all references and snippets ground; 1 when errors are
found (warnings alone do not affect the exit code).
"""

import argparse
import json
import re
import sys
from pathlib import Path

# `path/to/file.ext:123` or `path/to/file.ext:123-456` inside inline code.
# Requires an alphanumeric extension of 1-10 chars right before the colon so
# bare words like `localhost:3000` are excluded.
REF_RE = re.compile(
    r"`(?P<path>[\w./-]+\.[A-Za-z0-9]{1,10}):(?P<start>\d+)(?:-(?P<end>\d+))?`"
)

FENCE_RE = re.compile(r"^(```+|~~~+)\s*(\S*)")

# Attribution header on a snippet's first line: a comment token, "From:",
# a path with extension, and one or more line ranges. Later ranges may
# repeat the path or use the shorthand `:N-M` (path inherited).
ATTR_RE = re.compile(
    r"^\s*(?:#|//|--|;|%%|\*|/\*|<!--)+\s*From:\s*"
    r"(?P<path>[\w./-]+\.[A-Za-z0-9]{1,10}):"
    r"(?P<ranges>\d+(?:-\d+)?(?:\s*,\s*:?\d+(?:-\d+)?)*)"
)

RANGE_RE = re.compile(r":?(\d+)(?:-(\d+))?")

# Fence languages that never hold attributable source snippets
NON_SOURCE_LANGS = {"mermaid", "text", "markdown", "md", "", "console", "diff"}

COMMENT_PREFIXES = ("#", "//", "--", ";", "%", "*", "/*", "<!--")

MIN_UNATTRIBUTED_LINES = 5  # fences shorter than this skip the warning
MIN_MATCH_CHARS = 4  # substring matches shorter than this don't count


def parse_markdown(text: str):
    """Split markdown into (outside_lines, fences).

    outside_lines: list of (line_number, line) outside fenced code blocks.
    fences: list of (start_line, lang, [lines]) for each fenced block,
    where start_line is the line number of the first line INSIDE the fence.
    """
    outside = []
    fences = []
    in_fence = False
    fence_lang = ""
    fence_start = 0
    fence_lines = []

    for i, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line.strip())
        if m and not in_fence:
            in_fence = True
            fence_lang = m.group(2).lower()
            fence_start = i + 1
            fence_lines = []
            continue
        if m and in_fence and not m.group(2):
            in_fence = False
            fences.append((fence_start, fence_lang, fence_lines))
            continue
        if in_fence:
            fence_lines.append(line)
        else:
            outside.append((i, line))

    return outside, fences


def parse_attr_ranges(ranges_str: str):
    """Parse '46-49, :62-63, :79' into [(46, 49), (62, 63), (79, 79)]."""
    ranges = []
    for m in RANGE_RE.finditer(ranges_str):
        start = int(m.group(1))
        end = int(m.group(2) or start)
        ranges.append((start, end))
    return ranges


def normalize(line: str) -> str:
    return " ".join(line.split())


def is_comment_only(norm_line: str) -> bool:
    return norm_line.startswith(COMMENT_PREFIXES)


def file_lines(path: Path, cache: dict):
    if path not in cache:
        try:
            cache[path] = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            cache[path] = None
    return cache[path]


def check_snippet(fence_lines, ranges, source_lines, threshold):
    """Match a snippet's countable lines against the cited source range(s).

    Countable lines exclude blanks, elision markers (...), and comment-only
    lines (a model-added explanatory comment must not fail an otherwise
    verbatim snippet). A line matches when its normalized form is a
    substring of a cited source line or vice versa — this tolerates the
    docs trimming trailing comments or the source having extra indentation.

    Returns (matched, countable, unmatched_examples).
    """
    cited = []
    for start, end in ranges:
        cited.extend(source_lines[start - 1:end])
    cited_norm = [normalize(l) for l in cited if normalize(l)]

    matched = 0
    countable = 0
    unmatched = []

    for raw in fence_lines:
        norm = normalize(raw)
        if not norm:
            continue
        stripped_ellipsis = norm.lstrip("".join(set("#/-;%*<!"))).strip()
        if stripped_ellipsis in ("...", "…") or norm in ("...", "…"):
            continue
        if is_comment_only(norm):
            continue
        countable += 1
        hit = False
        for src in cited_norm:
            shorter = min(len(norm), len(src))
            if shorter >= MIN_MATCH_CHARS and (norm in src or src in norm):
                hit = True
                break
            if norm == src:  # very short identical lines still count
                hit = True
                break
        if hit:
            matched += 1
        elif len(unmatched) < 3:
            unmatched.append(norm[:80])

    ratio = (matched / countable) if countable else 1.0
    return matched, countable, unmatched, ratio >= threshold


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("export_dir", type=Path, help="wiki export directory (e.g. .deepwiki/<project>/)")
    ap.add_argument("--repo", type=Path, required=True, help="root of the scanned codebase")
    ap.add_argument("--snippet-threshold", type=float, default=0.7,
                    help="fraction of a snippet's countable lines that must match the cited range (default 0.7)")
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
    warnings = []
    total_refs = 0
    total_snippets = 0
    lc_cache = {}
    lines_cache = {}
    md_files = sorted(export_dir.glob("*.md"))

    for md in md_files:
        text = md.read_text(encoding="utf-8", errors="replace")
        outside, fences = parse_markdown(text)

        # Phase A: inline `path:line` references outside code fences
        for lineno, line in outside:
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
                if target not in lc_cache:
                    src = file_lines(target, lines_cache)
                    lc_cache[target] = len(src) if src is not None else -1
                n = lc_cache[target]
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

        # Phase B core: attributed snippet grounding
        for fence_start, lang, fence_lines in fences:
            if lang in NON_SOURCE_LANGS:
                continue
            attr = ATTR_RE.match(fence_lines[0]) if fence_lines else None
            if not attr:
                if len([l for l in fence_lines if l.strip()]) >= MIN_UNATTRIBUTED_LINES:
                    warnings.append({
                        "file": md.name, "line": fence_start,
                        "type": "snippet_unattributed", "severity": "warning",
                        "message": f"{lang or 'code'} fence has no 'From: path:N-M' attribution — verify it is an example, not an unattributed quote",
                    })
                continue

            total_snippets += 1
            rel = attr.group("path").lstrip("/")
            ranges = parse_attr_ranges(attr.group("ranges"))
            target = repo / rel
            source = file_lines(target, lines_cache)

            if source is None or not target.is_file():
                errors.append({
                    "file": md.name, "line": fence_start, "type": "snippet_attr_ref",
                    "message": f"snippet attributed to missing file: {rel}",
                })
                continue

            bad_range = next(((s, e) for s, e in ranges if s > e or e > len(source)), None)
            if bad_range:
                errors.append({
                    "file": md.name, "line": fence_start, "type": "snippet_attr_ref",
                    "message": f"snippet attribution {rel}:{bad_range[0]}-{bad_range[1]} out of range (file has {len(source)} lines)",
                })
                continue

            matched, countable, unmatched, ok = check_snippet(
                fence_lines[1:], ranges, source, args.snippet_threshold)
            if not ok:
                errors.append({
                    "file": md.name, "line": fence_start, "type": "snippet_mismatch",
                    "message": (
                        f"snippet attributed to {rel}:{attr.group('ranges')} matches "
                        f"{matched}/{countable} lines; unmatched e.g. {unmatched}"
                    ),
                })

    print(json.dumps({
        "status": "success" if not errors else "errors_found",
        "total_files": len(md_files),
        "total_refs": total_refs,
        "total_snippets": total_snippets,
        "total_errors": len(errors),
        "total_warnings": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }, indent=2))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()

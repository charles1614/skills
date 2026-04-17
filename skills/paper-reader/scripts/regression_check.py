#!/usr/bin/env python3
"""regression_check.py — Guardrail for extract_figures.py changes.

Walks a root directory of paper output folders, loads each
`figures/figures_manifest.json`, and diffs it against a pinned baseline.
Flags per-figure changes that are large enough to warrant manual review.

Use this BEFORE shipping any change to extract_figures.py:

    # First time only: create the baseline (after re-extracting the corpus)
    python3 regression_check.py --snapshot --root /path/to/paper_reader \\
        --baseline /path/to/baseline_manifests.json

    # Every subsequent change
    python3 regression_check.py --root /path/to/paper_reader \\
        --baseline /path/to/baseline_manifests.json

Exits 0 if all figures are within tolerance, 1 otherwise.
"""

import argparse
import json
import sys
from pathlib import Path


# Tolerances — chosen so routine extraction noise doesn't fire but real
# regressions do. A figure growing or shrinking by >10% is almost always
# a real boundary change worth eyeballing.
WIDTH_PCT = 0.10
HEIGHT_PCT = 0.10
CLIP_ABS_PT = 5.0
PAGE_CHANGE = True  # any page change is flagged


def load_manifest(manifest_path):
    """Return {(paper_slug, fig_num): fig_dict}."""
    with open(manifest_path) as f:
        figs = json.load(f)
    paper_slug = manifest_path.parent.parent.name
    return {(paper_slug, f["fig_num"]): f for f in figs}


def collect_all_manifests(root):
    """Collect every figures_manifest.json under root into a single dict."""
    all_figs = {}
    papers = []
    root = Path(root)
    for m in sorted(root.glob("*/figures/figures_manifest.json")):
        papers.append(m.parent.parent.name)
        all_figs.update(load_manifest(m))
    return all_figs, papers


def snapshot(root, baseline_path):
    all_figs, papers = collect_all_manifests(root)
    # Store as list of {paper, fig_num, ...fields} for stable diffing
    records = []
    for (paper, fn), fig in sorted(all_figs.items()):
        rec = {
            "paper": paper,
            "fig_num": fn,
            "filename": fig["filename"],
            "page": fig["page"],
            "width": fig["width"],
            "height": fig["height"],
            "clip_rect": fig["clip_rect"],
        }
        records.append(rec)
    with open(baseline_path, "w") as f:
        json.dump({"papers": papers, "figures": records}, f, indent=2)
    print(f"Baseline written: {len(records)} figures across {len(papers)} papers")
    print(f"  -> {baseline_path}")


def _fig_key(rec):
    return (rec["paper"], rec["fig_num"])


def _pct_change(a, b):
    """Return abs relative change, guarding against zero."""
    if a == 0 and b == 0:
        return 0.0
    if a == 0:
        return 1.0
    return abs(b - a) / a


def _clip_max_delta(a_clip, b_clip):
    """Max absolute delta across the 4 clip-rect coordinates."""
    return max(abs(a - b) for a, b in zip(a_clip, b_clip))


def diff(root, baseline_path):
    with open(baseline_path) as f:
        baseline_data = json.load(f)
    baseline = {_fig_key(r): r for r in baseline_data["figures"]}

    current, _ = collect_all_manifests(root)

    issues = []  # (severity, paper, fig_num, description)

    # Check every baseline figure for presence and deltas
    for key, base in baseline.items():
        paper, fn = key
        cur = current.get(key)
        if cur is None:
            issues.append(("MISSING", paper, fn,
                           f"figure disappeared (baseline {base['width']}x{base['height']})"))
            continue

        notes = []
        if cur["page"] != base["page"] and PAGE_CHANGE:
            notes.append(f"page {base['page']}->{cur['page']}")
        w_pct = _pct_change(base["width"], cur["width"])
        if w_pct > WIDTH_PCT:
            notes.append(f"width {base['width']}->{cur['width']} ({100 * w_pct:+.1f}%)")
        h_pct = _pct_change(base["height"], cur["height"])
        if h_pct > HEIGHT_PCT:
            notes.append(f"height {base['height']}->{cur['height']} ({100 * h_pct:+.1f}%)")
        clip_d = _clip_max_delta(base["clip_rect"], cur["clip_rect"])
        if clip_d > CLIP_ABS_PT:
            notes.append(f"clip_rect max-delta {clip_d:.1f}pt")

        if notes:
            issues.append(("CHANGE", paper, fn, "; ".join(notes)))

    # Check for new figures not in baseline
    for key, cur in current.items():
        if key not in baseline:
            paper, fn = key
            issues.append(("NEW", paper, fn,
                           f"figure added ({cur['width']}x{cur['height']})"))

    # Report
    if not issues:
        print(f"OK: all {len(current)} figures within tolerance of baseline "
              f"({len(baseline)} figures).")
        return 0

    by_sev = {"MISSING": [], "CHANGE": [], "NEW": []}
    for sev, paper, fn, desc in issues:
        by_sev[sev].append((paper, fn, desc))

    for sev in ("MISSING", "CHANGE", "NEW"):
        if not by_sev[sev]:
            continue
        print(f"\n--- {sev} ({len(by_sev[sev])}) ---")
        for paper, fn, desc in sorted(by_sev[sev]):
            print(f"  {paper} fig{fn}: {desc}")

    print(f"\nTotal: {len(issues)} issue(s) across {len({(p, n) for _, p, n, _ in issues})} figure(s).")
    return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True,
                        help="Root directory containing paper output folders")
    parser.add_argument("--baseline", required=True,
                        help="Path to baseline_manifests.json (read for diff, "
                             "written for --snapshot)")
    parser.add_argument("--snapshot", action="store_true",
                        help="Write current state as new baseline instead of diffing")
    args = parser.parse_args()

    if args.snapshot:
        snapshot(args.root, args.baseline)
        return 0
    return diff(args.root, args.baseline)


if __name__ == "__main__":
    sys.exit(main())

# Paper Reader

A Claude Code skill for reading AI/CS academic papers and generating detailed Chinese analysis reports.

## Skill

Located at `.claude/skills/paper-reader/`. Invoke via `/paper-reader <path-or-url>`.

## TeX Environment

- XeLaTeX via TinyTeX: `~/.local/share/mise/installs/tinytex/2026.02/`
- First-time setup: `bash .claude/skills/paper-reader/scripts/setup-tex.sh`
- Chinese fonts: Noto Serif CJK SC, Noto Sans CJK SC, Noto Sans Mono CJK SC

## Usage Examples

```
/paper-reader /path/to/paper.pdf
/paper-reader https://arxiv.org/abs/2401.12345
```

## Regression Testing (dev workflow)

When modifying `.claude/skills/paper-reader/scripts/extract_figures.py`, use the
regression harness to catch silent extraction regressions across the local
27-paper corpus.

The baseline lives at `.claude/skills/paper-reader/scripts/baseline_manifests.json`
and is **local to this directory** — never check it into the upstream skill repo,
since other users have different corpora.

**1. Snapshot the current state as the baseline** (one-off, only after you've
visually confirmed the corpus is in a known-good state):

```
python3 .claude/skills/paper-reader/scripts/regression_check.py \
  --root . \
  --baseline .claude/skills/paper-reader/scripts/baseline_manifests.json \
  --snapshot
```

**2. After every change to `extract_figures.py`**, re-extract all papers and
diff against the baseline:

```
for d in */paper.pdf; do
  python3 .claude/skills/paper-reader/scripts/extract_figures.py \
    "$d" "$(dirname "$d")/figures/" > /dev/null
done
python3 .claude/skills/paper-reader/scripts/regression_check.py \
  --root . \
  --baseline .claude/skills/paper-reader/scripts/baseline_manifests.json
```

The harness exits 0 when every figure is within tolerance (width/height delta ≤ 10%
and clip-rect delta ≤ 5pt). Non-zero exit means at least one figure changed
materially — open the listed figures, decide if each change is an improvement or a
regression, and only re-snapshot the baseline once all changes are confirmed wins.

For per-paper structural checks (body-text leakage, header artifacts, aspect-ratio
anomalies, etc.) the skill itself runs `validate_figures.py` at Step 1.6 — that's a
different tool aimed at end users and not part of this dev workflow.

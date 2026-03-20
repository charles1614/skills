---
name: paper-reader
description: >-
  Read AI/CS academic papers and generate detailed Chinese analysis reports in
  both Markdown and LaTeX formats. Use this skill whenever the user wants to
  analyze, summarize, review, or read an academic paper. Supports local PDF files
  and arxiv links. Triggers on: paper analysis, arxiv link, PDF paper review,
  academic paper summary, 论文分析, 论文阅读, 读论文, 分析论文.
---

# Paper Reader Skill

Read an AI/CS academic paper and produce a rigorous Chinese-language analysis report at senior PhD researcher level. Output both a Markdown (`.md`) file and an elegantly typeset LaTeX (`.tex`) file that compiles with XeLaTeX.

## Skill Files Location

This skill's supporting files are located relative to this SKILL.md:

- `references/analysis-prompt.md` — The full 10-section analysis prompt and writing guidelines
- `references/latex-guide.md` — LaTeX template usage guide, xeCJK pitfalls, and code examples
- `assets/template.tex` — The XeLaTeX template file
- `scripts/setup-tex.sh` — One-time TeX package installer
- `scripts/extract_figures.py` — Smart PDF figure extraction (uses PyMuPDF: caption detection + region rendering)
- `scripts/extract_text.py` — PDF text layer extraction (uses PyMuPDF: page-delimited plain text for grep-based verification)

**IMPORTANT**: At the start of every invocation, read `references/analysis-prompt.md` to load the full analysis structure and guidelines. This is mandatory — do not rely on memory of the prompt.

## Workflow

### Step 1: Parse Input

Determine the input type from the user's message:

**Local PDF file:**
- The user provides a file path (e.g., `/path/to/paper.pdf`)
- Read the first 1-2 pages of the PDF to extract the title, then read the full paper
- For large PDFs (50+ pages): read in chunks, prioritizing Abstract, Introduction, Method/System Design, Experiments, and Conclusion. **Do NOT skip Appendices** — they often contain critical training details (hyperparameters, compute, ablations) absent from main sections. The `paper_text.txt` (Step 1.3) covers all pages and enables grep-based lookup of appendix content without re-reading.

**Arxiv link:**
- The user provides an arxiv URL (e.g., `https://arxiv.org/abs/2401.12345` or `https://arxiv.org/pdf/2401.12345`)
- Extract the paper ID from the URL
- Download the PDF: `curl -L -o /tmp/paper_<id>.pdf "https://arxiv.org/pdf/<id>.pdf"`
- Read the first 1-2 pages to extract the title, then read the full paper

**Determine output directory early.** After reading the title page, immediately:
1. Sanitize the paper title: lowercase, replace spaces with underscores, remove special characters, truncate to 60 chars
2. Create the output subfolder:
   - If input is a local PDF: `<pdf_directory>/<sanitized_name>/`
   - If input is an arxiv link: `<current_working_directory>/<sanitized_name>/`
3. Run `mkdir -p <output_dir>/figures/`

This must happen BEFORE Steps 1.3/1.5/1.7 so extraction scripts have a valid output directory.

**CRITICAL: Factual accuracy.** Author names, affiliations, venue, and year must be **copied character-by-character from the PDF title page**. Never guess or rely on model knowledge. If the PDF text is ambiguous, re-read the title page carefully. Getting author names or institutions wrong is unacceptable.

**CRITICAL: Technical parameters must come from text, not figures.** When describing system architecture, data formats, algorithms, or any quantitative design parameters (e.g., block sizes, dimensions, precision formats, scaling strategies), extract values **exclusively from the paper's prose descriptions** — never infer them from figures or diagrams. Figures often show simplified examples or specific instances that differ from the general specification. For example, a figure may illustrate a 16×32 matrix, but the actual block size might be 16 elements. Always cross-check: if a parameter appears in both text and figure, the text description takes precedence.

**Do NOT pause to confirm with the user.** Proceed directly to text/figure extraction and analysis generation. Only pause if the PDF cannot be read or downloaded.

### Step 1.3 & 1.5: Extract Text and Figures (parallel)

**Prerequisite**: Ensure pymupdf is installed before running either extraction (one-time):
```
python3 -c "import fitz" 2>/dev/null || pip3 install pymupdf
```

Then run Steps 1.3 and 1.5 **in parallel** (they are independent):

#### Step 1.3: Extract Text

Extract the PDF's text layer as a searchable plain text file. This serves as the **ground truth** for verifying factual claims later:

```
python3 <skill-directory>/scripts/extract_text.py <pdf_path> <output_dir>/paper_text.txt
```

The output is page-delimited (`=== PAGE N ===`) plain text. This file is used in two ways:
1. **During writing (Step 2)**: grep to verify claims before writing them
2. **During verification (Step 2.5)**: haiku subagent cross-checks the generated .tex against this file

**If the output is very small (<1000 chars)**, the PDF likely has no text layer (scanned document). In this case, rely more heavily on `paper_figures_text.txt` (Step 1.7) and visual PDF reading, and be extra cautious with factual claims.

#### Step 1.5: Extract Figures

Extract figures **automatically** — no manual review unless extraction fails:

1. **Run the extraction script**:
   ```
   python3 <skill-directory>/scripts/extract_figures.py <pdf_path> <output_dir>/figures/
   ```
   This automatically detects figure captions (supports `Fig. N:`, `Figure N:`, `Figure N |`, `Figure N.` formats), finds figure regions using image blocks + vector drawings, and renders at 300 DPI.

2. **Only if extraction found 0 figures**: check if the paper uses a non-standard caption format and fall back to rendering key pages with `pdftoppm`.

3. **Map figures to analysis sections** using the output manifest:
   - Architecture/model diagrams → Section 5: 技术方法与系统架构
   - Result plots/charts → Section 6: 实验设计与评估分析
   - Comparison figures → Section 7: 批判性分析 or Section 3: 创新贡献与研究定位
   - Overview/pipeline figures → Section 2: 核心摘要与定性评估

   **Do NOT review every figure individually** unless extraction reported errors. Trust the script output and proceed to analysis.

### Step 1.7: Extract Figure Text (via haiku)

**Depends on**: Step 1.5 must complete first (needs `figures/` directory and `figures_manifest.json`).

Some information appears **only in figures** (e.g., training pipeline diagrams showing token counts, architecture diagrams with dimension labels) and is absent from the PDF text layer. Extract this text using a cheap model.

Launch a Task agent with `model: "haiku"` and `subagent_type: "general-purpose"`. Include these exact instructions in the prompt:

```
Read each figure image in <output_dir>/figures/ using the Read tool (it supports PNG images).
Also read <output_dir>/figures/figures_manifest.json to get caption and page info for each figure.

For each figure, write down ALL visible text: labels, numbers, annotations, flow chart box text,
axis labels, table cells, legend text. Be thorough — even small numbers matter.

Write the output to <output_dir>/paper_figures_text.txt in this format:

=== FIGURE N (page P): [caption from manifest] ===
[all visible text transcribed from the figure image]

(blank line between figures)
```

Replace `<output_dir>` with the actual path in the prompt.

This file is small (~500 tokens of labels/numbers) and serves as supplementary evidence alongside `paper_text.txt`. Token budget: ~15 images × ~1K tokens each ≈ ~15K haiku input tokens for images, plus the output file is tiny.

### Step 2: Generate LaTeX Analysis (primary output)

**Depends on**: Steps 1.3 and 1.7 must both complete before starting (needs `paper_text.txt` and `paper_figures_text.txt`).

**The `.tex` file is the source of truth.** Write it directly — do NOT write Markdown first.

**CRITICAL: Use extracted text as ground truth during writing.** For any factual claim you write — especially training configuration (optimizer, learning rate, batch size, compute), system parameters (dimensions, layer counts), and experimental numbers — **grep `paper_text.txt` first** to verify the claim exists in the paper's prose. If the info is not found in `paper_text.txt`, check `paper_figures_text.txt` for figure-only info. If not found in either, do NOT write the claim — either omit it or explicitly mark as「原文未明确提及」. The visual PDF reading provides understanding of structure, figures, and formulas; the extracted text files are the authoritative source for factual claims.

1. Read the full analysis prompt from `references/analysis-prompt.md` in this skill's directory
2. Read the LaTeX template from `assets/template.tex` and the guide from `references/latex-guide.md`
3. Use the output directory already created in Step 1 (the `<sanitized_name>/` subfolder)
4. Analyze the paper following the 10-section structure defined in the prompt
5. Apply the adaptive depth guidelines based on paper type (systems/ML/theory/survey/empirical)
6. Write the `.tex` file directly into the subfolder, using native LaTeX formatting throughout:
   - Replace all template placeholders (`%PAPER_TITLE%`, `%PAPER_AUTHORS%`, etc.). **For `pdftitle` in `\hypersetup{}`**, strip or escape special LaTeX characters (`%`, `#`, `&`, `_`, `~`, `^`, `{`, `}`) since hyperref does not handle them gracefully.
   - Use native LaTeX constructs — never think in Markdown then convert:
     - `\section{}`, `\subsection{}`, `\subsubsection{}` for headings
     - `\paragraph{}` for bold titled paragraphs (e.g., challenges, subsystem descriptions)
     - `\textbf{}` only for inline emphasis within a sentence
     - `\begin{itemize}` / `\begin{enumerate}` for lists
     - `booktabs` tables (`\toprule`, `\midrule`, `\bottomrule`)
     - `\begin{equation}` / `$...$` for math
   - Use the tcolorbox environments from the template:
     - `keyinsight` for TL;DR / core points
     - `strengthbox` for advantages
     - `weaknessbox` for limitations
     - `mathbox` for important formulas
     - `infobox` for metadata tables
   - Follow all xeCJK rules from the LaTeX guide (especially: `\text{}` for Chinese in math, `~` spacing, ASCII-only labels)
   - **Embed extracted figures** using `\includegraphics` inside `figure` environments:
     ```latex
     \begin{figure}[htbp]
     \centering
     \includegraphics[width=0.85\textwidth]{figures/fig1_name.png}
     \caption{中文图题描述}
     \label{fig:name}
     \end{figure}
     ```
   - Use relative paths (`figures/`) — the `.tex` file and `figures/` directory are in the same parent directory
   - See `references/latex-guide.md` for single-figure, side-by-side, and full-width examples
   - Reference figures in text with `如图~\ref{fig:name} 所示`

   Note: `analysis-prompt.md` uses Markdown syntax for figure embedding (`![]()`); translate these to LaTeX equivalents when writing.

### Step 2.5: Two-Phase Factual Verification

After writing the `.tex` file, perform systematic verification using both automated checking and manual review. **This step is mandatory — do not skip it.**

#### Phase A: Haiku Mechanical Verification

Launch a Task agent with `model: "haiku"` and `subagent_type: "general-purpose"` to perform mechanical claim-vs-evidence checking:

**Agent inputs** (pass file paths in the prompt):
- `<output_dir>/paper_text.txt` — primary evidence (PDF text layer)
- `<output_dir>/paper_figures_text.txt` — supplementary evidence (figure OCR)
- `<output_dir>/<filename>.tex` — the generated analysis (content sections only, skip LaTeX preamble)

**Agent task**: For every factual claim in the `.tex` file, search both evidence files for supporting text. Focus especially on:
- **All numerical values**: percentages, counts, dimensions, sizes, token counts, speedups
- **Training configuration**: optimizer, learning rate, batch size, compute resources, training duration
- **Parameter specifications**: layer counts, head dimensions, expert counts, vocabulary size
- **Attribution claims**: "this paper proposes X" vs "prior work proposes X"
- **Named entities**: model names, method names, dataset names, framework names

For each claim, output one of:
```
VERIFIED: [claim] — found: "[exact quote from evidence]" (page N / figure N)
NOT FOUND: [claim] — no supporting text in paper_text.txt or paper_figures_text.txt
MISMATCH: [claim in tex] says X, but evidence says Y (page N)
```

**Agent output**: Write the verification report to `<output_dir>/verification_report.txt`.

#### Phase B: Opus Review and Fix

After receiving the haiku verification report, the main model reviews and acts on flagged items:

1. **Read `verification_report.txt`**
2. For `NOT FOUND` claims:
   - If the claim is a training config, parameter, or number: **remove it** or mark as「原文未明确提及」
   - If the claim is a reasonable paraphrase or derivation: keep but verify by re-reading the specific PDF page visually
3. For `MISMATCH` claims:
   - **Correct the `.tex`** to match the paper's actual text
   - If the mismatch is minor (wording difference, not factual): keep the paraphrase
4. For systematic issues (e.g., many NOT FOUND in one section): re-read the relevant PDF pages and rewrite that section
5. If uncertain about a claim after review, add near-verbatim quotes: "（原文表述：'...'）"

### Step 3: Compile LaTeX

**IMPORTANT: Shell commands (`xelatex`, `ls`, `kpsewhich`, `curl`, `python3`, etc.) are already in PATH via mise. Call them directly — do NOT prepend `export PATH=...` or use full paths. Just run `xelatex ...` directly.**

1. **Check TeX environment** (first time only):
   ```
   kpsewhich xeCJK.sty
   ```
   If xeCJK is not found, run the setup script:
   ```
   bash <skill-directory>/scripts/setup-tex.sh
   ```

2. **Compile** (from the output directory):
   ```
   cd <output-directory>
   xelatex -interaction=nonstopmode <filename>.tex
   xelatex -interaction=nonstopmode <filename>.tex
   ```
   Two passes are needed for table of contents and cross-references.

3. **Handle compilation errors**:
   - Read the `.log` file to identify the error
   - Common fixes are documented in `references/latex-guide.md`
   - Fix the `.tex` file and recompile
   - Maximum 3 retry attempts

### Step 4: Derive Markdown from LaTeX

After the PDF compiles successfully, run the conversion script to produce the `.md` file:

```bash
python3 <skill-directory>/scripts/tex2md.py <output_dir>/<filename>.tex <output_dir>/<filename>.md
```

The script handles all environments from the template (sections, keyinsight/mathbox/infobox tcolorboxes, figure, table/tabular, itemize/enumerate, equation/align, lstlisting) and exits with code 1 if any `\includegraphics` in the `.tex` is missing from the output `.md`. If it exits 1, read the error output — it prints the missing figure paths — and investigate why those figure environments were not processed.

The script output looks like:
```
Written : /path/to/filename.md
Figures : 9 in .tex, 9 in .md
```

**Do not derive the Markdown manually.** The script is deterministic and will never drop figures.

### Step 5: Report Results

Report output files and a **pipeline diagnostic summary** showing the status of each stage. For every stage, report whether it completed normally or triggered a fallback.

```
Analysis complete:
- PDF: /path/to/paper_analysis.pdf
- Markdown: /path/to/paper_analysis.md
- LaTeX source: /path/to/paper_analysis.tex
- Figures: /path/to/figures/ (N figures extracted)
- Verification: /path/to/verification_report.txt (N verified, N not found, N mismatch)

Pipeline summary:
| Stage | Status | Notes |
|-------|--------|-------|
| Step 1: PDF reading | OK | Read N pages |
| Step 1.3: Text extraction | OK / FALLBACK | Extracted N chars (FALLBACK: <1000 chars, scanned PDF) |
| Step 1.5: Figure extraction | OK / FALLBACK | N figures (FALLBACK: 0 figures, used pdftoppm) |
| Step 1.7: Figure text (haiku) | OK / FALLBACK / SKIPPED | N figures transcribed (FALLBACK: agent failed, skipped) |
| Step 2: LaTeX writing | OK | N grep verifications performed |
| Step 2.5A: Haiku verification | OK | N verified, N not found, N mismatch |
| Step 2.5B: Opus review | OK / REWROTE | N fixes applied (REWROTE: section X rewritten) |
| Step 3: LaTeX compilation | OK / RETRIED | Compiled in N passes (RETRIED: N retries needed) |
| Step 4: Markdown derivation | OK | |
```

Use `OK` when the stage completed normally with no fallbacks. Use `FALLBACK`, `SKIPPED`, `RETRIED`, or `REWROTE` when an alternative path was taken. Include brief notes explaining what happened.

This summary helps the user assess confidence in the analysis — stages with fallbacks may indicate areas where accuracy is lower.

## Quality Requirements

- **LaTeX is the source of truth.** Write `.tex` first; derive `.md` mechanically. Never write Markdown first then convert to LaTeX.
- **All analysis text must be in Chinese.** Technical terms should appear as English in parentheses on first use, then English-only afterward.
- **Mathematical formulas are mandatory** where the paper contains math. Use proper LaTeX notation.
- **Critical analysis section must contain genuine critique** — not just a summary of the paper's claims. Identify real weaknesses, questionable assumptions, and missing experiments.
- **Data must be precise** — cite specific numbers from the paper (accuracy percentages, speedup factors, etc.), not vague descriptions.
- **LaTeX must compile cleanly** with zero errors on `xelatex`. Warnings are acceptable but errors are not.

## Output File Naming Convention

Given a paper titled "Attention Is All You Need":
```
attention_is_all_you_need/              ← dedicated subfolder
  attention_is_all_you_need_analysis.md
  attention_is_all_you_need_analysis.tex
  attention_is_all_you_need_analysis.pdf
  paper_text.txt                        ← extracted PDF text (Step 1.3)
  paper_figures_text.txt                ← figure OCR text (Step 1.7)
  verification_report.txt               ← haiku verification output (Step 2.5)
  figures/
    fig1.png    ← auto-extracted by extract_figures.py
    fig2.png
    fig3.png
    figures_manifest.json
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| PDF too large to read at once | Read pages in batches: first pages 1-20, then 20-40, etc. Focus on key sections. |
| PDF password-protected or corrupted | Ask user to provide an unprotected version. `extract_figures.py` will print a clear error. |
| Figure extraction finds 0 figures | Paper may use non-standard caption format. Check with `grep -i "figure\|fig\." <pdf_text>` and fall back to `pdftoppm`. |
| Arxiv download blocked | Ask user to download the PDF manually and provide the local path. |
| XeLaTeX not found | TinyTeX should already be in PATH via mise. Just run `xelatex` directly. If truly missing, check `which xelatex` and ensure mise is configured. |
| Chinese fonts not found | Run `fc-list :lang=zh` to check available fonts. Adjust template font names if needed. |
| tcolorbox errors | Run `scripts/setup-tex.sh` to install missing packages. |
| Text extraction yields empty/tiny file | PDF is likely scanned (no text layer). Rely on `paper_figures_text.txt` and visual reading. Be extra cautious with factual claims — mark uncertain items as「原文未明确提及」. |
| Haiku figure text agent fails | Proceed without `paper_figures_text.txt`. Note in verification that figure-only info was not cross-checked. |
| `paper_text.txt` has garbled characters | Some PDFs use custom fonts with broken Unicode mappings. Try `page.get_text("rawdict")` as fallback, or rely on visual reading. |

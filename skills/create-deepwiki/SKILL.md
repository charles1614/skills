---
name: create-deepwiki
description: Generate comprehensive deepwiki-style architecture documentation with deep codebase analysis, Architecture Decision Records (ADRs), Mermaid diagrams, and structured multi-file output. When the repo is the open-source release of a paper and a .paper/ folder is present, also documents how the implementation diverges from the paper. Use when users want to create architecture documentation, generate a wiki for a codebase, document a project's structure, or need comprehensive technical documentation.
license: Complete terms in LICENSE.txt
---

# DeepWiki-Style Architecture Documentation Generator

Generate comprehensive, structured architecture documentation with deep codebase analysis.

**Best for**: Complex codebases requiring detailed analysis - frameworks, libraries, services, platforms, tooling, and systems.

**Output**: Multi-file documentation to `.deepwiki/<project-name>/` including:
- Structured markdown documentation files (flat — no subdirectories for .md)
- Architecture Decision Records (ADRs) as a numbered section with numbered children
- Mermaid diagrams for architecture visualization
- Image assets in `.deepwiki/<project-name>/img/`

**STRICT OUTPUT BOUNDARY — non-negotiable.** Every artifact this run
produces lives under the output root, resolved against the project root
where the skill runs. Never write to the repo root, `docs/` (that is
committed project documentation, not generated output), `content/` of a
static-site project (Hugo/Nuxt/Gatsby treat it as build source), the
scanned codebase's tracked files, or the bare current working directory.

**Output root resolution.** The default is `.deepwiki/<project-name>/` —
hidden, tool-owned, collision-free; add `.deepwiki/` to the project's
.gitignore if it isn't already. A host project may override the staging
root in its CLAUDE.md (the DeepWiki app repo itself routes exports to
`content/<project-name>/`); an explicit project instruction always wins
over this default. Everywhere this document says `.deepwiki/<project-name>/`,
substitute the resolved output root.

**Target platform.** Exports are published into the DeepWiki app, which has
a precise upload/rendering contract (file naming, flat structure, link
format, frontmatter, Mermaid limits). Read
[`references/deepwiki-app-constraints.md`](references/deepwiki-app-constraints.md)
**before Task 4** — violating it breaks sidebar ordering or page navigation
after upload.

## Workflow Overview

Follow these 8 tasks in order:

1. **Codebase Scanning** - Comprehensively scan to understand implementation
2. **Structure Selection** - Determine optimal documentation structure
3. **Section Generation** - Create content based on discovered features
4. **Index Generation** - Generate index.md FIRST
5. **Detail File Generation** - Generate each section as separate file
6. **Validation** - Verify structure and syntax (loop until clean)
7. **Source-Reference Verification** - Ground every file/line reference and code snippet against the codebase (loop until clean)
8. **Publish** - Upload the export to the DeepWiki instance and report a pipeline summary

## Task 1: Codebase Scanning and Feature Discovery

**MANDATORY**: Execute comprehensive scanning before writing documentation.

Read [`references/scanning-commands.md`](references/scanning-commands.md) for complete scanning commands.

**Key discovery areas:**
- Project type and domain identification
- Core architectural patterns (concurrency, communication, distributed systems)
- Key features and capabilities
- Component taxonomy
- Integration and interface analysis
- Data flow and processing pipelines
- Quality attributes assessment
- Visual assets and documentation images
- Project evolution and roadmap
- Dependency tree analysis (package manifests, lock files)

**Recommended first command**: `tree -L 3 -I 'node_modules|.git|vendor|target|build|dist|__pycache__'` for a quick structural overview.

**Nested repositories — scan all related code, even across git boundaries.**
A target directory may contain more than one git repository (a companion
repo, a git submodule, a split-out module, a monorepo package, or a sibling
project cloned alongside the main one). Detect them early:

```bash
find . -name .git -not -path './.git/*' -prune -print 2>/dev/null   # nested repo roots
```

By DEFAULT, treat every nested repository as in scope and scan it as part of
the same system. Only EXCLUDE a nested repo when it is genuinely **unrelated**
to the main codebase — a third-party vendored dependency, a demo of an
external tool, or an unrelated project that merely happens to live in the
tree. Judge relatedness from its remote/name, README, and whether the main
code references it (shared package names, "moved to…" notes, the same product
family). When in doubt, INCLUDE it and state the relationship; do not silently
drop code the user expects documented.

For each in-scope nested repo: count its files in the scanning statistics and
component taxonomy, give it its own Task 2 section(s), and cite its files with
a path prefix that resolves from the scan root you pass to Task 7's verifier
(e.g. `nested-repo/src/foo.py:123`, not a bare `foo.py:123`). Note in the
`index.md` scope exactly which nested repos are covered and which (if any)
were excluded and why.

**Paper detection (optional input).** If the scanned repo is the open-source
release of a paper, the user may stage the paper at the repo root as
`.paper/` — typically a symlink to a paper_reader output directory. Check
for it (resolving symlinks) in either layout:

```bash
find -L .paper -maxdepth 2 -name paper_text.txt 2>/dev/null
```

- `paper_text.txt` — page-delimited raw extraction (`=== PAGE N ===`
  markers). This is the ONLY citable paper source; cite claims as
  "(paper p. N)".
- Secondary context, never the citation target: `<id>_analysis.md` (a prior
  analysis report), `paper_figures_text.txt` (figure OCR), `figures/`,
  `paper.pdf`.
- More than one match means multiple papers — plan one comparison file per
  paper (Task 2).
- Exclude `.paper/` from code-scanning statistics and from the documented
  component taxonomy; it is reference input, not part of the codebase.

When detected, Task 2 MUST plan a paper-vs-implementation section and Task 7
gains a paper-claim grounding pass. The paper may predate the released
code — treat the code as the current truth and the paper as design intent.

**Output**: Feature map and component taxonomy that guides documentation structure.

## Task 2: Documentation Structure Selection

Based on Task 1 findings, dynamically determine the optimal structure:

**Select documentation style:**
- Complex systems: deepwiki format with comprehensive tables and diagrams
- Simpler projects: streamlined format with essential sections only

**Diagramming approach:**
- Mermaid diagrams for architecture flows, component relationships, sequences
- ASCII art for simple hierarchies
- Tables for feature matrices and component mappings

**Plan structure dynamically:**
- Each project will have a DIFFERENT structure based on actual features
- Create section hierarchy that matches codebase organization
- Plan file structure for `.deepwiki/<project-name>/`
- If Task 1 detected a `.paper/` folder: plan a `N-paper-vs-implementation.md`
  section (numbered near the end, before the ADR section). With multiple
  papers, make it an index with numbered children (`N-1-paper-<short-slug>.md`
  per paper). See the "Paper vs. Implementation" template in
  [`references/section-templates.md`](references/section-templates.md).

See [`references/output-examples.md`](references/output-examples.md) for structure examples by project type.

## Task 3: Generate Documentation Sections

Create sections that match discovered features. Read [`references/section-templates.md`](references/section-templates.md) for section types and content guidelines.

**Content balance per section:**
- Text explanations: 50-60% (mix of paragraphs and bullet points)
- Mermaid diagrams: 30-40%
- Code snippets: 10-20% (5-10 snippets per major section, 5-15 lines each)

**Content length requirements:**
- Each markdown file must contain at least 1500 words of substantive content
- Aim for comprehensive coverage: explain concepts thoroughly, include examples, document trade-offs
- Maximum 6000 words per file to maintain focus
- Section lengths are flexible - some sections naturally need more content than others

**For every section, follow this structure:**
1. **Introduction** (1-2 paragraphs): What this is and why it exists
2. **Architecture/Overview** (Mermaid diagram): Structure, flow, or relationships
3. **Key Concepts** (2-4 paragraphs): How it works, design decisions, trade-offs
4. **Implementation Details** (table/text): Use tables for structured info
5. **Code References** (5-10 snippets): Critical patterns and implementations
6. **Source References**: Point to source files with line numbers
7. **Summary** (1-2 paragraphs): Key takeaways and connections to other sections

## Task 4: Generate Index Structure First

**IMPORTANT**: Generate `.deepwiki/<project-name>/index.md` FIRST.

**Determine project name:**
- Extract from directory: `basename $(pwd)`
- Or from package manifest (package.json, pyproject.toml, Cargo.toml)

**Index structure** (the YAML frontmatter is REQUIRED — the DeepWiki upload
API reads `title`/`slug`/`description` from it to name the wiki; re-uploads
with the same `slug` update the wiki in place):
```markdown
---
title: [Project Name] Architecture
slug: [project-name]-architecture
description: [One-line summary shown in the wiki list]
---

# [Project Name] Architecture Documentation

Last indexed: Commit: [commit hash from `git rev-parse --short HEAD`]

---

## Overview

## System Architecture
- Multi-Process Architecture and IPC
- Request Scheduling and Batching
...

## About This Documentation

This architecture documentation was generated through comprehensive analysis of the [Project Name] codebase, covering:

- **[N] source files analyzed** ([X] primary language files, [Y] configuration files)
- **[N] major subsystems documented**
- **[N]+ source files referenced** with specific line numbers
- **All public API functions covered**
- **Complete [feature] architecture explained**

### Key Components Covered

- **Component A**: Brief description
- **Component B**: Brief description
- ...

### Documentation Standards

- All source file references use format: `path/to/file.ext:line-range`
- Mermaid diagrams for architecture and flow visualization
- Code snippets attributed to source files
- Cross-references between related sections
```

Include comprehensive table of contents with all sections from Task 2.

## Task 5: Generate Detailed Documentation Files

After index.md, generate each first-level section as a separate file.

**File organization:**
- Each first-level section becomes a separate markdown file
- Subsections included within parent section file (or split as numbered
  children: `2-1-request-flow.md` under `2-system-architecture.md`)
- Place ALL .md files FLAT in `.deepwiki/<project-name>/` — the upload API
  flattens subdirectory paths (`adr/x.md` → `adr-x.md`), which breaks every
  internal link to them
- Use **un-padded** numbered prefixes: `1-overview.md`,
  `2-system-architecture.md`, `10-deployment.md`. Sorting is numeric, and
  zero-padding leaks into sidebar labels ("01 Overview"). The slug after the
  number must start with a lowercase letter or the file drops out of
  numbered ordering.

**ADR generation:**
- Generate ADRs as a numbered section of their own: an index file
  `N-architecture-decisions.md` plus numbered children `N-1-adr-<slug>.md`,
  `N-2-adr-<slug>.md`, … (where N is the section's position) so they group
  and sort under that section in the sidebar — never in an `adr/` subdirectory
- See ADR template in [`references/section-templates.md`](references/section-templates.md)
- Minimum 3 ADRs for complex projects covering key technology and architecture decisions
- Discover ADR-worthy decisions from code comments, README, and non-obvious architectural patterns

**For each file:**
- Follow content balance guidelines from Task 3
- Internal links must target the flat filename and END in `.md`
  (`[Request Flow](2-1-request-flow.md)`) — that suffix is what makes the
  app navigate between pages; `[[wiki-link]]` syntax is not supported
- Include accurate source file references with line numbers
- Verify all Mermaid diagrams are syntactically correct; prefer `graph LR`
  and split diagrams past ~15 nodes (the app renders them into a 500px-tall
  card — tall `TB` flowcharts scale down small)

Read [`references/format-guidelines.md`](references/format-guidelines.md) for detailed formatting rules.

**Image integration:**
- Create `.deepwiki/<project-name>/img/` directory.
- **Inventory candidates from BOTH sources, then choose — don't default to one.**
  Gather the repo's own images (README diagrams, `assets/`/`docs/` figures, sub-repo
  diagrams) AND, when a `.paper/` folder exists, its figures
  (`.paper/**/figures/` — read `figures_manifest.json` for captions to know which
  figure is the architecture/pipeline one vs. a results plot).
- **Vet every candidate against the CURRENT code for staleness — code is truth
  applies to images too.** An image is outdated when it depicts a superseded
  design: a renamed/replaced component, a removed stage, an old backbone, or
  different hyperparameters than the code now uses. Paper figures especially
  predate the released code and may show the research design rather than the
  release (e.g. a paper architecture figure showing one VLM backbone when the
  code ships another). Compare what the figure/caption asserts to what the code
  does before using it.
- **Pick the most suitable per section, then disclose any staleness.** Choose the
  candidate that best clarifies the section. A current repo asset usually wins on
  accuracy. But if a figure — *even a paper figure that is partly outdated* — is
  clearer or more complete than the Mermaid you would draw, KEEP it: a good
  published figure often beats a hand-drawn diagram. The condition is mandatory:
  whenever you use a figure that does not fully match the current code, you MUST
  state in its caption (or adjacent prose) exactly how it differs from the latest
  code — name the superseded component(s) and cite the current code's `file:line`
  — and link the paper-vs-implementation section. Only fall back to a Mermaid when
  no candidate figure is both clear and faithfully annotatable. Never present an
  outdated figure as current without that divergence note.
- Attribute paper figures ("© the paper, Fig N") — they are copyrighted, unlike
  most repo assets; confirm reuse is acceptable for the wiki's audience.
- Reference with relative paths: `![System Architecture](img/architecture.png)`.
  The upload API flattens every image to `{wiki-slug}/imgs/{basename}` and matches
  refs by **basename only** (path stripped), so give images **descriptive, unique
  basenames** (e.g. `rl-framework.png`, not a generic `diagram.png`); colliding
  basenames get silently renamed and break the ref. Ship every referenced image
  in the same upload batch (limits: ≤5 MB/image, ≤10 MB and ≤50 files total;
  jpg/png/gif/svg/webp).

**Add metadata IMMEDIATELY after each file's H1** (placement matters — the
app styles consecutive `Part of:`/`Generated:`/`Source commit:` paragraphs
directly under the H1 as a muted byline; anywhere else they render as body
text). The H1 line itself doubles as the back-navigation anchor:
```markdown
# [Section Title]

**Part of**: [Architecture Documentation](index.md)
**Generated**: [ISO 8601 timestamp, e.g. 2025-10-15T14:30:00Z]
**Source commit**: [hash]
```

## Task 6: Documentation Validation (Loop Until Valid)

**MANDATORY**: Run validation script and fix all errors before completion.

### Run Validation

```bash
python scripts/validate_docs.py .deepwiki/<project-name>/
```

The script validates:
- **Mermaid syntax**: Node IDs, brackets, arrows, subgraphs
- **Section structure**: Navigation links, metadata, Introduction/Summary sections
- **Word count**: Each markdown file meets min (1500) and max (6000) word limits
- **Internal links**: All `[text](file.md)` references resolve
- **Table format**: Proper markdown table syntax

### Validation Loop

1. Run the validation script
2. Check the JSON output:
   - `"status": "success"` → Documentation complete
   - `"status": "errors_found"` → Fix errors and re-run

3. Fix errors by type:
   | Error Type | Fix |
   |------------|-----|
   | `mermaid_syntax` | Fix diagram syntax at reported line |
   | `missing_section` | Add required section content (Introduction, Summary, metadata) |
   | `word_count` | Adjust file content length to meet min/max word limits |
   | `broken_link` | Fix file path or create missing file |
   | `table_format` | Fix table markdown syntax |
   | `adr_format` | Fix ADR file structure (naming, required sections, status) |
   | `cross_reference` | Link orphaned section files from index.md |

4. Re-run validation after fixes
5. **Repeat until all checks pass**

### Example Output

```json
{
  "status": "errors_found",
  "total_files": 5,
  "total_errors": 2,
  "errors": [
    {
      "file": "02-architecture.md",
      "line": 45,
      "type": "mermaid_syntax",
      "message": "Invalid node ID: spaces not allowed in 'Node One'"
    }
  ]
}
```

After fixing all errors:
```json
{
  "status": "success",
  "total_files": 5,
  "total_errors": 0,
  "errors": []
}
```

## Task 7: Source-Reference Verification (Loop Until Grounded)

**MANDATORY**: Task 6 checks structure and syntax; it cannot tell whether a
`file.py:123` reference or a code snippet is real. Fabricated source
references are the worst failure mode of generated architecture docs —
this gate grounds every one against the scanned codebase before publishing.

### Phase A: Deterministic pass

```bash
python scripts/verify_source_refs.py .deepwiki/<project-name>/ --repo <scanned-repo-root>
```

The script extracts every `` `path/to/file.ext:123` `` / `` `…:123-456` ``
reference outside code fences and errors when the file does not exist in the
repo or the line range runs past the end of the file. Same JSON shape as
Task 6 — fix every error and re-run until `"status": "success"`.

### Phase B: Snippet grounding (model pass)

For each code snippet attributed to a source file, grep one distinctive
line of the snippet in that file (e.g. `grep -nF "<distinctive line>"
<repo>/<path>`) and confirm it matches at the claimed location. For every
mismatch:
- Re-read the actual source and correct the snippet/line numbers, or
- Remove the reference if the claim cannot be grounded — never leave an
  unverified `file:line` in shipped documentation.

### Phase C: Paper-claim grounding (only when `.paper/` exists)

The comparison doc makes claims in two directions; each has its own ground
truth. Code claims are covered by Phases A–B. For every claim attributed to
the PAPER (a design choice, hyperparameter, component, or result "per the
paper"), grep `.paper/**/paper_text.txt` for supporting text and cite the
page from the `=== PAGE N ===` markers as "(paper p. N)". Any paper claim
that cannot be grounded in `paper_text.txt` is removed or explicitly hedged
("not stated in the paper text") — never left as a confident assertion.
Do NOT cite the `_analysis.md` as evidence; it is a derived report.

Re-run Phase A after edits. All phases clean → proceed to Task 8.

## Task 8: Publish to DeepWiki and Report

### Publish (default final action)

The DeepWiki app lists a wiki only when its database records exist — the
upload API writes Postgres + R2 together, so publishing ALWAYS goes through
the API (never directly to storage):

```bash
python3 scripts/deepwiki_cli.py publish .deepwiki/<project-name>/
```

Configuration via environment: `DEEPWIKI_URL` (production URL, or
`http://localhost:3000` for a dev instance), `DEEPWIKI_EMAIL`,
`DEEPWIKI_PASSWORD`. Useful: `publish --dry-run` (list what would upload),
`check` (verify auth only). The CLI also supports `list`, `get <slug>`
(download a wiki's markdown), and `delete <slug> --yes` — all through the
server's API, never direct database/storage access.

- Credentials configured → publish, then report the wiki URL printed by the
  script (`<base-url>/wiki/<slug>`).
- Credentials missing or upload fails (offline/transient) → the export is
  still complete locally; report this step as `SKIPPED`/`FALLBACK` with the
  reason and tell the user to re-run the script later. Do NOT treat the run
  as failed.
- Re-publishing with the same `slug` updates the existing wiki in place;
  unchanged files are versioned as "skipped" by the app.

### Pipeline summary (always)

End the run with a stage-status table so the user can judge confidence:

```
Pipeline summary:
| Task | Status | Notes |
|------|--------|-------|
| 1 Codebase scanning | OK | N files scanned |
| 2 Structure selection | OK | N sections planned |
| 3-5 Generation | OK | N files, N diagrams, N ADRs |
| 6 Validation | OK / RETRIED | 0 errors (RETRIED: N fixed) |
| 7 Source-ref verification | OK / RETRIED | N refs checked, N corrected |
| 8 Publish | OK / FALLBACK / SKIPPED | <wiki URL, or reason + re-run hint> |
```

## Core Principles

### Code is Truth
- Always scan and understand actual code before writing documentation
- Reference existing docs for context, but VERIFY against code
- When docs and code conflict, document what code actually does

### Accuracy First
- All file paths, line numbers, and code references must be accurate
- Never fabricate components or features that don't exist
- Use conservative estimates when exact numbers unavailable

### Explain Decisions
- Document not just "what" exists but "why" decisions were made
- Show trade-offs and alternatives considered
- Identify patterns and design principles

### Content Balance
- Prioritize explanation over code
- Use Mermaid diagrams liberally for architecture and flows
- Code snippets should illustrate, not duplicate codebase

## Quick Reference

### Source File References
- Inline format: `` `path/to/file.py` ``
- With line numbers: `` `path/to/file.py:123-456` ``

### Feature Tables
```
| Feature | Implementation | Key Classes | File Location |
|---------|----------------|-------------|---------------|
| Name    | Description    | `Class`     | `file.py:123` |
```

### Mermaid Diagrams
- Use `graph TB` or `graph LR` for components
- Use `sequenceDiagram` for request flows
- Node IDs: no spaces (use `NodeA`, not `Node A`)
- Labels: use brackets `A[Label Text]`
- See [`references/format-guidelines.md`](references/format-guidelines.md) for complete syntax

### Output Directory
```
.deepwiki/<project-name>/          ← strict output root (gitignored staging area)
├── index.md                     ← REQUIRED; YAML frontmatter names the wiki
├── img/                         ← image assets (uploaded in the same batch)
├── 1-overview.md                ← un-padded numbered prefixes, all .md flat
├── 2-system-architecture.md
├── 2-1-request-flow.md          ← numbered child of section 2
├── ...
├── 9-architecture-decisions.md  ← ADR index (N = last section number)
├── 9-1-adr-<slug>.md            ← flat ADR children — never an adr/ subdir
└── 9-2-adr-<slug>.md
```

## Reference Files

Load these as needed for detailed guidance:

- **Scanning commands**: [`references/scanning-commands.md`](references/scanning-commands.md)
  - Codebase enumeration, architecture scanning, pattern detection
  - Maximum coverage requirements and verification checklist

- **Section templates**: [`references/section-templates.md`](references/section-templates.md)
  - Common section types with descriptions
  - Content guidelines per section type
  - Project Evolution/Roadmap template

- **Format guidelines**: [`references/format-guidelines.md`](references/format-guidelines.md)
  - Mermaid syntax rules (CRITICAL)
  - Code snippet guidelines
  - Image integration strategy

- **Output examples**: [`references/output-examples.md`](references/output-examples.md)
  - Example structures for different project types
  - File naming conventions

- **DeepWiki app constraints**: [`references/deepwiki-app-constraints.md`](references/deepwiki-app-constraints.md)
  - The target platform's upload/rendering contract (MANDATORY before Task 4)
  - File naming/sorting, flat-structure rule, frontmatter, link format
  - Mermaid/image limits, metadata byline placement, publish mechanics

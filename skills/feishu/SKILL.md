---
name: feishu
description: >-
  Feishu (Lark) wiki tools: read pages as markdown, write markdown to new pages,
  optimize document formatting, copy/sync/export wiki pages. Use this skill when
  the user wants to interact with Feishu wiki — read, write, copy, sync, export,
  or optimize/polish wiki pages. Triggers on: feishu, lark, 飞书, wiki page,
  read feishu, write feishu, optimize feishu, copy feishu, sync feishu, export feishu.
---

# Feishu Wiki Tools

Read, write, optimize, copy, sync, and export Feishu wiki pages.

## Skill Files Location

This skill's supporting files are located relative to this SKILL.md:

- `scripts/feishu_tool.py` — Self-contained Python script for read/write/info operations (needs only `.env`)
- `references/optimization-guide.md` — Format comparison framework and known reference patterns
- `references/conservative-edits.md` — Guidelines for light-touch editing

## Prerequisites

- `.env` file with credentials (checked in order):
  1. `.env` in the current directory
  2. `~/.config/feishu_tools/.env`
  ```
  FEISHU_APP_ID=your_app_id
  FEISHU_APP_SECRET=your_app_secret
  ```
- Python packages: `requests`, `python-dotenv`

## Data Locations

- **Token cache**: `~/.config/feishu_tools/token_cache.json`
- **Sync state**: `~/log/feishu_tools/sync_logs/state/`
- **Sync logs**: `~/log/feishu_tools/sync_logs/` (one log per sync run)

Install dependencies on first run:
```bash
pip install requests python-dotenv 2>/dev/null
```

## Arguments

$ARGUMENTS should be: `ACTION [ARGS...]`

Determine the action from the user's intent:

| User intent | Action |
|-------------|--------|
| Read/view/fetch a page | `read SOURCE_URL` |
| Write/create/publish a page | `write PARENT_URL` |
| Optimize/polish a page | `optimize SOURCE_URL DEST_URL` |
| Copy a page | `copy SOURCE_URL TARGET_URL` |
| Sync pages | `sync SOURCE_URL TARGET_URL` |
| Export to local files | `export SOURCE_URL` |

---

## Action: read

Read a Feishu wiki page and display its content as markdown.

```bash
python <skill-directory>/scripts/feishu_tool.py read SOURCE_URL
```

Options:
- `--no-title` — Omit the H1 title from output

The script outputs clean markdown to stdout (logs go to stderr). Display the content to the user. If they ask follow-up questions, answer based on the retrieved text.

### Notes
- On first run, it may prompt for OAuth authorization — follow the printed URL
- Token is cached in `.feishu_token_cache.json` for subsequent runs
- Supports docx-type wiki pages only

---

## Action: write

Create a new Feishu wiki page from markdown content.

1. Prepare the markdown content from the conversation or a file.
2. Write the page using a heredoc:
   ```bash
   python <skill-directory>/scripts/feishu_tool.py write PARENT_URL --title "Page Title" <<'MARKDOWN'
   ## Section 1

   Content here...
   MARKDOWN
   ```
3. The script prints the new page URL to stdout. **Share this URL** with the user.

### Options
- `--heading-color` — Auto-color heading backgrounds by relative depth: outermost → **red/pink**, then orange, yellow, green, blue, purple. Explicit `{bg=N}` on a heading always wins.

### Inline formatting
| Syntax | Result |
|--------|--------|
| `**text**` | Bold |
| `*text*` | Italic |
| `` `code` `` | Inline code |
| `~~text~~` | Strikethrough |
| `[label](url)` | Link |
| `{red:text}` | **Red text** (`text_color=1`) |
| `{red:**text**}` | **Red bold** — key emphasis |

### Notes
- New page is created as a child (sub-node) of the parent.
- If `--title` is omitted, title is extracted from the first H1.
- The `MARKDOWN` delimiter must be quoted (`'MARKDOWN'`) to prevent variable expansion.
- Supported: headings, paragraphs, bold, italic, code, strikethrough, links, bullet/ordered lists, code blocks, blockquotes, dividers, **tables** (`| col | col |` pipe format), callout blocks, quote containers (`|>` prefix), LaTeX equations.
- Images are not yet supported for write-back.

---

## Action: optimize

Light-touch optimization of a Feishu wiki document: fix errors, complete descriptions, and slightly improve formatting — while preserving the original author's tone, style, and intent.

**Core principle**: The original document is the authority. The reference document only guides formatting structure. Never rewrite or restructure aggressively.

**Output**: A new wiki sub-page under the reference document containing the optimized version.

### Arguments

- **SOURCE_URL**: The document to optimize (content source)
- **DEST_URL**: The well-formatted reference document (format guide only; new page created under this)

### Workflow

Follow these 6 tasks in order:

1. **Read Source** — Fetch and understand the source document
2. **Read Reference** — Fetch and analyze the reference document's format
3. **Format Analysis** — Compare structures and identify format gaps
4. **Content Review** — Identify factual errors, incomplete descriptions, minor issues
5. **Generate Optimized Version** — Apply light-touch improvements
6. **Write to Feishu** — Create new sub-page with optimized content

### Task 1: Read Source Document

```bash
python <skill-directory>/scripts/feishu_tool.py read SOURCE_URL
```

Save the full output. This is the document to optimize.

**Analyze carefully:**
- Overall topic and purpose of the document
- Author's writing style and tone (formal/informal, technical/accessible)
- Existing heading structure and hierarchy
- Content organization and flow
- Level of detail in each section
- Use of formatting (bold, lists, code blocks, etc.)

**Record your observations** — you will need them in Task 5 to preserve the original character.

### Task 2: Read Reference Document

```bash
python <skill-directory>/scripts/feishu_tool.py read DEST_URL
```

Save the full output. This is the format reference only — not a content source.

**Analyze the FORMAT only:**
- Heading hierarchy pattern (depth, naming conventions)
- Section organization template
- Formatting conventions (when bold is used, list styles, etc.)
- Content density and paragraph structure
- Use of structural elements (dividers, quotes, code blocks)

### Task 3: Format Analysis

Read [`references/optimization-guide.md`](<skill-directory>/references/optimization-guide.md) for the detailed comparison framework and known reference format patterns.

Check the source document against these specific format conventions:

| Convention | Expected Pattern | Source Status |
|------------|-----------------|---------------|
| Opening callout | `[!callout]` with description + paper/repo links | Present? Missing? |
| Numbered headings | `## 1 标题` / `### 1.1 子标题` | Correct numbering? Duplicates? |
| Heading groups | No section resets — numbering is continuous across whole doc | Multiple `## 1` resets? |
| Level conflicts | Group/chapter titles at correct level vs. their sub-items | Any group title at same level as children? |
| Key concept callouts | `\|>` quote containers for key insights | Used where appropriate? |
| Code block tags | Language tag on every code block | Any bare ` ``` `? |
| Bold key terms | First mention of important technical terms bolded | Applied? |
| Inline emphasis | `{red:...}` for critical constraints; `{red:**...**}` for most important conclusion | Used sparingly? |
| LaTeX equations | `$inline$` and `$$display$$` | Correct syntax? |

**Important**: Only note FORMAT differences. Do not compare content topics.

### Task 4: Content Review (Light Touch)

Review the source document for issues that should be fixed regardless of format:

**Fix These:**
- **Factual errors**: Incorrect technical information, wrong version numbers, broken links
- **Incomplete descriptions**: Sentences that trail off, missing explanations, TODO/placeholder text
- **Obvious typos**: Spelling errors, grammar mistakes that change meaning
- **Broken formatting**: Unclosed markdown, inconsistent list indentation

**Do NOT Change:**
- **Author's tone**: If they write casually, keep it casual
- **Content focus**: If they emphasize certain topics, respect that emphasis
- **Technical opinions**: If they recommend a tool or approach, keep it
- **Original structure**: Only adjust structure if it clearly conflicts with the reference format
- **Level of detail**: If the author was brief on a topic, they may have had a reason

Read [`references/conservative-edits.md`](<skill-directory>/references/conservative-edits.md) for detailed guidelines on what changes are appropriate.

### Task 5: Generate Optimized Version

**CRITICAL**: Read this section carefully before writing.

#### The 80/20 Rule

The optimized document should be **80%+ identical** to the original. Changes should be subtle improvements, not rewrites.

#### What to change:

1. **Opening callout** — Add a `[!callout]` block at the top if missing
   - Use `[!callout icon=ICON bg=2 border=2]` — choose an appropriate icon freely (e.g. `gift`, `bulb`, `bookmark`, `pushpin`, `rocket`, `star`)
   - Put the document's intro description AND paper/code links **all inside** the callout as child paragraphs (separated by blank `>` lines)
   - Example:
     ```
     > [!callout icon=gift bg=2 border=2]
     > 本文档...的简介文字。
     >
     > **Paper**: [Title](url)
     >
     > **Code**: [GitHub](url)
     >
     ```
   - If the source already has an intro `|>` quote container, move its text into the callout children and remove the `|>` block

2. **Heading restructuring** — Fix numbering AND hierarchy when needed:
   - Apply **continuous sequential numbering** across the whole document (`## 1`, `## 2`, `## 3`…), not per-section resets
   - **Heading groups**: If multiple independent sections each restart at "1.", "2."…, choose a fix:
     - *Elevate the group header*: if a heading like `## 深度推导：…` logically contains sub-items also at `##`, promote it to `#` and demote sub-items to `##`
     - *Continuous renumber*: if no clear group header exists, renumber all items sequentially (1, 2, 3, 4…)
   - **Level conflicts**: if a heading that groups several sub-sections is at the same `##` level as those sub-sections, promote it one level up (`##` → `#`, `###` → `##`, etc.)
   - **Renaming allowed**: you MAY revise a heading's title when it's too generic or doesn't capture the actual scope — keep the core topic, just improve precision
   - **Reordering allowed**: you MAY reorder sections when the logical flow clearly improves (e.g., prerequisite concepts before dependent ones) — note each reorder in the summary report

3. **Key concept callouts** — match the source document's existing callout style (`|>` or `>`)
   - Only where the source already emphasizes something but doesn't use callout format
   - Do NOT add callouts around content that wasn't emphasized in the original

4. **Code block language tags** — Add missing language tags to bare code blocks

5. **Formatting conventions** — Apply reference patterns
   - Bold key technical terms on first mention
   - Use `inline code` for function names, variables, file paths

6. **Inline emphasis** — Extract and highlight the most important points per section
   - Preserve ALL existing `{red:...}`, `**bold**`, `*italic*` from the source exactly
   - Add new emphasis sparingly — 1–3 instances per section maximum:
     - `**bold**` — key technical terms, lead-in labels in lists
     - `*italic*` — terms being defined, foreign phrases, titles
     - `{red:text}` — critical constraints, warnings, things the reader must not miss
     - `{red:**text**}` — the single most important conclusion or insight in the document; use at most once or twice total
   - Ask: *would a reader skimming this document immediately understand the core point?* If not, add one emphasis
   - Never bold/red entire sentences — mark only the specific phrase or term

7. **Factual corrections** — Fix identified errors from Task 4

8. **Description completion** — Flesh out incomplete sections
   - Add only information that is clearly implied or factually obvious
   - Do NOT fabricate details or add your own opinions

#### What NOT to change:

- **Author's tone and voice** — Colorful language (e.g., 灵魂拷问, 降维打击, 一句话总结) is intentional. Keep it.
- **Existing emphasis** — If the author used `{red:...}` or bold on something, that was intentional; don't remove or move it
- **Section scope** — Don't merge or split sections; don't change what each section covers
- **Technical examples and code snippets** — Preserve exactly
- **Author's analogies and explanations** — Their way of explaining is part of the value
- **Length** — Don't pad sections to match reference length
- **Author's personal insights or recommendations** — These are the core value of the document

#### Generating the output:

Produce the complete optimized markdown. Do NOT output a diff — output the full document.

### Task 6: Write to Feishu

Determine an appropriate title. Use the source document's original title, optionally with a suffix.

Write the optimized content as a new sub-page under the reference document:

```bash
python <skill-directory>/scripts/feishu_tool.py write DEST_URL --heading-color --title "TITLE" <<'MARKDOWN'
[full optimized markdown content here — NO H1 line]
MARKDOWN
```

**Important notes for writing:**
- Always include `--heading-color` to auto-color headings by depth (required for visual formatting)
- **Do NOT include a `# Title` H1 line in the heredoc body.** The page title is set via `--title`. If H1 is in the body, it shifts heading depth by 1 and all headings get the wrong color (orange instead of red for top-level `##` sections).
- Use a heredoc (`<<'MARKDOWN'`) to avoid shell escaping issues
- The `MARKDOWN` delimiter must be quoted (`'MARKDOWN'` not `MARKDOWN`) to prevent variable expansion
- If the content contains the string `MARKDOWN` on its own line, use a different delimiter (e.g., `<<'FEISHU_EOF'`)

The script prints the URL of the newly created page. **Share this URL with the user.**

#### Post-write verification:

After writing, optionally verify by reading back:
```bash
python <skill-directory>/scripts/feishu_tool.py read NEW_PAGE_URL
```

### Summary Report

After completing all tasks, provide the user with:

1. **URL** of the new page
2. **Changes made** — brief list of what was modified
3. **Confidence level** — how confident you are in the changes

### Reference Files

Load these as needed for detailed guidance:

- **Optimization guide**: [`references/optimization-guide.md`](<skill-directory>/references/optimization-guide.md)
- **Conservative edits**: [`references/conservative-edits.md`](<skill-directory>/references/conservative-edits.md)

---

## Action: copy

Copy wiki pages between locations with full fidelity (text, images, tables, formatting).

```bash
python <skill-directory>/scripts/feishu_tool.py copy SOURCE_URL TARGET_URL [options]
```

Options:
- `-r` — Recursive: copy all subpages
- `-n` — Add auto-numbered headings (1.1, 1.2)
- `--fix-refs` — Fix internal references in copies
- `--title "Title"` — Override page title
- `-v` — Verbose output

The script prints the new page URL to stdout.

---

## Action: sync

Incremental sync — only copies new or modified pages on subsequent runs. State is persisted in `.feishu_sync_state/`.

```bash
python <skill-directory>/scripts/feishu_tool.py sync SOURCE_URL TARGET_URL [options]
```

Options:
- `-n` — Add auto-numbered headings
- `--no-fix-refs` — Skip reference remapping
- `--title "Title"` — Custom root page title
- `-v` — Verbose output

First run performs a full copy. Subsequent runs detect NEW/MODIFIED/DELETED pages and sync incrementally.

---

## Action: export

Export wiki pages and subpages to local markdown files with images.

```bash
python <skill-directory>/scripts/feishu_tool.py export SOURCE_URL [-o DIR]
```

Options:
- `-o DIR` — Output directory (default: `wiki_output`)
- `-v` — Verbose output

Creates a directory tree with `.md` files and `images/` subdirectories.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OAuth prompt on first run | Follow the printed authorization URL, then re-run |
| Token expired | Delete `.feishu_token_cache.json` and re-run |
| "Only docx pages supported" | The page is a sheet/bitable/etc., not a document |
| Permission denied | Add required scopes to your Feishu app: `wiki:wiki`, `docx:document`, `drive:drive` |

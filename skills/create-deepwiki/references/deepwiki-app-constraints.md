# DeepWiki App Constraints (target-platform contract)

Verified against the DeepWiki app source (the Next.js app this skill's
exports are published into). Every rule below is enforced or interpreted by
app code — violating one degrades rendering or breaks navigation. Citations
are to that app's repo.

## File naming and ordering (sidebar)

The sidebar parses filenames with `^(\d+(?:-\d+)*)-([a-z].*)$` and sorts
numerically per dash-separated number part (`components/WikiViewer.tsx`).

- `index.md` always sorts first (REQUIRED by the upload API), `overview.md`
  second if present.
- Use **un-padded** numbered prefixes: `1-overview.md`, `2-architecture.md`,
  `2-1-request-flow.md`, `10-deployment.md`. Sorting is numeric (`2-` before
  `10-`; the app normalizes `01` → `1`), so zero-padding buys nothing —
  stay un-padded so filenames, labels, and links read identically.
- Label derivation: `2-1-request-flow.md` → "2.1 Request Flow". Choose slugs
  that title-case well.
- Start the slug part with a **lowercase letter** (the current app matches
  case-insensitively, but lowercase kebab-case is the convention all links
  and examples assume).

## Flat structure only — subdirectories break links

The upload API flattens paths: `adr/001-foo.md` becomes `adr-001-foo.md`
(`app/api/wiki/upload/route.ts` sanitizeFilename). Any markdown link to the
original subdir path then 404s, and the renamed file escapes numbered
ordering.

- Keep ALL `.md` files at the export root.
- ADRs: give them a numbered section of their own — a parent
  `N-architecture-decisions.md` (the ADR index) with children
  `N-1-adr-<slug>.md`, `N-2-adr-<slug>.md`, … so they group and sort
  under that section.

## index.md frontmatter (names the wiki)

The upload API reads YAML frontmatter from index.md for the wiki's
identity (`route.ts:146-162`); without it, the title falls back to the
first H1 and the slug is auto-derived:

```yaml
---
title: <Project> Architecture
slug: <project>-architecture
description: One-line summary shown in the wiki list.
---
```

Re-uploading with the same `slug` updates the existing wiki in place
(owner/admin only) — unchanged files are versioned as "skipped".

## Internal links

- Links navigate between pages ONLY when the target ends in `.md`:
  `[Request Flow](2-1-request-flow.md)` (`lib/markdown/MarkdownRenderer.tsx:867`).
  Matching is case-insensitive; no leading `./`.
- **Cross-file anchors break navigation**: `2-arch.md#flow` does not end in
  `.md`, is never intercepted by the wiki-link handler, and falls through to
  a raw browser load. Link cross-file targets by FILE ONLY; anchors are for
  same-page jumps.
- Same-page anchors `#heading-id` work; IDs are derived as: strip
  formatting, lowercase, remove non-word chars (ASCII), spaces → `-`.
- `[[wiki-link]]` syntax is NOT supported.
- External `http(s)` links open in a new tab.

## Page metadata byline

Consecutive paragraphs placed **immediately after the H1** that start with
`Part of:`, `Generated:`, `Last indexed:`, or `Source commit:` are styled as
a muted caption byline instead of body text (`MarkdownRenderer.tsx:892-920`).
Bold labels work because the colon sits outside the strong tag:

```markdown
# Request Scheduling

**Part of**: [Architecture Documentation](index.md)
**Generated**: 2026-06-11T10:00:00Z
**Source commit**: abc1234
```

Anywhere else in the file, these lines render as ordinary paragraphs.
Three traps: only the FIRST H1 in the document is processed; the first
paragraph that doesn't match one of those labels ends the styled run; and
anything between the H1 and the byline — a back-link, an `---` rule, even
a stray sentence — kills the styling for everything after it.

## Table of contents

Only `##` (H2) and `###` (H3) appear in the TOC; H1 is the page title and
H4+ are invisible to navigation (`lib/markdown/extractHeadings.ts`). An H3
without a preceding H2 is dropped. Structure pages so every navigable
concept is an H2/H3.

## Mermaid diagrams

Rendered inline into a card capped at **500px height** with click-to-zoom
(`app/globals.css`). Tall diagrams get scaled small inline.

- Prefer `graph LR` for wide component graphs; split a diagram rather than
  letting one grow past ~15 nodes.
- White card background in BOTH themes — don't rely on theme colors inside
  the diagram.
- The app themes every diagram itself with one unified palette
  (`lib/markdown/mermaidTheme.ts`). NEVER hardcode colors: inline
  `classDef`/`style`/`linkStyle` fill/stroke/color directives override the
  app theme and clash with it. Leave diagrams unstyled.
- Node IDs without spaces (`NodeA[Label Text]`); cluster labels wrap at
  800px.

## Images

- Upload images in the SAME batch as the markdown; the API rewrites relative
  references (`![x](img/foo.png)`, `./foo.png`, bare `foo.png`) to R2 URLs by
  basename match (`route.ts:36-117`). External `http(s)` image URLs pass
  through untouched.
- Basename matching is case-insensitive AND extension-blind as a fallback —
  `foo.png` and `foo.svg` collide, and a colliding upload is silently renamed
  (`foo-1.png`), breaking the markdown ref. Basenames must be unique
  **after stripping the extension and lowercasing**.
- Formats: jpg/jpeg/png/gif/svg/webp. Limits: 5 MB per image, 50 files and
  10 MB total per upload.
- Inline display caps at 500px height.
- **Figure captions**: an image immediately followed (no blank line) by an
  emphasis line renders as a centered figure with a muted caption
  (`MarkdownRenderer.tsx`):

  ```markdown
  ![System Architecture](img/architecture.png)
  *Figure 1: High-level system architecture*
  ```

## Markdown dialect

- Rendered with marked + DOMPurify. Raw HTML survives only for an allowlist
  (headings, lists, tables, `details`/`summary`, `img`, `svg`, …); anything
  else is stripped — prefer pure markdown. `<details>`/`<summary>` is the
  one useful HTML escape hatch (collapsible long listings).
- **NOT supported — renders literally**: task lists (`- [ ]`), footnotes
  (`[^1]`), math/LaTeX (`$...$`, `$$...$$` — no KaTeX), definition lists.
  Write formulas as code spans or Unicode (`x ∈ [0, 1]`, `O(n log n)`);
  use plain bullets instead of checkboxes.
- Syntax highlighting: typescript, javascript, jsx, tsx, css, json, bash,
  markdown, yaml, python, sql. Other languages render as plain monospace —
  still fine, just unstyled.

## Publishing

A wiki exists on the site only when the app writes its Postgres records
(Wiki → WikiFile → WikiVersion); R2 holds content blobs. NEVER write to R2
directly — publish through the authenticated upload API via
`scripts/deepwiki_cli.py publish` (see SKILL.md Task 8; the CLI also
supports `list` / `get` / `delete` / `check`, all API-only).

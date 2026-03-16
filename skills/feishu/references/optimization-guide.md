# Format Optimization Guide

## Known Reference Format Pattern

The following conventions were observed across multiple well-formatted reference documents (GLM-5 技术报告解读, YaRN 代码解读, Qwen-3.5 Preview). Use these as the **target format** when optimizing:

### Opening Callout

Every document starts with a callout block (blockquote in markdown) containing:
- A 📌 emoji prefix
- **Paper/resource links**: Paper title linked to arXiv/publication, GitHub repo link
- **Related doc links**: Cross-references to related wiki pages

Example:
```markdown
> 📌 **Paper**: [FlashAttention: Fast and Memory-Efficient Exact Attention](https://arxiv.org/abs/2205.14135)
> **Code**: [GitHub](https://github.com/Dao-AILab/flash-attention)
> **Related**: [FlashAttention-2 解读](link), [Memory-Efficient Attention](link)
```

### Numbered Headings

Sections use explicit numbering in the heading text:
- `## 1 第一节标题` (top-level sections)
- `### 1.1 子节标题` (subsections)
- `### 1.2 另一个子节` (next subsection)
- `## 2 第二节标题` (next top-level)

Numbers are part of the heading text, not auto-generated. Ensure numbering is sequential with no duplicates.

### Callout Blocks for Key Concepts

Important concepts, prerequisites, or highlights use blockquote callouts with emoji markers:
- 📌 for key points and important notes
- 📚 for background knowledge or prerequisites
- Other emoji as appropriate for the context

Example:
```markdown
> 📌 **核心思想**: Tiling + recomputation，用计算换IO，减少HBM访问
```

### Code Blocks with Language Tags

All code blocks specify a language tag: ` ```python `, ` ```cpp `, ` ```bash `, etc. Never use bare ` ``` `.

### LaTeX Equations

Mathematical formulas use LaTeX syntax. Inline: `$O(N^2)$`. Display:
```
$$
S = QK^T \in \mathbb{R}^{N \times N}
$$
```

### Cross-Links

References to other wiki documents use inline markdown links with descriptive text, not raw URLs.

### Section Separators

Major sections are separated by horizontal rules (`---`).

---

## Analysis Framework

When comparing source and reference documents, work through these dimensions systematically.

## 1. Heading Structure

| Check | What to look for |
|-------|-----------------|
| Numbering | Does source use `## 1`, `### 1.1` pattern? Are numbers sequential and continuous? |
| Depth | Does source match reference's hierarchy depth? |
| Duplicates | Any duplicate section numbers (e.g., two `## 5` sections)? |
| Group resets | Does numbering restart in multiple places (first `## 1, 2, 3`, then another `## 1, 2, 3`)? |
| Level conflicts | Is any group/chapter heading at the same level as the sub-items it introduces? |

**When to adjust**: Fix duplicate or reset numbering. Elevate group headers that sit at the wrong level. Add numbers if reference uses them and source doesn't.

**When NOT to adjust**: Don't merge or split sections, don't change what each section covers.

### Heading Group Conflicts

A document has a **heading group conflict** when:
- Multiple sibling headings each restart internal numbering: first `## 1, ## 2, ## 3`, then another `## 1, ## 2, ## 3`
- A "chapter title" heading is at the same markdown level as the sub-sections it introduces

**Fix strategy (choose one):**
1. **Elevate the group header**: if a heading like `## 深度推导：…` logically contains `## 1`, `## 2`, `## 3` sub-items, promote it to `#` and convert sub-items to `##`
2. **Continuous renumber**: if there is no clear group header, renumber all headings sequentially without resets

**Renaming**: when restructuring, you may revise heading titles to accurately reflect the section's actual scope — keep the core topic, improve precision only.

**Reordering**: move sections when a prerequisite concept appears after the concept that depends on it, or when closely related topics are scattered. Note every reorder in the summary report.

## 2. Opening Structure

| Check | What to look for |
|-------|-----------------|
| Opening callout | Does source have a 📌 callout with paper/repo links? |
| Paper links | Are arXiv/publication links present and correct? |
| Related links | Are cross-references to related docs included? |

**When to adjust**: Add opening callout if missing. Fix broken paper links.

**When NOT to adjust**: Don't fabricate links you're not sure about. If the paper doesn't have a GitHub repo, don't add one.

## 3. Text Formatting

| Convention | Reference pattern | Apply to source? |
|-----------|-------------------|-----------------|
| **Bold** for key terms | First mention of important concepts bolded | Yes, if clearly a pattern |
| `inline code` | Used for function names, variables, paths | Match reference usage |
| Callout blocks (`\|>`) | Quote containers for key insights | Add where appropriate |
| `{red:text}` | Critical constraints / must-not-miss warnings | Add very sparingly |
| `{red:**text**}` | Single most important conclusion in document | At most 1–2 total |
| `*italic*` | Terms being defined, foreign phrases | Match reference usage |

**When to adjust**: Bold key technical terms on first use. Use code formatting for identifiers. Add `{red:...}` only for genuinely critical information a skimming reader must not miss.

**When NOT to adjust**: Don't add bold/italic that changes emphasis the author didn't intend. Never bold entire sentences. Preserve all existing emphasis exactly.

## 4. List Conventions

| Check | What to look for |
|-------|-----------------|
| Bullet vs ordered | Reference uses ordered for sequential steps |
| List item format | Short phrases with bold lead-in terms |

**When to adjust**: Convert sequential steps from bullets to ordered lists.

**When NOT to adjust**: If the source's list style is internally consistent and appropriate.

### Sequential Step Patterns ("第x步" / "Step N")

When source uses bold-paragraph headers for sequential steps (e.g., `**第一步：...**` followed by prose), choose format based on content length:

- **Short items** (≤1 sentence per step) → convert to numbered list: `1. **第一步**：...`
- **Long prose or equations per step** → keep as bold-paragraph headers; nesting multi-paragraph content under list items is awkward in Feishu
- **Never use bullet lists** for sequential steps — order matters

## 5. Code Blocks

| Check | What to look for |
|-------|-----------------|
| Language tags | Reference always uses language tags |
| Annotations | Reference adds comments explaining key lines |

**When to adjust**: Add missing language tags. Never leave bare ` ``` `.

**When NOT to adjust**: Don't modify actual code content.

## 6. Content Density

**When to adjust**: Complete obviously unfinished sentences. Add a brief intro to sections that jump straight into details.

**When NOT to adjust**: Don't pad short sections. Brevity may be intentional.

## 7. Structural Elements

| Element | Reference pattern |
|---------|------------------|
| Blockquotes (`>`) | 📌/📚 callouts for key points and prerequisites |
| LaTeX equations | Display math with `$$`, inline with `$` |

---

## Analysis Output Template

After comparing, produce a table like this (for your own reference, not for the user):

```
FORMAT GAPS IDENTIFIED:
1. [opening] Source missing 📌 opening callout with paper/repo links
2. [numbering] Source has duplicate ## 5 sections
3. [code] Source has code blocks without language tags
4. [callouts] Source missing 📌 callout blocks for key concepts

CONTENT ISSUES FOUND:
1. [factual] Section X cites wrong complexity
2. [incomplete] Section Y trails off mid-sentence
3. [numbering] Two sections both labeled "## 5"

CHANGES I WILL NOT MAKE:
1. Source's engaging tone (灵魂拷问, 降维打击, etc.) — author's voice
2. Technical examples and code — correct as-is
3. Section order — narrative flow is logical
4. Author's analogies and explanations — preserve original insights
```

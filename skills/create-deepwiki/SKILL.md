---
name: create-deepwiki
description: Generate comprehensive deepwiki-style architecture documentation with deep codebase analysis, Architecture Decision Records (ADRs), Mermaid diagrams, and structured multi-file output. Use when users want to create architecture documentation, generate a wiki for a codebase, document a project's structure, or need comprehensive technical documentation.
license: Complete terms in LICENSE.txt
---

# DeepWiki-Style Architecture Documentation Generator

Generate comprehensive, structured architecture documentation with deep codebase analysis.

**Best for**: Complex codebases requiring detailed analysis - frameworks, libraries, services, platforms, tooling, and systems.

**Output**: Multi-file documentation to `docs/<project-name>/` including:
- Structured markdown documentation files
- Architecture Decision Records (ADRs) in `docs/adr/`
- Mermaid diagrams for architecture visualization
- Image assets in `docs/<project-name>/img/`

## Workflow Overview

Follow these 6 tasks in order:

1. **Codebase Scanning** - Comprehensively scan to understand implementation
2. **Structure Selection** - Determine optimal documentation structure
3. **Section Generation** - Create content based on discovered features
4. **Index Generation** - Generate index.md FIRST
5. **Detail File Generation** - Generate each section as separate file
6. **Validation** - Verify quality and accuracy

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
- Plan file structure for `docs/<project-name>/`

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

**IMPORTANT**: Generate `docs/<project-name>/index.md` FIRST.

**Determine project name:**
- Extract from directory: `basename $(pwd)`
- Or from package manifest (package.json, pyproject.toml, Cargo.toml)

**Index structure:**
```markdown
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
- Subsections included within parent section file
- Place all files in `docs/<project-name>/`
- Use numbered prefixes for clear ordering: `01-overview.md`, `02-system-architecture.md`

**ADR generation:**
- Generate Architecture Decision Records in `docs/<project-name>/adr/`
- See ADR template in [`references/section-templates.md`](references/section-templates.md)
- Minimum 3 ADRs for complex projects covering key technology and architecture decisions
- Discover ADR-worthy decisions from code comments, README, and non-obvious architectural patterns

**For each file:**
- Add navigation: `[<-Back to Index](index.md)` at top
- Follow content balance guidelines from Task 3
- Include accurate source file references with line numbers
- Verify all Mermaid diagrams are syntactically correct

Read [`references/format-guidelines.md`](references/format-guidelines.md) for detailed formatting rules.

**Image integration:**
- Create `docs/<project-name>/img/` directory
- Copy relevant architecture diagrams from project
- Reference with relative paths: `![System Architecture](img/architecture.png)`

**Add metadata to each file:**
```markdown
**Part of**: [Architecture Documentation](index.md)
**Generated**: [ISO 8601 timestamp, e.g. 2025-10-15T14:30:00Z]
**Source commit**: [hash]
```

## Task 6: Documentation Validation (Loop Until Valid)

**MANDATORY**: Run validation script and fix all errors before completion.

### Run Validation

```bash
python scripts/validate_docs.py docs/<project-name>/
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
docs/<project-name>/
├── index.md
├── img/
├── 01-overview.md
├── 02-system-architecture.md
├── 03-...
└── ...
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

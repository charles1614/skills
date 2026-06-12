# Section Templates

## Section Creation Guidelines

1. **Don't force fit**: Only create sections for features that actually exist
2. **Group logically**: Combine related topics into parent/child sections
3. **Match project style**: Adapt to project type (library vs service vs CLI)
4. **Use consistent naming**: Follow similar project conventions
5. **Create hierarchy**: Use parent sections with subsections
6. **Consider audience**: Balance technical depth with readability
7. **Include context**: Always explain "why" decisions were made

## Common Section Types

### Overview Section (Always Include)

- "What is [Project]?" section explaining purpose
- Primary use cases and target users
- Key stakeholders and user personas
- Supported models/frameworks/platforms (table format)
- Key metrics or capabilities
- High-level architecture diagram

### Installation and Setup

Include when installation is non-trivial:
- Installation methods (pip, docker, source)
- Dependencies and requirements
- Environment setup steps
- Reference installation scripts

### Core Architecture / System Architecture

- **Mermaid diagram**: High-level showing main layers and relationships
- **Text explanation**: 1-2 paragraphs on architectural style and rationale
- **Bullet points**: Key principles, patterns, responsibilities, communication
- **Components table**: Component | File Location | Key Methods | Responsibility
- Multi-process/thread architecture (if applicable)
- Inter-process communication patterns
- Message formats and data classes (4-10 code examples)

### Configuration System

Include when complex configuration exists:
- Configuration parameters and structure
- Parameter validation and defaults
- Configuration file formats
- Reference config classes

### Request Processing / Pipeline

- **Mermaid sequence diagram**: End-to-end request flow
- **Text explanation**: How requests are processed, key decision points
- **Pipeline stages table**: Stage | Input → Output | File | Method
- Batching strategies with trade-offs
- Scheduling policies comparison
- State transitions (Mermaid state diagram if complex)
- 4-10 code snippets covering parsing, batching, scheduling, error handling

### Memory Management / Caching

- Memory hierarchy (GPU/CPU/Storage tiers)
- Cache implementations table: Type | Implementation | Storage | Eviction Policy
- Memory pools and allocation strategies
- Cache warming and prefetching

### Distributed Execution / Parallelism

- Parallelism strategies table: Type | Parameter | Implementation | Communication
- Communication patterns (NCCL, MPI, collectives)
- Distributed coordination and synchronization
- Load balancing across workers

### Programming Interfaces

- Python API with example usage
- HTTP/REST API endpoints and formats
- Command-line interface
- OpenAI API compatibility (if applicable)

### Testing Infrastructure

- Test framework and organization
- Test types (unit, integration, performance)
- Test execution commands
- Coverage and CI/CD

### Security Architecture

Include when security is a significant concern:
- Authentication and authorization mechanisms
- Data encryption (at rest, in transit)
- Input validation and sanitization
- Secret management
- Security headers and CORS policies
- Audit logging
- Vulnerability management and dependency scanning

### Data Model and Schema Design

Include when the project has non-trivial data structures:
- Entity relationship diagram (Mermaid ER diagram)
- Core data models and their relationships
- Database schema and migration strategy
- Data validation rules and constraints
- Serialization/deserialization patterns
- Data access patterns and query optimization

### Error Handling and Resilience

Include when the project has explicit error handling patterns:
- Error classification and hierarchy
- Retry policies and backoff strategies
- Circuit breaker patterns
- Graceful degradation strategies
- Error reporting and alerting
- Recovery procedures

### Deployment and Operations

- Container deployment (Docker, Kubernetes)
- Server configuration
- Monitoring and observability
- Health checks and metrics

### Build System

- Build configuration
- Dependency management
- Platform-specific builds
- Installation packaging

### Architecture Decision Records (ADRs)

**Always generate ADRs** as flat numbered children of a dedicated section:
an index `N-architecture-decisions.md` plus `N-M-adr-<slug>.md` per ADR —
never in an `adr/` subdirectory (the DeepWiki upload API flattens
subdirectory paths, breaking links and ordering).

**ADR format** (byline directly after the H1, then a blank line before Status):
```markdown
# ADR-NNNN: [Decision Title]

**Part of**: [Architecture Documentation](index.md)
**Generated**: [timestamp]
**Source commit**: [hash]

**Status**: Proposed | Accepted | Deprecated | Superseded
**Date**: YYYY-MM-DD

## Context
What problem are we solving? What constraints exist?

## Decision
What did we decide to do?

## Consequences
What are the trade-offs? What are the benefits and drawbacks?

## Alternatives Considered
What other options were evaluated?
```

**File naming**: `N-M-adr-<slug>.md` (e.g., `9-1-adr-use-postgres.md`, where 9 is the ADR section's number)

**What to document as ADRs**:
- Technology choices (database, framework, language)
- Architectural patterns (microservices vs monolith, event-driven)
- API design decisions (REST vs GraphQL, versioning strategy)
- Security decisions (authentication method, encryption)
- Performance trade-offs (caching strategy, scaling approach)

**Discovery**: Find ADR-worthy decisions by:
- Searching for comments: `grep -r "TODO\|FIXME\|NOTE\|design\|decision" --include="*.py"`
- Reading README and existing docs for rationale
- Identifying non-obvious architectural patterns in code

### Paper vs. Implementation (only when `.paper/` exists)

When the repo is the open-source release of a paper (detected via the
`.paper/` folder, see SKILL.md Task 1), generate `N-paper-vs-implementation.md`
analyzing how the released code diverges from the paper.

**Stance — code is current truth, paper is design intent.** The paper
usually predates the released code. Frame differences as evolution
(renames, post-paper features, changed hyperparameters, dropped
prototypes), never as errors in either artifact. Where they disagree about
current behavior, the code wins; where the code is silent about intent, the
paper explains why.

**Grounding rules (enforced in Task 7 Phase C):**
- Paper claims cite `paper_text.txt` pages: "(paper p. N)" from the
  `=== PAGE N ===` markers. Grep before writing; unverifiable paper claims
  are removed or hedged.
- Code claims cite `file:line` like every other section (Task 7 Phase A/B).
- The prior `_analysis.md` and `paper_figures_text.txt` may guide where to
  look, but are never cited as evidence.

**Required structure:**
```markdown
# Paper vs. Implementation

**Part of**: [Architecture Documentation](index.md)
**Generated**: [timestamp]
**Source commit**: [hash]

## Introduction
Identify the paper (exact title and date from page 1 of paper_text.txt),
the relationship between paper and repo, and the comparison's scope.

## Alignment Overview
| Paper concept (paper p. N) | Code location | Status |
|---|---|---|
| ... | `path/file.py:123` | matches / renamed / changed / absent in code / post-paper addition |

## Key Divergences
2-4 deep-dive subsections (###) on the most significant differences:
what the paper specifies (with page cites), what the code does (with
file:line), and the likely engineering rationale (hedged when inferred).

## In the Paper Only
Components/experiments described but not in the released code.

## In the Code Only
Features the paper never mentions (post-paper additions, infra, tooling).

## Summary
What a reader of the paper must know before reading this codebase.
```

**Figures**: optional — copy a paper figure from `.paper/**/figures/` into
`img/` only when it materially clarifies a divergence AND fits the upload
budget (5 MB per image, 10 MB total per upload).

**Multiple papers**: make `N-paper-vs-implementation.md` an index and write
one `N-M-paper-<short-slug>.md` child per paper, each following this
template.

## Domain-Specific Sections

### For ML/AI Systems

- Model execution and inference
- Training pipelines
- Model versioning and registry
- Feature engineering
- Quantization and optimization
- Hardware acceleration (GPU/TPU/NPU)

### For Web Applications

- Frontend architecture
- Backend services
- Database design
- Session management
- Asset pipeline

### For Data Processing

- ETL pipelines
- Data validation and quality
- Stream processing
- Batch processing
- Data warehousing

### For Infrastructure/Platform

- Resource provisioning
- Orchestration and scheduling
- Service mesh
- Network architecture
- Storage systems

## Project Evolution and Roadmap (Always Include)

Generate from all available sources. If no formal files exist, extract from:
- Commit history and git tags
- Code comments and TODO/FIXME notes
- Version files and package manifests
- Architectural changes in the codebase

**Evidence rule — never invent history.** Every milestone, version row,
deprecation, and issue reference must trace to a real source: a git tag, a
dated commit, a CHANGELOG/ROADMAP entry, or a code comment. Cite issue/PR
numbers only when they appear verbatim in those sources. When git history is
thin (a squashed release dump, a fresh import), shrink this section to what
the evidence supports — drop the subsections you cannot ground, and if the
remainder cannot reach the word-count floor without padding, merge it into
the Overview section instead (see the merge-don't-pad rule in SKILL.md
Task 3). The template below shows the *maximum* shape, not a quota.

### Template

The metadata byline sits immediately after the H1 — nothing (not even a
back-link) between them, or the app renders it as body text:

```markdown
# Project Evolution and Roadmap

**Part of**: [Architecture Documentation](index.md)
**Generated**: [date]
**Source commit**: [hash]

---

## Historical Development

### Version Timeline

| Version | Date | Key Features | Notes |
|---------|------|--------------|-------|
| v3.0.0 | Oct 2025 | Major feature | Notes |
| v2.0.0 | Jun 2025 | Breaking change | Notes |
| v1.0.0 | Jan 2025 | Initial release | Notes |

### Major Milestones

- **Q1 2025**: Project inception
- **Q2 2025**: Added distributed support
- **Q3 2025**: Introduced caching
- **Q4 2025**: Production-ready

### Deprecated Features

- **Old API** (removed in v2.0): Replaced with new API
- **Legacy mode** (deprecated): New mode preferred

## Current State

### Recent Major Changes (Last 3 Months)

- Introduced new feature
- Added optimization
- Refactored component
- Migrated to new backend

### Experimental Features

- **Feature A**: In beta, may change
- **Feature B**: Experimental support
- **Feature C**: Under active development

### Known Issues

From code analysis (TODO/FIXME comments) — cite the comment's `file:line`,
and an issue number only if the comment names one:
- Performance bottleneck in X (`path/file.py:123`)
- Memory leak in Y (being investigated, `path/other.py:45`)
- Incompatibility with Z (workaround in place)

## Future Direction

### Planned Features

From ROADMAP.md and GitHub milestones (omit this subsection entirely when no
such sources exist). Use plain bullets — the app does not render `- [ ]`
task-list syntax:

**Q4 2025** (In Progress):
- Feature improvement
- New capability
- Optimization

**Q1 2026** (Planned):
- Major feature
- Platform support
- Deployment option

### Areas for Improvement

1. **Component refactoring**: Current design has limits
2. **Memory management**: Better pressure handling needed
3. **Observability**: Improve metrics and tracing

## Technical Debt

### High Priority

- Refactor legacy code (marked for removal)
- Replace temporary workaround
- Optimize hot path

### Medium Priority

- Consolidate duplicate code
- Improve error handling
- Update deprecated dependencies

### Low Priority

- Code cleanup
- Test coverage improvement
- Logging standardization

## Summary

This section documents the project's evolution from inception to current state, highlighting major milestones, deprecated features, and planned improvements. Understanding this trajectory helps developers:
- Anticipate future changes and plan accordingly
- Understand why certain design decisions were made
- Identify areas needing attention or refactoring
```

## Content Guidelines Per Section

### Text Formatting

- **Start with narrative**: 1-2 paragraphs for context
- **Use bullet points for**:
  - Feature lists
  - Design decisions
  - Key points
  - Quick references
  - Comparison items
- **Alternate formats**: Paragraph → Bullets → Paragraph → Bullets

### Content Balance

Per major section (counts, not percentages — prose carries the explanation):

| Content Type | Target | Purpose |
|--------------|--------|---------|
| Text (paragraphs + bullets) | The majority of every section's words | Explain concepts and decisions |
| Mermaid diagrams | 1-3 per file, ≤~15 nodes each | Show architecture and flows |
| Code snippets | 4-10 per file, 5-15 lines each | Illustrate key implementations |
| Tables | Where structure helps (components, comparisons) | Map features to `file:line` |

### Code Snippets Strategy

- Include 4-10 snippets per major section
- Keep snippets to 5-15 lines
- Cover different aspects and patterns:
  - Main pattern implementation
  - Alternative approaches
  - Error handling
  - Configuration examples
  - Integration points
- Always attribute with the `From: path:N-M` header line (grammar in
  [`format-guidelines.md`](format-guidelines.md)) — Task 7 verifies these
  mechanically
- Quote the source **verbatim** — never add or edit comments inside an
  attributed snippet; explanation belongs in the surrounding prose

### What to Avoid

- Dumping large code blocks without explanation
- Filling sections with excessive code
- Code snippets longer than 20 lines
- Duplicating codebase content without adding value

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
- Message formats and data classes (5-10 code examples)

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
- 5-10 code snippets covering parsing, batching, scheduling, error handling

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

**Always generate ADRs** in `docs/<project-name>/adr/` directory.

**ADR format**:
```markdown
# ADR-NNNN: [Decision Title]

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

**File naming**: `NNNN-decision-title.md` (e.g., `0001-use-postgres.md`)

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

### Template

```markdown
# Project Evolution and Roadmap

[<-Back to Index](index.md)

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

From code analysis (TODO/FIXME comments):
- Performance bottleneck in X (Issue #234)
- Memory leak in Y (being investigated)
- Incompatibility with Z (workaround in place)

## Future Direction

### Planned Features

From ROADMAP.md and GitHub milestones:

**Q4 2025** (In Progress):
- [ ] Feature improvement
- [ ] New capability
- [ ] Optimization

**Q1 2026** (Planned):
- [ ] Major feature
- [ ] Platform support
- [ ] Deployment option

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

| Content Type | Percentage | Purpose |
|--------------|------------|---------|
| Text (paragraphs + bullets) | 50-60% | Explain concepts and decisions |
| Mermaid diagrams | 30-40% | Show architecture and flows |
| Code snippets | 10-20% | Illustrate key implementations |

### Code Snippets Strategy

- Include 5-10 snippets per major section
- Keep snippets to 5-15 lines
- Cover different aspects and patterns:
  - Main pattern implementation
  - Alternative approaches
  - Error handling
  - Configuration examples
  - Integration points
- Always attribute with file path and function/class name
- Add explanatory comments for complex logic

### What to Avoid

- Dumping large code blocks without explanation
- Filling sections with excessive code
- Code snippets longer than 20 lines
- Duplicating codebase content without adding value

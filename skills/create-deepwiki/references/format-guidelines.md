# Format Guidelines

## Source File References

### Inline Format
- Use inline code: `` `path/to/file.py` ``
- With line numbers: `` `path/to/file.py:123-456` ``
- Multiple references: `` `file1.py`, `file2.py`, `file3.py` ``

## Feature Tables

```markdown
| Feature/Component | Implementation | Key Classes/Functions | File Location |
|-------------------|----------------|----------------------|---------------|
| Name | Description | `ClassName`, `function_name` | `path/to/file.py:123-456` |
```

## Mermaid Diagrams

### Diagram Types

| Type | Syntax | Use For |
|------|--------|---------|
| Component relationships | `graph TB` or `graph LR` | Architecture, dependencies |
| Request flows | `sequenceDiagram` | Interactions, API calls |
| Decision trees | `flowchart` | Logic flows, pipelines |
| State machines | `stateDiagram-v2` | State transitions |

Keep diagrams focused: max 15-20 nodes.

### Grammar and Syntax Rules (CRITICAL)

1. **Node IDs**: Alphanumeric without spaces
   - ✅ `NodeA`, `Node1`, `Init_Probe`
   - ❌ `Node One`, `My Node`

2. **Labels**: Use square brackets
   - `A[Label Text]`
   - `A["Text with: special, chars"]` (quote special chars)

3. **Arrows**:
   - Solid: `-->` or `-->|label text|`
   - Dotted: `-.->` or `-.->|label text|`
   - Thick: `==>` or `==>|label text|`

4. **Subgraphs**:
   ```
   subgraph SubgraphName [Display Title]
       direction TB
       Node1 --> Node2
   end
   ```

5. **Comments**: Use `%%` for comments

6. **Styling**:
   ```
   classDef className fill:#color,stroke:#color
   A:::className
   ```

### Common Pitfalls

| Wrong | Correct | Issue |
|-------|---------|-------|
| `Node One` | `NodeOne` | Spaces in ID |
| `A[Label` | `A[Label]` | Missing bracket |
| `end` as ID | `EndNode` | Reserved keyword |
| `()` in ID | `A[Text ()]` | Parens only in labels |

### Basic Example

```mermaid
graph TB
    A[Client Request] --> B[HTTP Server]
    B --> C[Request Parser]
    C --> D[Scheduler]
    D --> E[Model Worker]
    E --> F[Response]
```

### Advanced Example with Styling

```mermaid
graph TB
    %% Style Definitions
    classDef input fill:#e1f5ff,stroke:#0288d1
    classDef process fill:#fff9c4,stroke:#f57f17
    classDef output fill:#c8e6c9,stroke:#388e3c

    Input(User Request):::input
    Input --> Gateway[API Gateway]:::process

    subgraph Processing [Request Processing]
        direction TB
        Gateway --> Auth[Authentication]:::process
        Auth --> Valid[Validation]:::process
        Valid --> Process[Process]:::process
    end

    Process --> Output(Response):::output
```

### Sequence Diagram Example

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Cache
    participant DB

    Client->>API: Request
    API->>Cache: Check Cache
    alt Cache Hit
        Cache-->>API: Return Data
    else Cache Miss
        API->>DB: Query
        DB-->>API: Result
        API->>Cache: Update Cache
    end
    API-->>Client: Response
```

## Code Snippets

### Guidelines

- **5-10 snippets per major section**
- **5-15 lines each** (max 20)
- **Always attribute** with file path and function name

### Example Format

```python
# From: path/to/scheduler.py:123-135
class Scheduler:
    def get_next_batch(self):
        # Select requests for next batch using configured policy
        return self.policy.select(self.queue)
```

### Cover Different Scenarios

1. Main pattern implementation
2. Alternative approaches
3. Error handling
4. Configuration examples
5. Integration points

### What to Avoid

- Large code blocks without explanation
- Code snippets > 20 lines
- Dumping entire files or classes
- Code without context

## Cross-References

- Link to sections: `[Section Name](filename.md)`
- Link to subsections: `[Subsection](filename.md#anchor)`
- Use descriptive text, not "click here"

## Metadata and Attribution

Each file should start with:

```markdown
# Section Title

**Part of**: [Architecture Documentation](index.md)
**Generated**: [timestamp]
**Source commit**: [hash]

---
```

## Image Integration

### Directory Structure

```
docs/<project-name>/
├── img/
│   ├── architecture-diagram.png
│   ├── request-flow.svg
│   └── component-chart.png
├── index.md
└── ...
```

### Copying Images from Project

```bash
mkdir -p "docs/<project-name>/img"

# Copy architecture diagrams
find . -type f \( -iname "*architecture*.png" -o -iname "*diagram*.png" \) \
  | grep -v "node_modules\|\.git" \
  | xargs -I {} cp {} "docs/<project-name>/img/"
```

### Reference Format

```markdown
![System Architecture](img/architecture-diagram.png)
*Figure 1: High-level system architecture*
```

### Best Practices

| Practice | Reason |
|----------|--------|
| Prefer local copies | Ensures availability |
| Use web links for large files | Reduces repo size |
| Add descriptive alt text | Accessibility |
| Use SVG for diagrams | Scalable, smaller |
| Name with prefixes | `arch-overview.png`, `flow-request.svg` |

### Integration Guidelines

1. Review discovered images from scanning
2. Identify architecture-relevant images
3. Copy local or use web links
4. Reference in appropriate sections
5. Add descriptive captions

### Example Integration

```markdown
## System Architecture

The system follows a multi-tier architecture.

![Existing Architecture Diagram](img/system-architecture.png)
*Figure 1: High-level system architecture (from project documentation)*

```mermaid
graph TB
    A[Client] --> B[API Gateway]
    B --> C[Service Layer]
    C --> D[Data Layer]
```
*Figure 2: Detailed component interaction flow*
```

## Academic Honesty

- Never fabricate components or features
- Always verify code claims by reading source files
- When docs and code conflict, document the CODE
- Use conservative estimates when exact numbers unavailable

## Enforcement

- Each major section must analyze 5-10 actual source files
- Include specific function names, class names, implementation details
- Provide concrete examples from codebase
- Include line number references for specific code claims

#!/usr/bin/env python3
"""
Validation script for DeepWiki documentation.
Checks Mermaid syntax, section structure, links, and table format.

Usage: python3 validate_docs.py <export-dir>   (e.g. .deepwiki/<project-name>/)
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


# Word count limits for document validation (per markdown file)
MIN_DESCRIPTION_WORDS = 1500  # Minimum words for comprehensive documentation
MAX_DESCRIPTION_WORDS = 6000

# Upload budget — keep in sync with deepwiki_cli.py and the app's
# WikiUpload.tsx (the API itself does not enforce these; the client/CLI do).
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB per image
MAX_TOTAL_BYTES = 10 * 1024 * 1024  # 10 MB per upload batch
MAX_FILES = 50                      # files per upload batch (md + images)


def extract_content_outside_code_blocks(content: str) -> Tuple[str, List[Tuple[int, int]]]:
    """
    Extract content outside of code blocks and return line mapping.
    Returns the filtered content and list of (original_line, filtered_line) tuples.
    """
    lines = content.split('\n')
    filtered_lines = []
    line_mapping = []  # Maps filtered line index to original line number
    in_code_block = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block
            filtered_lines.append('')  # Keep line for counting but empty
            line_mapping.append(i + 1)
        elif not in_code_block:
            filtered_lines.append(line)
            line_mapping.append(i + 1)
        else:
            filtered_lines.append('')  # Keep line for counting but empty
            line_mapping.append(i + 1)

    return '\n'.join(filtered_lines), line_mapping


def strip_markdown_formatting(text: str) -> str:
    """Mirror the app's stripMarkdownFormatting (lib/markdown/extractHeadings.ts)."""
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)  # images -> alt text
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)   # links -> link text
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)        # bold
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)           # italic
    text = re.sub(r'`([^`]*)`', r'\1', text)               # inline code
    text = re.sub(r'<[^>]+>', '', text)                    # html tags
    return text


def extract_heading_ids(content: str) -> set:
    """Compute heading anchor IDs the way the DeepWiki app renderer does:
    strip formatting, lowercase, drop non-word chars (ASCII \\w, matching
    JS), collapse whitespace to hyphens. Headings inside code fences are
    not rendered as headings and are excluded."""
    filtered_content, _ = extract_content_outside_code_blocks(content)
    ids = set()
    for line in filtered_content.split('\n'):
        m = re.match(r'^#{1,6}\s+(.+)$', line)
        if m:
            heading = strip_markdown_formatting(m.group(1)).strip().lower()
            heading = re.sub(r'[^\w\s-]', '', heading, flags=re.ASCII)
            ids.add(re.sub(r'\s+', '-', heading.strip()))
    return ids


def validate_mermaid_block(content: str, start_line: int) -> List[Dict[str, Any]]:
    """Validate a Mermaid diagram block for syntax errors."""
    errors = []
    lines = content.split('\n')

    # Keywords that ARE valid at start of line (not node IDs)
    valid_keywords = {'subgraph', 'direction', 'end', 'style', 'classDef', 'class', 'graph', 'flowchart', 'sequenceDiagram', 'stateDiagram', 'participant', 'actor', 'note', 'alt', 'else', 'opt', 'loop', 'par', 'and', 'rect', 'activate', 'deactivate'}

    # Track bracket balance
    brackets = {'[': 0, '(': 0, '{': 0}
    bracket_pairs = {'[': ']', '(': ')', '{': '}'}

    for i, line in enumerate(lines):
        line_num = start_line + i
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith('%%'):
            continue

        # Hardcoded colors override the DeepWiki app's unified Mermaid theme
        # (lib/markdown/mermaidTheme.ts in the app) and clash with it.
        # stroke-width/-dasharray don't match: the colon must follow directly.
        if re.match(r'(?i)(classDef|style|linkStyle)\b', stripped) and \
                re.search(r'(?i)\b(?:fill|stroke|color)\s*:', stripped):
            errors.append({
                'line': line_num,
                'type': 'mermaid_hardcoded_style',
                'message': "Hardcoded diagram color (fill/stroke/color directive) — the DeepWiki app applies its own Mermaid theme; leave diagrams unstyled"
            })
            continue

        # Skip lines starting with valid keywords
        first_word = stripped.split()[0] if stripped.split() else ''
        if first_word.lower() in valid_keywords or first_word.rstrip(':').lower() in valid_keywords:
            continue

        # Check for spaces in node IDs (before brackets or arrows)
        # Pattern: word with space before [ or ( or { or -->
        # But exclude lines that start with valid keywords
        node_pattern = r'^(\s*)([A-Za-z_][A-Za-z0-9_\s]*?)(?:\[|\(|\{|-->|-.->|==>)'
        match = re.match(node_pattern, line)
        if match:
            node_id = match.group(2).strip()
            # Skip if it's a keyword or keyword combination
            if node_id.lower() not in valid_keywords and ' ' in node_id:
                # Check it's not a subgraph definition
                if not stripped.lower().startswith('subgraph'):
                    errors.append({
                        'line': line_num,
                        'type': 'mermaid_syntax',
                        'message': f"Invalid node ID: spaces not allowed in '{node_id}'"
                    })

        # Check bracket balance (only for non-comment, non-keyword lines)
        for char in line:
            if char in brackets:
                brackets[char] += 1
            elif char in bracket_pairs.values():
                for open_b, close_b in bracket_pairs.items():
                    if char == close_b:
                        brackets[open_b] -= 1

        # Check for invalid arrow syntax
        if '--' in line or '-.' in line or '==' in line:
            # Valid arrows: -->, -.->. ==>, also -->|text| etc
            # Skip sequence diagram arrows (->> etc)
            if not any(x in line for x in ['->>','-->>','-x','--x']):
                invalid_arrows = re.findall(r'(?<!-)--(?!>)(?!-)|(?<!\.)-\.(?!->)|(?<!=)==(?!>)', line)
                if invalid_arrows:
                    errors.append({
                        'line': line_num,
                        'type': 'mermaid_syntax',
                        'message': f"Invalid arrow syntax. Use -->, -.->, or ==>"
                    })

    # Check subgraph/end balance
    subgraph_count = 0
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith('subgraph'):
            subgraph_count += 1
        elif stripped == 'end':
            subgraph_count -= 1
            if subgraph_count < 0:
                errors.append({
                    'line': start_line + i,
                    'type': 'mermaid_syntax',
                    'message': "Unexpected 'end' without matching 'subgraph'"
                })
                subgraph_count = 0  # Reset to avoid cascading errors

    if subgraph_count > 0:
        errors.append({
            'line': start_line,
            'type': 'mermaid_syntax',
            'message': f"Unbalanced subgraph blocks: {subgraph_count} unclosed 'subgraph'"
        })

    # Check final bracket balance
    for bracket, count in brackets.items():
        if count > 0:  # Only report unclosed, not over-closed
            errors.append({
                'line': start_line,
                'type': 'mermaid_syntax',
                'message': f"Unbalanced brackets: {count} unclosed '{bracket}'"
            })

    return errors


def validate_section_structure(content: str, filename: str) -> List[Dict[str, Any]]:
    """Validate section structure compliance."""
    errors = []

    # Skip index.md - it has different structure
    if filename == 'index.md':
        return errors

    # Get content outside code blocks for validation
    filtered_content, _ = extract_content_outside_code_blocks(content)

    # Check for navigation link to index (the byline's Part of link counts)
    if '](index.md)' not in filtered_content:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "Missing link back to index.md — put it in the metadata byline: **Part of**: [Architecture Documentation](index.md)"
        })

    # Check for metadata
    if '**Generated**:' not in filtered_content and '**Part of**:' not in filtered_content:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "Missing metadata (Generated timestamp or Part of)"
        })

    # Check for Introduction section
    if not re.search(r'^#{1,2}\s+Introduction', content, re.MULTILINE | re.IGNORECASE):
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "Missing required 'Introduction' section"
        })

    # Check for Summary section
    if not re.search(r'^#{1,2}\s+Summary', content, re.MULTILINE | re.IGNORECASE):
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "Missing required 'Summary' section"
        })

    # Check for at least one Mermaid diagram (for architecture docs)
    if '```mermaid' not in content:
        # Only warn for architecture-related files
        if any(kw in filename.lower() for kw in ['arch', 'system', 'design']):
            errors.append({
                'line': 1,
                'type': 'missing_section',
                'message': "Architecture file should contain at least one Mermaid diagram"
            })

    # Check for code references (backtick file paths) - only in filtered content
    code_ref_pattern = r'`[a-zA-Z0-9_/.-]+\.(py|js|ts|go|rs|java|c|cpp|h)(?::\d+)?`'
    if not re.search(code_ref_pattern, filtered_content):
        # Only warn for non-overview files
        if 'overview' not in filename.lower() and 'evolution' not in filename.lower() and 'roadmap' not in filename.lower():
            errors.append({
                'line': 1,
                'type': 'missing_section',
                'message': "Missing code file references (e.g., `path/to/file.py:123`)"
            })

    return errors


def validate_links(content: str, docs_dir: Path, current_file: str) -> List[Dict[str, Any]]:
    """Validate internal markdown links and image references (excluding code blocks)."""
    errors = []

    # Get content outside code blocks
    filtered_content, line_mapping = extract_content_outside_code_blocks(content)
    lines = filtered_content.split('\n')

    # Pattern for markdown links/images: [text](path) or ![alt](path)
    link_pattern = r'(!?)\[([^\]]*)\]\(([^)\s]+)\)'

    heading_ids = None  # computed lazily, only when a same-page anchor appears
    current_dir = (docs_dir / current_file).parent

    for i, line in enumerate(lines):
        if not line:  # Skip empty lines (from code blocks)
            continue

        # Strip inline code spans so `[text](file.md)` examples aren't linted
        scan_line = re.sub(r'`[^`]*`', '', line)
        original_line = line_mapping[i] if i < len(line_mapping) else i + 1

        for match in re.finditer(link_pattern, scan_line):
            is_image = match.group(1) == '!'
            link_path = match.group(3)

            # Skip external links
            if link_path.startswith(('http://', 'https://', 'mailto:')):
                continue

            file_path = link_path.split('#')[0]

            # Image references must resolve to a shipped file (the upload API
            # also falls back to basename matching, mirrored here)
            if is_image or any(file_path.lower().endswith(ext) for ext in IMAGE_EXTS):
                target = (current_dir / file_path).resolve() if file_path else None
                if target is None or not target.exists():
                    basename = Path(file_path).name.lower()
                    shipped = {p.name.lower() for p in docs_dir.rglob('*')
                               if p.is_file() and p.suffix.lower() in IMAGE_EXTS}
                    if basename not in shipped:
                        errors.append({
                            'line': original_line,
                            'type': 'broken_image',
                            'message': f"Image reference '{link_path}' does not resolve to a shipped image"
                        })
                continue

            # Same-page anchor links: verify against this file's heading IDs
            if link_path.startswith('#'):
                if heading_ids is None:
                    heading_ids = extract_heading_ids(content)
                anchor = link_path[1:]
                if anchor and anchor not in heading_ids:
                    errors.append({
                        'line': original_line,
                        'type': 'broken_anchor',
                        'message': f"Anchor '{link_path}' matches no heading ID in this file"
                    })
                continue

            if file_path.endswith('.md'):
                # Cross-file anchors are not intercepted by the app's wiki-link
                # handler (only hrefs ending in .md navigate) — they break.
                if '#' in link_path:
                    errors.append({
                        'line': original_line,
                        'type': 'broken_anchor',
                        'message': f"Cross-file anchor '{link_path}' does not navigate in the app — link to the file only"
                    })
                # The upload API flattens paths, so links must target the
                # bare flat filename.
                if '/' in file_path:
                    errors.append({
                        'line': original_line,
                        'type': 'flat_structure',
                        'message': f"Internal link '{link_path}' must target a bare flat filename (no '/')"
                    })

            # Resolve relative path
            if file_path:
                target_path = (current_dir / file_path).resolve()

                if not target_path.exists():
                    errors.append({
                        'line': original_line,
                        'type': 'broken_link',
                        'message': f"Broken link: '{link_path}' does not exist"
                    })

    return errors


def validate_tables(content: str) -> List[Dict[str, Any]]:
    """Validate markdown table format (excluding tables in code blocks)."""
    errors = []

    # Get content outside code blocks
    filtered_content, line_mapping = extract_content_outside_code_blocks(content)
    lines = filtered_content.split('\n')

    in_table = False
    table_start = 0
    expected_cols = 0

    for i, line in enumerate(lines):
        if not line:  # Skip empty lines (from code blocks)
            if in_table:
                in_table = False
            continue

        stripped = line.strip()

        # Detect table start (header row with |)
        if '|' in stripped and not in_table:
            # Check if this looks like a table header (at least 2 pipes)
            if stripped.count('|') >= 2:
                in_table = True
                table_start = i
                expected_cols = stripped.count('|')
                continue

        if in_table:
            if not stripped or '|' not in stripped:
                # Table ended
                in_table = False
                continue

            # Check separator row (should have | and -)
            if i == table_start + 1:
                if not re.match(r'^\|?[\s\-:|]+\|?$', stripped):
                    original_line = line_mapping[i] if i < len(line_mapping) else i + 1
                    errors.append({
                        'line': original_line,
                        'type': 'table_format',
                        'message': "Invalid table separator row (should be |---|---|)"
                    })
                continue

            # Check column count consistency
            col_count = stripped.count('|')
            if col_count != expected_cols:
                original_line = line_mapping[i] if i < len(line_mapping) else i + 1
                errors.append({
                    'line': original_line,
                    'type': 'table_format',
                    'message': f"Inconsistent column count: expected {expected_cols}, got {col_count}"
                })

    return errors


def validate_word_count(content: str, filename: str) -> List[Dict[str, Any]]:
    """Validate document has adequate word count."""
    errors = []

    # Skip index.md - it has different structure
    if filename == 'index.md':
        return errors

    # Get content outside code blocks
    filtered_content, _ = extract_content_outside_code_blocks(content)

    # Count words (excluding markdown syntax)
    text_only = re.sub(r'[#*`|\->\[\]()]', ' ', filtered_content)
    words = [w for w in text_only.split() if len(w) > 1]
    word_count = len(words)

    if word_count < MIN_DESCRIPTION_WORDS:
        errors.append({
            'line': 1,
            'type': 'word_count',
            'message': f"Document too short: {word_count} words (minimum: {MIN_DESCRIPTION_WORDS})"
        })

    if word_count > MAX_DESCRIPTION_WORDS:
        errors.append({
            'line': 1,
            'type': 'word_count',
            'message': f"Document too long: {word_count} words (maximum: {MAX_DESCRIPTION_WORDS})"
        })

    return errors


def validate_filename_convention(filename: str) -> List[Dict[str, Any]]:
    """Validate the export's file-naming convention (numbered, un-padded,
    lowercase kebab-case slugs). The app sorts numbered prefixes numerically;
    these rules keep filenames, sidebar labels, and links consistent."""
    errors = []

    if filename in ('index.md', 'overview.md'):
        return errors

    m = re.match(r'^(\d+(?:-\d+)*)-(.+)\.md$', filename)
    if m:
        prefix, slug = m.group(1), m.group(2)
        if re.search(r'(?:^|-)0\d', prefix):
            errors.append({
                'line': 1,
                'type': 'filename_convention',
                'message': f"Zero-padded number part in '{filename}' — use un-padded prefixes (1-, 2-, 10-)"
            })
        if not re.match(r'^[a-z][a-z0-9-]*$', slug):
            errors.append({
                'line': 1,
                'type': 'filename_convention',
                'message': f"Slug after the numeric prefix must be lowercase kebab-case starting with a letter: '{filename}'"
            })
    else:
        errors.append({
            'line': 1,
            'type': 'filename_convention',
            'severity': 'warning',
            'message': f"'{filename}' has no numeric prefix — it will sort after all numbered sections in the sidebar"
        })

    return errors


def validate_metadata_placement(content: str, filename: str) -> List[Dict[str, Any]]:
    """The app styles the metadata byline only when it directly follows the
    FIRST H1 — content before the H1, a second H1, or anything between the
    H1 and the byline breaks the styling."""
    errors = []

    filtered_content, line_mapping = extract_content_outside_code_blocks(content)
    lines = filtered_content.split('\n')

    h1_indices = [i for i, line in enumerate(lines) if re.match(r'^#\s+\S', line)]

    if not h1_indices:
        errors.append({
            'line': 1,
            'type': 'metadata_placement',
            'message': "File has no H1 title — the app uses the H1 as the page title and byline anchor"
        })
        return errors

    if len(h1_indices) > 1:
        errors.append({
            'line': line_mapping[h1_indices[1]],
            'type': 'metadata_placement',
            'message': "Multiple H1 headings — only the first H1 gets byline styling; use H2+ for sections"
        })

    first_h1 = h1_indices[0]
    before = [l for l in lines[:first_h1] if l.strip()]
    if before:
        errors.append({
            'line': line_mapping[0],
            'type': 'metadata_placement',
            'message': "Content before the H1 — the metadata byline must directly follow the H1, with nothing above it"
        })

    after = next((l for l in lines[first_h1 + 1:] if l.strip()), '')
    if not re.match(r'^\**Part of\**\s*:', after):
        errors.append({
            'line': line_mapping[first_h1],
            'type': 'metadata_placement',
            'message': "First paragraph after the H1 must be the metadata byline starting with **Part of**:"
        })

    return errors


def validate_unsupported_markdown(content: str) -> List[Dict[str, Any]]:
    """Flag markdown the DeepWiki app renders literally (no marked extension
    is configured for these)."""
    errors = []

    filtered_content, line_mapping = extract_content_outside_code_blocks(content)

    for i, line in enumerate(filtered_content.split('\n')):
        if not line:
            continue
        # Strip inline code spans so regex/code examples don't false-positive
        scan = re.sub(r'`[^`]*`', '', line)
        original_line = line_mapping[i] if i < len(line_mapping) else i + 1

        if re.match(r'^\s*[-*+]\s+\[[ xX]\]\s', scan):
            errors.append({
                'line': original_line,
                'type': 'unsupported_markdown',
                'message': "Task-list syntax '- [ ]' renders literally in the app — use plain bullets"
            })
        if re.search(r'\[\^[^\]\s]+\]', scan):
            errors.append({
                'line': original_line,
                'type': 'unsupported_markdown',
                'severity': 'warning',
                'message': "Footnote syntax '[^..]' is not supported by the app renderer"
            })
        if '$$' in scan:
            errors.append({
                'line': original_line,
                'type': 'unsupported_markdown',
                'severity': 'warning',
                'message': "Math/LaTeX is not rendered — write formulas as code spans or Unicode"
            })

    return errors


def validate_adr_file(content: str, filename: str) -> List[Dict[str, Any]]:
    """Validate an Architecture Decision Record file."""
    errors = []

    # Check naming convention: flat numbered child of the ADR section,
    # e.g. 9-1-adr-use-postgres.md (sorts under section 9 in the app sidebar)
    if not re.match(r'^\d+(-\d+)*-adr-[a-z]', filename):
        errors.append({
            'line': 1,
            'type': 'adr_format',
            'message': f"ADR filename should match N-M-adr-<slug>.md (flat, numbered under the ADR section): '{filename}'"
        })

    # Check required sections
    for section in ['## Context', '## Decision', '## Consequences']:
        if section not in content:
            errors.append({
                'line': 1,
                'type': 'adr_format',
                'message': f"ADR missing required section: '{section}'"
            })

    # Check for status metadata
    if '**Status**:' not in content:
        errors.append({
            'line': 1,
            'type': 'adr_format',
            'message': "ADR missing **Status**: metadata"
        })

    return errors


def validate_index(content: str, docs_dir: Path) -> List[Dict[str, Any]]:
    """Validate index.md has required structure."""
    errors = []

    # YAML frontmatter names the wiki: the DeepWiki upload API reads
    # title/slug/description from it (falling back to the first H1 and an
    # auto-derived slug), and re-uploads match the existing wiki by slug.
    fm_match = re.match(r'\A---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "index.md missing YAML frontmatter (title/slug/description name the wiki on upload)"
        })
    else:
        fm = fm_match.group(1)
        for key in ('title', 'slug', 'description'):
            value_match = re.search(rf'^{key}\s*:\s*(\S.*)$', fm, re.MULTILINE)
            if not value_match:
                errors.append({
                    'line': 1,
                    'type': 'missing_section',
                    'message': f"index.md frontmatter missing '{key}:'"
                })
                continue
            value = value_match.group(1).strip()
            # Unquoted values containing ': ' break YAML parsing (gray-matter
            # on the server) and silently lose the wiki identity.
            if value[0] not in '"\'' and ': ' in value:
                errors.append({
                    'line': 1,
                    'type': 'frontmatter',
                    'message': f"Frontmatter '{key}' value contains ': ' — quote it to keep the YAML parseable"
                })
            if key == 'slug':
                slug = value.strip('"\'')
                if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', slug):
                    errors.append({
                        'line': 1,
                        'type': 'frontmatter',
                        'message': f"Frontmatter slug '{slug}' must be lowercase kebab-case ([a-z0-9-], used verbatim in the wiki URL)"
                    })

    if '## Overview' not in content:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "index.md missing required '## Overview' section"
        })

    # Count internal links to .md files
    link_pattern = r'\[([^\]]+)\]\(([^)]+\.md[^)]*)\)'
    links = re.findall(link_pattern, content)
    internal_links = [l for l in links if not l[1].startswith('http')]
    if len(internal_links) < 3:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': f"index.md should link to at least 3 section files (found {len(internal_links)})"
        })

    # Check for metadata line
    if 'Last indexed' not in content and 'Commit' not in content:
        errors.append({
            'line': 1,
            'type': 'missing_section',
            'message': "index.md missing metadata (Last indexed / Commit hash)"
        })

    return errors


def validate_file(file_path: Path, docs_dir: Path) -> List[Dict[str, Any]]:
    """Validate a single markdown file."""
    errors = []

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return [{'line': 0, 'type': 'read_error', 'message': str(e)}]

    lines = content.split('\n')
    filename = file_path.name

    # Find and validate Mermaid blocks
    in_mermaid = False
    mermaid_start = 0
    mermaid_content = []

    for i, line in enumerate(lines, 1):
        if line.strip().startswith('```mermaid'):
            in_mermaid = True
            mermaid_start = i + 1
            mermaid_content = []
        elif in_mermaid and line.strip() == '```':
            in_mermaid = False
            mermaid_errors = validate_mermaid_block('\n'.join(mermaid_content), mermaid_start)
            errors.extend(mermaid_errors)
        elif in_mermaid:
            mermaid_content.append(line)

    # Determine file type and apply appropriate validators.
    # ADRs are flat numbered children (e.g. 9-1-adr-use-postgres.md) — the
    # DeepWiki upload API flattens subdirectories, so an adr/ folder would
    # break links and ordering after upload.
    is_adr = bool(re.match(r'^\d+(-\d+)*-adr-', filename))
    is_index = filename == 'index.md'

    if is_adr:
        # ADR files have their own structure requirements (no word count minimum)
        errors.extend(validate_adr_file(content, filename))
        errors.extend(validate_metadata_placement(content, filename))
    elif is_index:
        # index.md has its own structure requirements (frontmatter precedes
        # the H1, so metadata placement is not enforced there)
        errors.extend(validate_index(content, docs_dir))
    else:
        # Regular section files
        errors.extend(validate_section_structure(content, filename))
        errors.extend(validate_word_count(content, filename))
        errors.extend(validate_metadata_placement(content, filename))

    # Common validators for all file types
    errors.extend(validate_filename_convention(filename))
    errors.extend(validate_links(content, docs_dir, filename))
    errors.extend(validate_tables(content))
    errors.extend(validate_unsupported_markdown(content))

    return errors


def validate_docs(docs_dir: str) -> Dict[str, Any]:
    """Validate all documentation in a directory."""
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        return {
            'status': 'error',
            'message': f"Directory not found: {docs_dir}"
        }

    all_errors = []
    total_files = 0

    # Find all markdown files
    for md_file in docs_path.glob('**/*.md'):
        total_files += 1

        # The upload API flattens subdirectory paths (adr/x.md -> adr-x.md),
        # breaking links and ordering — every .md must sit at the export root.
        if md_file.parent != docs_path:
            all_errors.append({
                'file': str(md_file.relative_to(docs_path)),
                'line': 1,
                'type': 'flat_structure',
                'message': "Markdown file in a subdirectory — all .md files must sit flat at the export root"
            })

        file_errors = validate_file(md_file, docs_path)

        for error in file_errors:
            error['file'] = str(md_file.relative_to(docs_path))
            all_errors.append(error)

    # Image assets: upload budget and basename uniqueness. The app matches
    # image refs by basename (case-insensitive, extension optional), so
    # foo.png and foo.svg collide and get silently renamed on upload.
    image_files = [p for p in docs_path.rglob('*')
                   if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
    total_bytes = sum(p.stat().st_size for p in image_files)
    total_bytes += sum(p.stat().st_size for p in docs_path.glob('**/*.md'))

    for img in image_files:
        if img.stat().st_size > MAX_IMAGE_BYTES:
            all_errors.append({
                'file': str(img.relative_to(docs_path)),
                'line': 0,
                'type': 'image_assets',
                'message': f"Image is {img.stat().st_size // 1024} KB — exceeds the {MAX_IMAGE_BYTES // (1024*1024)} MB per-image upload limit"
            })

    if total_files + len(image_files) > MAX_FILES:
        all_errors.append({
            'file': '.', 'line': 0, 'type': 'image_assets',
            'message': f"{total_files + len(image_files)} files exceed the {MAX_FILES}-file upload limit — trim or merge"
        })
    if total_bytes > MAX_TOTAL_BYTES:
        all_errors.append({
            'file': '.', 'line': 0, 'type': 'image_assets',
            'message': f"Export totals {total_bytes // 1024} KB — exceeds the {MAX_TOTAL_BYTES // (1024*1024)} MB upload limit"
        })

    stems_seen: Dict[str, str] = {}
    for img in image_files:
        key = img.stem.lower()
        if key in stems_seen:
            all_errors.append({
                'file': str(img.relative_to(docs_path)),
                'line': 0,
                'type': 'image_assets',
                'message': f"Image basename collides with '{stems_seen[key]}' (matching is case-insensitive and extension-blind) — rename to a unique, descriptive basename"
            })
        else:
            stems_seen[key] = img.name

    # Unreferenced shipped images (warning — they still upload and count
    # against the budget)
    referenced = set()
    for md_file in docs_path.glob('**/*.md'):
        text = md_file.read_text(encoding='utf-8', errors='replace')
        for m in re.finditer(r'!\[[^\]]*\]\(([^)\s]+)\)', text):
            name = Path(m.group(1).split('#')[0]).name.lower()
            referenced.add(name)
            referenced.add(Path(name).stem)
    for img in image_files:
        if img.name.lower() not in referenced and img.stem.lower() not in referenced:
            all_errors.append({
                'file': str(img.relative_to(docs_path)),
                'line': 0,
                'type': 'image_assets',
                'severity': 'warning',
                'message': "Shipped image is never referenced from any markdown file"
            })

    # Cross-file consistency: check index.md links match actual files
    index_path = docs_path / 'index.md'
    if index_path.exists():
        index_content = index_path.read_text(encoding='utf-8')
        link_pattern = r'\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]*)?\)'
        index_links = set()
        for match in re.finditer(link_pattern, index_content):
            link_target = match.group(2)
            if not link_target.startswith('http'):
                index_links.add(link_target)

        # Check for orphaned section files (not linked from index)
        for md_file in docs_path.glob('*.md'):
            if md_file.name == 'index.md':
                continue
            if md_file.name not in index_links:
                all_errors.append({
                    'file': 'index.md',
                    'line': 1,
                    'type': 'cross_reference',
                    'message': f"Section file '{md_file.name}' exists but is not linked from index.md"
                })

    # Warnings (entries marked severity: warning) don't fail validation —
    # they are a review worklist, not blockers.
    warnings = [e for e in all_errors if e.get('severity') == 'warning']
    errors = [e for e in all_errors if e.get('severity') != 'warning']

    return {
        'status': 'success' if not errors else 'errors_found',
        'total_files': total_files,
        'total_errors': len(errors),
        'total_warnings': len(warnings),
        'errors': errors,
        'warnings': warnings
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_docs.py <docs_directory>", file=sys.stderr)
        sys.exit(1)

    docs_dir = sys.argv[1]
    result = validate_docs(docs_dir)

    print(json.dumps(result, indent=2))

    # Exit with error code if errors found
    if result['status'] != 'success':
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Validation script for DeepWiki documentation.
Checks Mermaid syntax, section structure, links, and table format.
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple


# Word count limits for document validation (per markdown file)
MIN_DESCRIPTION_WORDS = 1500  # Minimum words for comprehensive documentation
MAX_DESCRIPTION_WORDS = 6000


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


def validate_mermaid_block(content: str, start_line: int) -> List[Dict[str, Any]]:
    """Validate a Mermaid diagram block for syntax errors."""
    errors = []
    lines = content.split('\n')

    # Reserved keywords that can't be used as node IDs
    reserved = {'end', 'click', 'style', 'classDef', 'class', 'linkStyle'}

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

    # Check for navigation link to index
    if '[<-Back to Index](index.md)' not in filtered_content:
        if '](index.md)' not in filtered_content:
            errors.append({
                'line': 1,
                'type': 'missing_section',
                'message': "Missing navigation link to index.md (use [<-Back to Index](index.md))"
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
    """Validate internal markdown links (excluding those in code blocks)."""
    errors = []

    # Get content outside code blocks
    filtered_content, line_mapping = extract_content_outside_code_blocks(content)
    lines = filtered_content.split('\n')

    # Pattern for markdown links: [text](path.md) or [text](path.md#anchor)
    link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'

    for i, line in enumerate(lines):
        if not line:  # Skip empty lines (from code blocks)
            continue

        for match in re.finditer(link_pattern, line):
            link_text, link_path = match.groups()

            # Skip external links
            if link_path.startswith('http://') or link_path.startswith('https://'):
                continue

            # Skip anchor-only links
            if link_path.startswith('#'):
                continue

            # Extract file path (remove anchor if present)
            file_path = link_path.split('#')[0]

            # Skip image links
            if any(file_path.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
                continue

            # Resolve relative path
            if file_path:
                current_dir = (docs_dir / current_file).parent
                target_path = (current_dir / file_path).resolve()

                if not target_path.exists():
                    original_line = line_mapping[i] if i < len(line_mapping) else i + 1
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


def validate_adr_file(content: str, filename: str) -> List[Dict[str, Any]]:
    """Validate an Architecture Decision Record file."""
    errors = []

    # Check naming convention (NNNN-*.md)
    if not re.match(r'^\d{4}-', filename):
        errors.append({
            'line': 1,
            'type': 'adr_format',
            'message': f"ADR filename should start with NNNN- prefix: '{filename}'"
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

    # Determine file type and apply appropriate validators
    is_adr = 'adr' in str(file_path.parent.name)
    is_index = filename == 'index.md'

    if is_adr:
        # ADR files have their own structure requirements (no word count minimum)
        errors.extend(validate_adr_file(content, filename))
    elif is_index:
        # index.md has its own structure requirements
        errors.extend(validate_index(content, docs_dir))
    else:
        # Regular section files
        errors.extend(validate_section_structure(content, filename))
        errors.extend(validate_word_count(content, filename))

    # Common validators for all file types
    errors.extend(validate_links(content, docs_dir, filename))
    errors.extend(validate_tables(content))

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
        file_errors = validate_file(md_file, docs_path)

        for error in file_errors:
            error['file'] = str(md_file.relative_to(docs_path))
            all_errors.append(error)

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

    return {
        'status': 'success' if not all_errors else 'errors_found',
        'total_files': total_files,
        'total_errors': len(all_errors),
        'errors': all_errors
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

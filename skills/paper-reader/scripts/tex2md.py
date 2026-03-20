#!/usr/bin/env python3
"""
tex2md.py — Convert paper-reader skill LaTeX analysis (.tex) to Markdown (.md).

Usage:
    python3 tex2md.py INPUT.tex [OUTPUT.md]

Exits 1 if any \\includegraphics in the .tex has no matching ![]() in the .md.
"""

import re
import sys
from pathlib import Path


# ── Math protection ────────────────────────────────────────────────────────────

def _protect_math(s: str) -> tuple[str, list[str]]:
    phs: list[str] = []

    def _ph(m: re.Match) -> str:
        phs.append(m.group(0))
        return f'\x00M{len(phs)-1}\x00'

    s = re.sub(r'\\\[[\s\S]*?\\\]', _ph, s)        # \[...\]
    s = re.sub(r'\$\$[\s\S]*?\$\$', _ph, s)         # $$...$$
    s = re.sub(r'\$[^$\n]+?\$', _ph, s)             # $...$
    return s, phs


def _restore_math(s: str, phs: list[str]) -> str:
    for i, p in enumerate(phs):
        s = s.replace(f'\x00M{i}\x00', p)
    return s


# ── Inline substitution ────────────────────────────────────────────────────────

def inline(s: str) -> str:
    """Convert inline LaTeX to Markdown, preserving math spans."""
    s, phs = _protect_math(s)
    s = re.sub(r'(?<!\\)%.*', '', s)           # strip comments
    s = re.sub(r'\\label\{[^}]*\}', '', s)     # \label{}

    # Cross-references → remove phrase (including surrounding brackets if present)
    s = re.sub(r'[（(]\s*如图[~\s]*\\ref\{[^}]*\}\s*所示\s*[，,]?\s*[）)]', '', s)
    s = re.sub(r'如图[~\s]*\\ref\{[^}]*\}\s*所示[，,]?', '', s)
    s = re.sub(r'如图[~\s]*\\ref\{[^}]*\}', '', s)
    s = re.sub(r'[（(]?(?:公式|式|定理|算法)[~\s]*(?:\(?\\ref\{[^}]*\}\)?)[ ）)]*', '', s)
    s = re.sub(r'图[~\s]*\\ref\{[^}]*\}', '', s)
    s = re.sub(r'\\ref\{[^}]*\}', '', s)
    s = re.sub(r'\\cite(?:p|t)?\{[^}]*\}', '', s)
    s = re.sub(r'[（(]\s*[）)]', '', s)             # clean up empty brackets left by ref removal

    # Iterative command expansion (handles one level of nesting per pass)
    for _ in range(4):
        s = re.sub(r'\\textbf\{([^{}]*)\}', r'**\1**', s)
        s = re.sub(r'\\(?:textit|emph)\{([^{}]*)\}', r'*\1*', s)
        s = re.sub(r'\\texttt\{([^{}]*)\}', r'`\1`', s)
        s = re.sub(r'\\text(?:sf|rm|sc|up|md|normal|bf)?\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\(?:mbox|hbox|fbox|raisebox\{[^}]*\})\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\makecell(?:\[[^\]]*\])?\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\multirow\{[^}]*\}\{[^}]*\}\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\multicolumn\{[^}]*\}\{[^}]*\}\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\[gro]mark\{([^{}]*)\}', r'**\1**', s)
        s = re.sub(r'\\textcolor\{[^}]*\}\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\colorbox\{[^}]*\}\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\href\{([^}]*)\}\{([^{}]*)\}', r'[\2](\1)', s)
        s = re.sub(r'\\footnote\{([^{}]*)\}', r' (\1)', s)

    s = re.sub(r'\\url\{([^}]*)\}', r'<\1>', s)
    s = re.sub(r'\\textsc\{([^{}]*)\}', r'\1', s)

    for old, new in [
        ('\\ratingfull', '★'), ('\\ratinghalf', '★'), ('\\ratingempty', '☆'),
        ('\\textbullet', '•'), ('\\checkmark', '✓'), ('\\xmark', '✗'),
        ('\\times', '×'), ('\\cdot', '·'), ('\\ldots', '…'), ('\\dots', '…'),
        ('\\%', '%'), ('\\&', '&'), ('\\#', '#'), ('\\_', '_'),
        ('\\{', '{'), ('\\}', '}'),
        ('---', '—'), ('--', '–'),
        ("''", '"'), ('``', '"'),
    ]:
        s = s.replace(old, new)

    s = re.sub(r'~', ' ', s)
    s = re.sub(r'\\[,;!]', '', s)
    s = re.sub(r'\\ ', ' ', s)
    s = re.sub(r'\\quad\b', ' ', s)
    s = re.sub(r'\\qquad\b', '  ', s)
    s = re.sub(r'\\\\\s*(?:\[[^\]]*\])?', ' ', s)   # \\ line break → space
    s = re.sub(r'\\(?:centering|noindent|medskip|smallskip|bigskip|hfill|vfill)\b', '', s)
    s = re.sub(r'\\(?:vspace|hspace)\*?\{[^}]*\}', '', s)
    s = re.sub(r'\\(?:small|large|Large|LARGE|huge|Huge|normalsize|footnotesize|scriptsize)\b', '', s)
    s = re.sub(r'\\(?:bfseries|itshape|sffamily|ttfamily|rmfamily)\b', '', s)
    s = re.sub(r'@\{\}', '', s)   # tabular @{} artifacts
    s = re.sub(r'  +', ' ', s)
    s = _restore_math(s, phs)
    return s.strip()


# ── Converter ──────────────────────────────────────────────────────────────────

class Converter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.pos: int = 0

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _s(self, line: str) -> str:
        """Strip comments + whitespace."""
        return re.sub(r'(?<!\\)%.*', '', line).strip()

    def _collect_env(self, env: str) -> list[str]:
        """Collect lines until matching \\end{env}. Advances pos past \\end."""
        collected: list[str] = []
        depth = 1
        while self.pos < len(self.lines):
            line = self.lines[self.pos]
            self.pos += 1
            s = self._s(line)
            if re.search(r'\\begin\{' + re.escape(env) + r'\}', s):
                depth += 1
            if re.search(r'\\end\{' + re.escape(env) + r'\}', s):
                depth -= 1
                if depth == 0:
                    return collected
            collected.append(line)
        return collected

    def _collect_braced(self, first_line: str) -> tuple[str, bool]:
        """
        Given a line containing an opening '{', collect until the brace closes,
        reading more lines from self if needed.
        Returns (content_inside_braces, consumed_extra_lines).
        """
        open_pos = first_line.find('{')
        if open_pos == -1:
            return '', False
        depth = 1
        chars: list[str] = []
        i = open_pos + 1
        rest = first_line
        extra = False
        while True:
            while i < len(rest):
                c = rest[i]
                if c == '{':
                    depth += 1
                    chars.append(c)
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return ''.join(chars), extra
                    chars.append(c)
                else:
                    chars.append(c)
                i += 1
            # Need another line
            if self.pos >= len(self.lines):
                break
            chars.append('\n')
            rest = self.lines[self.pos]
            self.pos += 1
            extra = True
            i = 0
        return ''.join(chars), extra

    def _sub_convert(self, lines: list[str]) -> list[str]:
        sub = Converter()
        sub.lines = lines
        sub.pos = 0
        out: list[str] = []
        while sub.pos < len(sub.lines):
            out.extend(sub._next_block())
        return out

    # ── Public entry ──────────────────────────────────────────────────────────

    def convert(self, tex: str) -> str:
        m = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', tex, re.DOTALL)
        body = m.group(1) if m else tex
        self.lines = body.split('\n')
        self.pos = 0

        parts: list[str] = []
        while self.pos < len(self.lines):
            parts.extend(self._next_block())

        # Collapse multiple blank lines to one
        result: list[str] = []
        prev_blank = False
        for p in parts:
            if p == '':
                if not prev_blank:
                    result.append(p)
                prev_blank = True
            else:
                result.append(p)
                prev_blank = False

        return '\n'.join(result).strip() + '\n'

    # ── Block dispatch ────────────────────────────────────────────────────────

    def _next_block(self) -> list[str]:
        if self.pos >= len(self.lines):
            return []
        line = self.lines[self.pos]
        s = self._s(line)

        # Blank / comment-only
        if not s or s.startswith('%'):
            self.pos += 1
            return [''] if not s else []

        # Skip pure layout commands
        if re.match(r'\\(?:vspace|hspace)\*?\{', s):
            self.pos += 1
            return []
        if re.match(r'\\(?:newpage|clearpage|cleardoublepage)\b', s):
            self.pos += 1
            return ['', '---', '']
        if re.match(r'\\(?:tableofcontents|listoffigures|listoftables|maketitle)\b', s):
            self.pos += 1
            return []
        if re.match(r'\\(?:medskip|smallskip|bigskip|hfill|vfill|noindent|centering)\b', s):
            self.pos += 1
            return []

        # Brace group { ... } at top level — e.g. {\hypersetup{...}\tableofcontents}
        if s == '{':
            self.pos += 1
            depth = 1
            while self.pos < len(self.lines) and depth > 0:
                l = self.lines[self.pos]
                self.pos += 1
                depth += l.count('{') - l.count('}')
            return []

        # ── Title block commands ──────────────────────────────────────────────

        if re.match(r'\\papertitle\{', s):
            self.pos += 1
            content, _ = self._collect_braced(s)
            return [f'# {inline(content)}', '']

        if re.match(r'\\paperauthors\{', s):
            self.pos += 1
            content, _ = self._collect_braced(s)
            return [f'**作者**: {inline(content)}', '']

        if re.match(r'\\papervenue\{', s):
            self.pos += 1
            content, _ = self._collect_braced(s)
            return [f'**发表**: {inline(content)}', '']

        if re.match(r'\\paperdate\{', s):
            self.pos += 1
            content, _ = self._collect_braced(s)
            val = inline(content).replace('\\today', '').strip()
            return ([f'**分析日期**: {val}', ''] if val else [])

        # ── Section commands ──────────────────────────────────────────────────

        # Brace-aware arg pattern: handles up to 2 levels of nesting
        # e.g. \paragraph{$\mathbf{dQ}$ text} — stops at matching }, not first }
        _BA = r'(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*'

        m = re.match(r'\\section\{(' + _BA + r')\}', s)
        if m:
            self.pos += 1
            return ['', f'# {inline(m.group(1))}', '']

        m = re.match(r'\\subsection\{(' + _BA + r')\}', s)
        if m:
            self.pos += 1
            return ['', f'## {inline(m.group(1))}', '']

        m = re.match(r'\\subsubsection\{(' + _BA + r')\}', s)
        if m:
            self.pos += 1
            return ['', f'### {inline(m.group(1))}', '']

        m = re.match(r'\\paragraph\{(' + _BA + r')\}(.*)', s)
        if m:
            self.pos += 1
            title = inline(m.group(1))
            rest_text = inline(m.group(2)).strip()
            out = ['', f'**{title}**']
            if rest_text:
                out += ['', rest_text]
            return out

        # ── Display math \[...\] ──────────────────────────────────────────────

        if s == '\\[':
            self.pos += 1
            math_lines: list[str] = []
            while self.pos < len(self.lines):
                l = self.lines[self.pos]
                self.pos += 1
                if self._s(l) == '\\]':
                    break
                math_lines.append(l.rstrip())
            math = '\n'.join(math_lines).strip()
            return ['', f'$$\n{math}\n$$', '']

        # ── \begin{env} ───────────────────────────────────────────────────────

        m = re.match(r'\\begin\{(\w+\*?)\}(.*)', s)
        if m:
            env = m.group(1)
            rest = m.group(2).strip()
            self.pos += 1
            env_lines = self._collect_env(env)
            return self._handle_env(env, rest, env_lines)

        # ── \end{env} at top level (stray) ───────────────────────────────────

        if re.match(r'\\end\{', s):
            self.pos += 1
            return []

        # ── Regular paragraph ─────────────────────────────────────────────────

        _STRUCTURAL = re.compile(
            r'\\(?:section|subsection|subsubsection|paragraph|begin|end|'
            r'newpage|clearpage|papertitle|paperauthors|papervenue|paperdate|'
            r'tableofcontents|vspace|hspace)\b'
        )
        para: list[str] = []
        while self.pos < len(self.lines):
            l = self.lines[self.pos]
            s2 = self._s(l)
            if not s2:
                break
            if s2.startswith('%'):
                self.pos += 1
                continue
            if _STRUCTURAL.match(s2) or s2 in ('\\[', '{'):
                break
            para.append(inline(s2))
            self.pos += 1

        text = ' '.join(para).strip()
        if text:
            return [text]
        # Nothing collected — skip one line to avoid infinite loop
        self.pos += 1
        return []

    # ── Environment handlers ──────────────────────────────────────────────────

    def _handle_env(self, env: str, rest: str, lines: list[str]) -> list[str]:
        opt_m = re.match(r'\[([^\]]*)\](.*)', rest)
        opt = opt_m.group(1) if opt_m else ''

        dispatch: dict = {
            'keyinsight':  self._keyinsight,
            'strengthbox': self._box,
            'weaknessbox': self._box,
            'mathbox':     self._mathbox,
            'infobox':     self._infobox,
            'figure':      self._figure,
            'table':       self._table,
            'tabular':     self._tabular,
            'tabularx':    self._tabular,
            'longtable':   self._tabular,
            'itemize':     self._list_env,
            'enumerate':   self._list_env,
            'equation':    self._equation,
            'equation*':   self._equation,
            'align':       self._align,
            'align*':      self._align,
            'gather':      self._align,
            'gather*':     self._align,
            'lstlisting':  self._lstlisting,
            'verbatim':    self._verbatim,
            'center':      lambda o, l: self._sub_convert(l),
            'flushleft':   lambda o, l: self._sub_convert(l),
            'flushright':  lambda o, l: self._sub_convert(l),
            'minipage':    lambda o, l: self._sub_convert(l),
            'subfigure':   lambda o, l: [],   # handled inside _figure
            'algorithm':   lambda o, l: [],
            'algorithmic': lambda o, l: [],
            'algorithm2e': lambda o, l: [],
            'abstract':    lambda o, l: self._sub_convert(l),
        }
        handler = dispatch.get(env)
        if handler:
            return handler(opt, lines)
        return self._sub_convert(lines)

    def _keyinsight(self, title: str, lines: list[str]) -> list[str]:
        title = inline(title)
        inner = self._sub_convert(lines)
        non_blank = [l for l in inner if l]

        if title in ('TL;DR', 'TL; DR'):
            label = '📌 **TL;DR**'
        elif title == '一句话总结':
            label = '📌 **一句话总结**'
        else:
            label = f'📌 **{title}**'

        if len(non_blank) <= 1:
            content = non_blank[0] if non_blank else ''
            return ['', f'> {label}: {content}', '']

        # Multi-line blockquote
        out = ['', f'> {label}:', '>']
        for l in non_blank:
            out.append(f'> {l}')
        out.append('')
        return out

    def _box(self, title: str, lines: list[str]) -> list[str]:
        return [''] + self._sub_convert(lines) + ['']

    def _mathbox(self, title: str, lines: list[str]) -> list[str]:
        title = inline(title)
        inner = self._sub_convert(lines)
        out = ['']
        if title:
            out += [f'**{title}**', '']
        out += inner + ['']
        return out

    def _infobox(self, title: str, lines: list[str]) -> list[str]:
        return self._table(title, lines)

    def _figure(self, opt: str, lines: list[str]) -> list[str]:
        text = '\n'.join(lines)
        paths = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', text)
        cap_m = re.search(r'\\caption\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}', text)
        caption = inline(cap_m.group(1)) if cap_m else ''
        if not paths:
            return []
        out = ['']
        for p in paths:
            out.append(f'![{caption}]({p})')
        out.append('')
        return out

    def _table(self, title: str, lines: list[str]) -> list[str]:
        tab_envs = ('tabular', 'tabularx', 'longtable')
        for i, line in enumerate(lines):
            for te in tab_envs:
                m = re.match(r'\s*\\begin\{' + te + r'\}(.*)', line)
                if m:
                    spec = m.group(1).strip()
                    tab_lines: list[str] = []
                    depth = 1
                    j = i + 1
                    while j < len(lines):
                        l = lines[j]
                        for te2 in tab_envs:
                            if re.search(r'\\begin\{' + te2 + r'\}', l):
                                depth += 1
                            if re.search(r'\\end\{' + te2 + r'\}', l):
                                depth -= 1
                        if depth == 0:
                            break
                        tab_lines.append(l)
                        j += 1
                    return [''] + self._tabular(spec, tab_lines) + ['']
        return self._sub_convert(lines)

    def _tabular(self, spec: str, lines: list[str]) -> list[str]:
        rows: list[list[str]] = []
        current = ''
        for line in lines:
            s = self._s(line)
            if not s:
                continue
            if re.match(r'\\(?:toprule|midrule|bottomrule|hline)\b', s):
                continue
            if re.match(r'\\(?:caption|label)\{', s):
                continue
            if re.match(r'^\[[0-9]+[a-z]*\]$', s):   # [4pt] spacing spec
                continue
            current += ' ' + s
            if '\\\\' in current:
                parts = current.split('\\\\')
                for part in parts[:-1]:
                    part = re.sub(r'^\s*\[[^\]]*\]', '', part).strip()  # strip [4pt]
                    if not part:
                        continue
                    # Replace \& with placeholder before splitting on & column separator
                    safe = part.replace('\\&', '\x00AMP\x00')
                    cells = [inline(c.replace('\x00AMP\x00', '&').strip()) for c in safe.split('&')]
                    rows.append(cells)
                current = parts[-1]

        # Flush remaining (row without \\)
        if current.strip():
            safe = current.replace('\\&', '\x00AMP\x00')
            cells = [inline(c.replace('\x00AMP\x00', '&').strip()) for c in safe.split('&')]
            if any(c for c in cells):
                rows.append(cells)

        if not rows:
            return []
        ncols = max(len(r) for r in rows)
        pad = lambda r: r + [''] * max(0, ncols - len(r))
        out = [
            '| ' + ' | '.join(pad(rows[0])) + ' |',
            '| ' + ' | '.join(['---'] * ncols) + ' |',
        ]
        for row in rows[1:]:
            out.append('| ' + ' | '.join(pad(row)) + ' |')
        return out

    def _list_env(self, env: str, lines: list[str]) -> list[str]:
        is_ordered = (env == 'enumerate')
        out: list[str] = ['']
        counter = 0
        i = 0
        while i < len(lines):
            line = lines[i]
            s = self._s(line)
            if not s or s.startswith('%'):
                i += 1
                continue

            # Nested environment
            bm = re.match(r'\\begin\{(\w+\*?)\}(.*)', s)
            if bm:
                nested_env = bm.group(1)
                nested_rest = bm.group(2)
                i += 1
                nested_lines: list[str] = []
                depth = 1
                while i < len(lines):
                    nl = lines[i]
                    ns = self._s(nl)
                    i += 1
                    if re.search(r'\\begin\{' + re.escape(nested_env) + r'\}', ns):
                        depth += 1
                    if re.search(r'\\end\{' + re.escape(nested_env) + r'\}', ns):
                        depth -= 1
                        if depth == 0:
                            break
                    nested_lines.append(nl)
                nested_out = self._handle_env(nested_env, nested_rest, nested_lines)
                out.extend(('  ' + l if l else '') for l in nested_out)
                continue

            if s.startswith('\\item'):
                counter += 1
                item_rest = s[5:].strip()
                item_rest = re.sub(r'^\[([^\]]*)\]', r'(\1) ', item_rest)
                item_text = inline(item_rest)
                # Collect continuation lines (until next \item / \begin / blank)
                i += 1
                while i < len(lines):
                    ns = self._s(lines[i])
                    if not ns:
                        break
                    if ns.startswith('%'):
                        i += 1
                        continue
                    if ns.startswith('\\item') or re.match(r'\\(?:begin|end)\{', ns):
                        break
                    item_text += ' ' + inline(ns)
                    i += 1
                prefix = f'{counter}. ' if is_ordered else '- '
                out.append(f'{prefix}{item_text.strip()}')
                continue

            i += 1  # pre-\item line, skip

        out.append('')
        return out

    def _equation(self, opt: str, lines: list[str]) -> list[str]:
        math_lines = [
            self._s(l) for l in lines
            if not re.match(r'\s*\\label\{', l) and self._s(l)
        ]
        math = '\n'.join(math_lines).strip()
        return (['', f'$$\n{math}\n$$', ''] if math else [])

    def _align(self, opt: str, lines: list[str]) -> list[str]:
        math_lines = [
            l.rstrip() for l in lines
            if not re.match(r'\s*\\label\{', l)
        ]
        math = '\n'.join(math_lines).strip()
        return (['', f'$$\n\\begin{{aligned}}\n{math}\n\\end{{aligned}}\n$$', ''] if math else [])

    def _lstlisting(self, opt: str, lines: list[str]) -> list[str]:
        lang_m = re.search(r'language=(\w+)', opt)
        lang = lang_m.group(1).lower() if lang_m else ''
        return ['', f'```{lang}'] + lines + ['```', '']

    def _verbatim(self, opt: str, lines: list[str]) -> list[str]:
        return ['', '```'] + lines + ['```', '']


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    tex_path = Path(sys.argv[1])
    md_path = Path(sys.argv[2]) if len(sys.argv) > 2 else tex_path.with_suffix('.md')

    tex = tex_path.read_text(encoding='utf-8')
    md = Converter().convert(tex)
    md_path.write_text(md, encoding='utf-8')

    # Figure count verification
    tex_figs = len(re.findall(r'\\includegraphics', tex))
    md_figs = len(re.findall(r'^!\[', md, re.MULTILINE))
    print(f"Written : {md_path}", file=sys.stderr)
    print(f"Figures : {tex_figs} in .tex, {md_figs} in .md", file=sys.stderr)

    if tex_figs != md_figs:
        tex_paths = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', tex)
        md_paths  = re.findall(r'^!\[[^\]]*\]\(([^)]+)\)', md, re.MULTILINE)
        missing = sorted(set(tex_paths) - set(md_paths))
        if missing:
            print(f"ERROR   : missing in .md: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Scan all docs/**/*.md for common markdown format issues."""
import os, re, sys
from collections import defaultdict

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')

def line_iter(p):
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, 1):
            yield i, line.rstrip('\n')

def check_file(p):
    issues = []
    stats = {'lines': 0, 'code_blocks': 0, 'fences': 0, 'tables': 0}

    # 1. Empty / tiny file
    try:
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        issues.append((1, 'read-error', str(e)))
        return stats, issues

    raw_lines = content.split('\n')
    stats['lines'] = len(raw_lines)

    if stats['lines'] <= 1:
        issues.append((1, 'empty-file', f'{stats["lines"]} lines'))
        return stats, issues

    # 2. Detect unclosed / odd-count code fences
    fences = [(i, l) for i, l in enumerate(raw_lines, 1) if re.match(r'^\s*```', l)]
    stats['fences'] = len(fences)
    if stats['fences'] % 2 != 0:
        issues.append((fences[-1][0], 'odd-fence', f'{stats["fences"]} fences (last at L{fences[-1][0]})'))

    # 3. Nested code blocks: a fence starting with 4+ spaces OR inside a list item
    #    (any fence preceded by a line ending in `:` and starting with list marker)
    in_list = False
    for i, line in enumerate(raw_lines, 1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if re.match(r'^[\-\*\+]\s', stripped) or re.match(r'^\d+\.\s', stripped):
            in_list = True
        elif stripped == '':
            pass
        else:
            in_list = False
        if re.match(r'^\s*```', line):
            # Inside a list item with 2+ space indent is "nested" and renders broken
            if indent >= 4 and i > 1 and re.match(r'^\s*[\-\*\+]\s', raw_lines[i-2] if i >= 2 else ''):
                issues.append((i, 'nested-fence', f'fence at indent={indent} inside list'))

    # 4. Escapes that don't need to be escaped inside a word:
    #    word\_word or word\*word (escape is only needed at start/end of emphasis)
    for i, line in enumerate(raw_lines, 1):
        for m in re.finditer(r'(?<=[A-Za-z0-9])\\_(?=[A-Za-z0-9])', line):
            issues.append((i, 'useless-escape', f'\\_{m.group()!r}'))
        for m in re.finditer(r'(?<=[A-Za-z0-9])\\\*(?=[A-Za-z0-9])', line):
            issues.append((i, 'useless-escape', f'\\*{m.group()!r}'))
        for m in re.finditer(r'(?<=[A-Za-z0-9])\\\[(?=[A-Za-z0-9])', line):
            issues.append((i, 'useless-escape', f'\\[{m.group()!r}'))
        for m in re.finditer(r'(?<=[A-Za-z0-9])\\\](?=[A-Za-z0-9])', line):
            issues.append((i, 'useless-escape', f'\\]{m.group()!r}'))
        # \####  – accidental escape of heading marker
        if re.match(r'^\s*\\#{1,6}\s', line):
            issues.append((i, 'escaped-heading', line.strip()[:40]))

    # 5. Fence with no language tag: ```{newline} immediately
    for i, line in enumerate(raw_lines, 1):
        if re.match(r'^```\s*$', line):
            stats['code_blocks'] += 1
            issues.append((i, 'fence-no-lang', '```'))

    # 6. Heading levels: detect ## then #### (skipping ###)
    prev_level = 0
    for i, line in enumerate(raw_lines, 1):
        m = re.match(r'^(#{1,6})\s', line)
        if m:
            lvl = len(m.group(1))
            if prev_level and lvl > prev_level + 1:
                issues.append((i, 'heading-skip',
                              f'jump from H{prev_level} to H{lvl}: {line.strip()[:40]}'))
            prev_level = lvl

    # 7. Table format: only flag mismatches when the separator line is
    # actually bracketed by real table rows on both sides.  A bare
    # "---|---|" between blank paragraphs (often used as a visual rule,
    # not a table) used to flag false-positives in 148 places.
    def is_table_row(ln):
        s = ln.rstrip()
        return s.startswith('|') and s.count('|') >= 2
    def is_separator(ln):
        return bool(re.match(r'^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$', ln))
    for i, line in enumerate(raw_lines, 1):
        if not is_separator(line):
            continue
        # Walk back for a real table row (skip blank lines)
        prev_cols = None
        for j in range(i-2, max(-1, i-6), -1):
            if raw_lines[j].strip() == '':
                continue
            if is_table_row(raw_lines[j]):
                prev_cols = raw_lines[j].count('|')
            break
        next_cols = None
        for j in range(i, min(len(raw_lines), i+4)):
            if raw_lines[j].strip() == '':
                continue
            if is_table_row(raw_lines[j]):
                next_cols = raw_lines[j].count('|')
            break
        if prev_cols is None and next_cols is None:
            continue  # separator is isolated — not a real table
        stats['tables'] += 1
        this_cols = line.count('|')
        if prev_cols is not None and prev_cols != this_cols:
            issues.append((i, 'table-col-mismatch',
                          f'separator has {this_cols} cols, row above has {prev_cols}'))
        if next_cols is not None and next_cols != this_cols:
            issues.append((i, 'table-col-mismatch',
                          f'separator has {this_cols} cols, row below has {next_cols}'))

    # 8. Triple-or-more blank lines
    blank_run = 0
    for i, line in enumerate(raw_lines, 1):
        if line.strip() == '':
            blank_run += 1
            if blank_run == 3:
                issues.append((i, 'triple-blank', '3+ consecutive blank lines'))
        else:
            blank_run = 0

    # 9. BOM / CRLF
    if content.startswith('\ufeff'):
        issues.append((1, 'bom', 'file starts with UTF-8 BOM'))
    if '\r\n' in content:
        issues.append((1, 'crlf', 'file uses CRLF line endings'))

    # 10. Front matter sanity (must start with --- if present)
    if raw_lines and raw_lines[0].strip() == '---':
        # Find closing
        end = None
        for j in range(1, min(len(raw_lines), 200)):
            if raw_lines[j].strip() == '---':
                end = j + 1
                break
        if end is None:
            issues.append((1, 'unclosed-frontmatter', 'starts with --- but no closing'))

    return stats, issues


# === main ===
total_files = 0
total_issues = 0
by_kind = defaultdict(int)
problem_files = []

for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.md'):
            continue
        p = os.path.join(dp, f)
        total_files += 1
        stats, issues = check_file(p)
        if issues:
            rel = os.path.relpath(p, ROOT)
            problem_files.append((rel, stats, issues))
            for _, kind, _ in issues:
                by_kind[kind] += 1
            total_issues += len(issues)

print(f'=== SUMMARY ===')
print(f'Scanned:   {total_files} markdown files')
print(f'Files w/ issues: {len(problem_files)}')
print(f'Total issues:    {total_issues}')
print()
print(f'=== Issues by kind ===')
for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
    print(f'  {k:30s} {v:5d}')
print()
print(f'=== Files with issues (sorted by # issues desc) ===')
problem_files.sort(key=lambda x: -len(x[2]))
for rel, stats, issues in problem_files[:80]:
    print(f'\n[{len(issues):3d} issues, {stats["lines"]:5d} lines] {rel}')
    for ln, kind, msg in issues[:8]:
        print(f'    L{ln:4d}  {kind:24s}  {msg}')
    if len(issues) > 8:
        print(f'    ... and {len(issues) - 8} more')

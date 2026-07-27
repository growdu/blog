#!/usr/bin/env python3
"""Add title front matter to markdown files lacking one.

Extracts title from first H1 heading; falls back to filename/dirname.
Runs in CI before Hugo build so the repo stays clean (no manual metadata).
"""
import os
import re
import sys


def extract_h1_title(content):
    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else None


def fallback_title(filepath):
    basename = os.path.splitext(os.path.basename(filepath))[0]
    if basename == 'index':
        return os.path.basename(os.path.dirname(filepath))
    return basename


def split_front_matter(content):
    """Return (fm_text, body). fm_text is '' for empty FM, None if absent."""
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if m:
        return m.group(1), content[m.end():]
    m = re.match(r'^---\r?\n---\r?\n', content)
    if m:
        return '', content[m.end():]
    return None, content


def has_title(fm_text):
    return bool(re.search(r'^title\s*:', fm_text, re.MULTILINE))


def yaml_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')


def process(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    fm_text, body = split_front_matter(content)
    if fm_text is not None and has_title(fm_text):
        return False

    source = body if fm_text is not None else content
    title = extract_h1_title(source) or fallback_title(filepath)

    line = f'title: "{yaml_escape(title)}"'
    new_fm = line if not fm_text else line + '\n' + fm_text
    result = f'---\n{new_fm}\n---\n{body if fm_text is not None else content}'

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(result)
    return True


def main():
    docs_dir = sys.argv[1] if len(sys.argv) > 1 else 'docs'
    count = 0
    for root, _, files in os.walk(docs_dir):
        for fn in files:
            if fn.endswith('.md') and fn != '_index.md':
                fp = os.path.join(root, fn)
                try:
                    if process(fp):
                        count += 1
                except Exception as e:
                    print(f'ERROR {fp}: {e}', file=sys.stderr)
    print(f'Added titles to {count} files')


if __name__ == '__main__':
    main()

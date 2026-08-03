#!/usr/bin/env python3
"""Strip ``text`` from ``\\`\\`\\`text`` fences so fences never carry the
``text`` language tag.

Source rule: A previous auto-fix pass (``fix-markdown.py``) replaced every
bare ``\\`\\`\\``` closing fence with ``\\`\\`\\`text``. That injection is
wrong: ``text`` is not a meaningful language hint and it produces
non-standard markdown. This script restores every such fence to
``\\`\\`\\```.
"""
import os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs')
FENCE_RE = re.compile(r'^(\s*)```text\s*$', re.MULTILINE)

files_changed = 0
total_replacements = 0
for dp, _, fn in os.walk(ROOT):
    for fname in fn:
        if not fname.endswith('.md'):
            continue
        path = os.path.join(dp, fname)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            original = f.read()
        if '```text' not in original:
            continue
        new, n = FENCE_RE.subn(lambda m: f'{m.group(1)}```', original)
        if new != original:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new)
            files_changed += 1
            total_replacements += n

print(f'Files changed:        {files_changed}')
print(f'```text -> ``` rows:  {total_replacements}')

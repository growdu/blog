#!/usr/bin/env python3
"""Remove the default menu from matery theme's _config.yml so the menu
defined in _config.matery.yml is the sole source. Hexo deepmerges the
theme config with _config.<theme>.yml at the key level, which causes
duplicate (Chinese + English) navigation items otherwise."""
import re, sys

path = 'themes/matery/_config.yml'
try:
    with open(path, encoding='utf-8') as f:
        content = f.read()
except FileNotFoundError:
    print(f'{path} not found, skipping', file=sys.stderr)
    sys.exit(0)

new_content = re.sub(
    r'^menu:\s*\n(?:[ \t]+.*\n)*',
    '',
    content,
    count=1,
    flags=re.MULTILINE,
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Patched matery theme: removed default menu')

#!/usr/bin/env python3
"""Prepare the matery theme for use with this blog:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Ensure menu links use url_for() so the /blog/ root prefix is applied
   (GitHub Pages project site needs /blog/ on every internal link).
"""
import os, re, sys

path = 'themes/matery/_config.yml'
try:
    with open(path, encoding='utf-8') as f:
        content = f.read()
except FileNotFoundError:
    print(f'{path} not found, skipping', file=sys.stderr)
    sys.exit(0)

# 1. Remove the default menu section
new_content = re.sub(
    r'^menu:\s*\n(?:[ \t]+.*\n)*',
    '',
    content,
    count=1,
    flags=re.MULTILINE,
)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Removed default menu from theme config')

# 2. Ensure menu links use url_for in all EJS templates
layout_dir = 'themes/matery/layout'
patched = 0
for root, dirs, files in os.walk(layout_dir):
    for fname in files:
        if not fname.endswith('.ejs'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, encoding='utf-8') as fh:
            c = fh.read()
        orig = c
        # href="<%= theme.menu[key] %>" -> href="<%- url_for(theme.menu[key]) %>"
        c = re.sub(
            r'href="<%=\s*(theme\.menu\[[^\]]+\])\s*%>"',
            r'href="<%- url_for(\1) %>"',
            c,
        )
        # href="<%- theme.menu[key] %>" (not already url_for) -> wrap in url_for
        c = re.sub(
            r'href="<%-\s*(theme\.menu\[[^\]]+\])\s*%>"',
            r'href="<%- url_for(\1) %>"',
            c,
        )
        if c != orig:
            with open(fpath, 'w', encoding='utf-8') as fh:
                fh.write(c)
            patched += 1
            print(f'  url_for: {os.path.relpath(fpath, "themes/matery")}')
print(f'Patched menu links in {patched} template(s)')

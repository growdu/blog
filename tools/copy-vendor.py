#!/usr/bin/env python3
"""Copy vendor assets from node_modules to source/lib/.

Handles:
1. CDN-localized files (from tools/cdn-manifest.json)
2. Prism/Mermaid/Gitalk assets (fixed)
3. Font Awesome webfonts (referenced by css/all.min.css)

Run AFTER sync-hexo.py (which creates source/).
"""
import os, json, shutil, sys

LIB = 'source/lib'
MANIFEST = 'tools/cdn-manifest.json'

# Fixed vendor assets
FIXED = [
    ('node_modules/prismjs/themes/prism-tomorrow.min.css', f'{LIB}/prism/prism-tomorrow.min.css'),
    ('node_modules/prismjs/components/prism-core.min.js', f'{LIB}/prism/prism-core.min.js'),
    ('node_modules/prismjs/plugins/autoloader/prism-autoloader.min.js', f'{LIB}/prism/prism-autoloader.min.js'),
    ('node_modules/mermaid/dist/mermaid.min.js', f'{LIB}/mermaid/mermaid.min.js'),
    ('node_modules/gitalk/dist/gitalk.css', f'{LIB}/gitalk/gitalk.css'),
    ('node_modules/gitalk/dist/gitalk.min.js', f'{LIB}/gitalk/gitalk.min.js'),
]

# Directories to copy (fontawesome webfonts referenced by all.min.css)
FIXED_DIRS = [
    ('node_modules/@fortawesome/fontawesome-free/webfonts', f'{LIB}/fontawesome-free/webfonts'),
]

copies = list(FIXED)

if os.path.isfile(MANIFEST):
    with open(MANIFEST, encoding='utf-8') as f:
        copies.extend(json.load(f))
    print(f'Loaded CDN manifest')

ok = skip = 0
for src, dst in copies:
    if os.path.isfile(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        ok += 1
    else:
        print(f'WARNING: {src} not found')
        skip += 1

for src_dir, dst_dir in FIXED_DIRS:
    if os.path.isdir(src_dir):
        shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
        ok += len(os.listdir(dst_dir))
    else:
        print(f'WARNING: {src_dir} not found')

print(f'Copied {ok} files, {skip} missing')

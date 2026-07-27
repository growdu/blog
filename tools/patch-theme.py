#!/usr/bin/env python3
"""Prepare the matery theme:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Inject a category-overview section into the homepage so visitors can
   see and navigate to major categories without scrolling through dozens
   of pages of post cards.
"""
import os, re, sys

theme_dir = 'themes/matery'

# --- 1. Remove default menu ---
path = os.path.join(theme_dir, '_config.yml')
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
print('Removed default menu from theme config')

# --- 2. Inject category overview into homepage ---
category_ejs = """<% if (site.categories && site.categories.length) { %>
<div class="container" style="margin-top: 20px;">
  <div class="card" style="padding: 16px 20px;">
    <div style="font-size: 1.3rem; font-weight: bold; margin-bottom: 12px;">文章分类</div>
    <div class="row" style="margin-bottom: 0;">
      <% site.categories.each(function(cat){ %>
        <div class="col s6 m4 l3" style="margin-bottom: 6px;">
          <a href="<%- url_for(cat.path) %>" class="chip waves-effect waves-light">
            <%= cat.name %><span style="margin-left: 4px; color: #999;"><%= cat.posts.length %></span>
          </a>
        </div>
      <% }) %>
    </div>
  </div>
</div>
<% } %>"""

partial_dir = os.path.join(theme_dir, 'layout', '_partial')
os.makedirs(partial_dir, exist_ok=True)
with open(os.path.join(partial_dir, 'category-overview.ejs'), 'w', encoding='utf-8') as f:
    f.write(category_ejs)
print('Created category-overview partial')

# Inject the partial include into index.ejs after the first partial call
# (typically the hero/banner section), so categories appear above the post list
index_path = os.path.join(theme_dir, 'layout', 'index.ejs')
if os.path.isfile(index_path):
    with open(index_path, encoding='utf-8') as f:
        idx = f.read()
    if 'category-overview' not in idx:
        lines = idx.split('\n')
        new_lines = []
        injected = False
        for line in lines:
            new_lines.append(line)
            if not injected and 'partial(' in line:
                new_lines.append('<%- partial("_partial/category-overview") %>')
                injected = True
        if not injected:
            new_lines.insert(0, '<%- partial("_partial/category-overview") %>')
        with open(index_path, 'w', encoding='utf-8') as f:
           f.write('\n'.join(new_lines))
        print('Injected category-overview into index.ejs')
    else:
        print('category-overview already in index.ejs')
else:
    print('index.ejs not found, skipping injection')

# --- 3. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams ---
inject_css = """<link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet"/>
<style>
pre[class*="language-"]{background:#282c34!important;border-radius:8px;padding:16px;font-size:14px;margin:16px 0;overflow-x:auto}
code[class*="language-"]{font-family:Consolas,Monaco,'Source Code Pro',monospace}
.mermaid{text-align:center;margin:16px 0}
</style>"""

inject_js = """<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-core.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>if(window.mermaid){mermaid.initialize({startOnLoad:false,theme:'default'});mermaid.run();}</script>"""

for root, dirs, files in os.walk(os.path.join(theme_dir, 'layout')):
    for fname in files:
        if not fname.endswith('.ejs'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, encoding='utf-8') as f:
            c = f.read()
        changed = False
        if '</head>' in c and 'prism-tomorrow' not in c:
            c = c.replace('</head>', inject_css + '\n</head>', 1)
            changed = True
        if '</body>' in c and 'mermaid@10' not in c:
            c = c.replace('</body>', inject_js + '\n</body>', 1)
            changed = True
        if changed:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(c)
            print(f'Injected CSS/JS into {os.path.relpath(fpath, theme_dir)}')

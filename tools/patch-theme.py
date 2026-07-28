#!/usr/bin/env python3
"""Prepare the matery theme:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Inject a featured-posts section into the homepage.
3. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams.
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

# --- 2. Inject featured posts section into homepage ---
featured_ejs = """<% var featured = site.posts.sort('-date').limit(5); %>
<% if (featured.length) { %>
<div class="container" style="margin-top: 20px;">
  <h4 style="margin-bottom: 15px;">推荐文章</h4>
  <div class="row">
    <% featured.each(function(post){ %>
      <div class="col s12 m6 l4">
        <a href="<%- url_for(post.path) %>" style="text-decoration:none;color:inherit">
          <div class="card hoverable">
            <div class="card-content">
              <span class="card-title" style="font-size:1.05rem;line-height:1.4"><%= post.title %></span>
              <p style="color:#999;font-size:0.85rem;margin-top:8px">
                <%= date(post.date, 'YYYY-MM-DD') %>
                <% if (post.categories && post.categories.length) { %>
                  <span style="margin-left:8px"><%= post.categories.first().name %></span>
                <% } %>
              </p>
            </div>
          </div>
        </a>
      </div>
    <% }) %>
  </div>
</div>
<% } %>"""

partial_dir = os.path.join(theme_dir, 'layout', '_partial')
os.makedirs(partial_dir, exist_ok=True)
with open(os.path.join(partial_dir, 'featured-posts.ejs'), 'w', encoding='utf-8') as f:
    f.write(featured_ejs)
print('Created featured-posts partial')

index_path = os.path.join(theme_dir, 'layout', 'index.ejs')
if os.path.isfile(index_path):
    with open(index_path, encoding='utf-8') as f:
        idx = f.read()
    if 'featured-posts' not in idx:
        lines = idx.split('\n')
        new_lines = []
        injected = False
        for line in lines:
            new_lines.append(line)
            if not injected and 'partial(' in line:
                new_lines.append('<%- partial("_partial/featured-posts") %>')
                injected = True
        if not injected:
            new_lines.insert(0, '<%- partial("_partial/featured-posts") %>')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print('Injected featured-posts into index.ejs')

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

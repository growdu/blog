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

#!/usr/bin/env python3
"""Prepare the matery theme:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams.
3. Inject Gitalk comments into the post-detail gitalk block.
4. Inject custom blog styling (colors, typography, effects).
5. Inject homepage statistics + category navigation.
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

# --- 2. Inject prism.js CSS + Mermaid.js ---
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

# --- 3. Inject Gitalk comments ---
partial_dir = os.path.join(theme_dir, 'layout', '_partial')
os.makedirs(partial_dir, exist_ok=True)

gitalk_card_ejs = """<% if (theme.gitalk && theme.gitalk.enable) { %>
<%
  var hashCode = function(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) {
      h = ((h << 5) - h) + s.charCodeAt(i); h |= 0;
    }
    return 'p' + Math.abs(h);
  };
  var gitalkId = hashCode(page.path);
%>
<div class="card" data-aos="fade-up">
  <div class="card-content">
    <% if (theme.gitalk.clientID && theme.gitalk.clientID.length > 0) { %>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.css">
    <div id="gitalk-container" data-gitalk-id="<%= gitalkId %>" data-gitalk-title="<%= page.title %>"></div>
    <script src="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.min.js"></script>
    <script>
      var gitalk = new Gitalk({
        clientID: '<%= theme.gitalk.clientID %>',
        clientSecret: '<%= theme.gitalk.clientSecret %>',
        repo: '<%= theme.gitalk.repo %>',
        owner: '<%= theme.gitalk.owner %>',
        admin: ['<%= theme.gitalk.owner %>'],
        id: '<%= gitalkId %>',
        language: 'zh-CN',
        distractionFreeMode: false,
        createIssueManually: false,
        labels: ['Gitalk', 'Comment'],
        perPage: 10
      });
      gitalk.render('gitalk-container');
    </script>
    <% } else { %>
    <div style="text-align: center; padding: 30px 20px; color: #999;">
      <i class="fas fa-comments" style="font-size: 28px;"></i>
      <p style="margin-top: 10px; font-size: 14px;">评论系统待配置 GitHub OAuth App</p>
    </div>
    <% } %>
  </div>
</div>
<% } %>"""

with open(os.path.join(partial_dir, 'gitalk-card.ejs'), 'w', encoding='utf-8') as f:
    f.write(gitalk_card_ejs)
print('Created gitalk-card.ejs')

post_detail = os.path.join(theme_dir, 'layout', '_partial', 'post-detail.ejs')
if os.path.isfile(post_detail):
    with open(post_detail, encoding='utf-8') as f:
        pd = f.read()
    original = pd
    for pat in ['<%- partial("_partial/gitalk") %>', "<%- partial('_partial/gitalk') %>"]:
        pd = pd.replace(pat, '')
    if 'gitalk-card' not in pd:
        new_pd, count = re.subn(
            r"(<%\s*if\s*\(theme\.gitalk\s*&&\s*theme\.gitalk\.enable\)\s*\{\s*%>)(.*?)(<%\s*\}\s*%>)",
            r"\1\n        <%- partial('_partial/gitalk-card') %>\n    \3",
            pd,
            flags=re.DOTALL,
        )
        if count > 0:
            pd = new_pd
            print(f'Injected gitalk-card into gitalk if-block')
        else:
            lines = pd.split('\n')
            for i, line in enumerate(lines):
                if 'prev-next' in line:
                    lines.insert(i, "    <%- partial('_partial/gitalk-card') %>")
                    pd = '\n'.join(lines)
                    print('Injected gitalk-card before prev-next (fallback)')
                    break
    else:
        print('gitalk-card already present')
    if pd != original:
        with open(post_detail, 'w', encoding='utf-8') as f:
            f.write(pd)
        print('Saved post-detail.ejs')
else:
    print('WARNING: post-detail.ejs not found')

# --- 4. Custom blog styling (subtle, keep original theme colors) ---
custom_css = """<style id="custom-blog-style">
/* Article typography */
#articleContent{font-size:16px;line-height:1.85}
#articleContent p{margin-bottom:1.3em}
#articleContent h2{margin-top:1.8em;margin-bottom:.8em;padding-bottom:.3em;border-bottom:2px solid #e0e0e0;font-weight:700}
#articleContent h3{margin-top:1.5em;margin-bottom:.6em;font-weight:600}
#articleContent blockquote{border-left:4px solid #009688;background:#f5f5f5;padding:12px 20px;margin:16px 0;border-radius:0 8px 8px 0;color:#666}
#articleContent code{background:#f5f5f5;padding:2px 6px;border-radius:4px;font-size:.9em}
#articleContent table{width:100%;border-collapse:collapse;margin:16px 0;display:block;overflow-x:auto}
#articleContent th,#articleContent td{border:1px solid #e0e0e0;padding:8px 12px;text-align:left}
#articleContent th{background:#f5f5f5;font-weight:600}
#articleContent img{border-radius:8px;max-width:100%}
/* Reading progress bar */
.reading-progress{position:fixed;top:0;left:0;height:3px;width:0;background:#009688;z-index:99999;transition:width .1s ease}
/* Card hover */
.card{transition:transform .25s ease,box-shadow .25s ease}
.card:hover{transform:translateY(-4px);box-shadow:0 8px 20px rgba(0,0,0,.1)}
/* Scrollbar */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:#f5f5f5}
::-webkit-scrollbar-thumb{background:#bbb;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#999}
/* Statistics bar (top, compact) */
.stats-bar{display:flex;justify-content:center;gap:48px;padding:14px 0;background:#fff;border-bottom:1px solid #f0f0f0}
.stats-bar .stat-item{text-align:center}
.stats-bar .stat-num{font-size:26px;font-weight:800;color:#333}
.stats-bar .stat-label{font-size:13px;color:#999;margin-top:2px}
/* Category sidebar (left, fixed, desktop only) */
.cat-sidebar{position:fixed;left:12px;top:80px;width:180px;max-height:78vh;overflow-y:auto;z-index:100;background:#fff;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.06);padding:8px 0}
.cat-sidebar .cat-title{font-size:14px;font-weight:700;padding:6px 14px 8px;color:#333;border-bottom:1px solid #f0f0f0;margin-bottom:4px}
.cat-sidebar a{display:block;padding:5px 14px;font-size:13px;color:#666;transition:all .15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cat-sidebar a:hover{background:#f5f5f5;color:#009688;padding-left:18px}
.cat-sidebar .cat-count{float:right;color:#bbb;font-size:12px}
@media(max-width:1400px){.cat-sidebar{display:none}}
</style>"""

custom_js = """<script id="custom-blog-script">
(function(){
  var bar=document.createElement('div');bar.className='reading-progress';document.body.appendChild(bar);
  function updateBar(){var st=window.scrollY,dh=document.documentElement.scrollHeight-window.innerHeight;bar.style.width=(dh>0?(st/dh*100):0)+'%';}
  window.addEventListener('scroll',updateBar,{passive:true});updateBar();
})();
</script>"""

for root, dirs, files in os.walk(os.path.join(theme_dir, 'layout')):
    for fname in files:
        if not fname.endswith('.ejs'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, encoding='utf-8') as f:
            c = f.read()
        changed = False
        if '</head>' in c and 'custom-blog-style' not in c:
            c = c.replace('</head>', custom_css + '\n</head>', 1)
            changed = True
        if '</body>' in c and 'custom-blog-script' not in c:
            c = c.replace('</body>', custom_js + '\n</body>', 1)
            changed = True
        if changed:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(c)
            print(f'Injected custom CSS/JS into {os.path.relpath(fpath, theme_dir)}')

# --- 5. Statistics bar (top of homepage) + category sidebar (fixed left) ---
# Compact statistics bar above main content (not inside article area)
index_path = os.path.join(theme_dir, 'layout', 'index.ejs')
if os.path.isfile(index_path):
    with open(index_path, encoding='utf-8') as f:
        idx = f.read()
    if 'stats-bar' not in idx:
        stats_ejs = """<% if (is_home() && page.current === 1) { %>
<div class="stats-bar">
    <div class="stat-item"><div class="stat-num"><%= site.posts.length %></div><div class="stat-label">文章</div></div>
    <div class="stat-item"><div class="stat-num"><%= site.categories.length %></div><div class="stat-label">分类</div></div>
    <div class="stat-item"><div class="stat-num"><%= site.tags.length %></div><div class="stat-label">标签</div></div>
</div>
<% } %>
"""
        idx = idx.replace('<main class="content">', stats_ejs + '<main class="content">', 1)
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(idx)
        print('Injected statistics bar into index.ejs (above content)')
    else:
        print('Statistics bar already in index.ejs')

# Fixed category sidebar on all pages (desktop only)
sidebar_ejs = """<% if (site.categories && site.categories.length) { %>
<div class="cat-sidebar">
  <div class="cat-title">分类导航</div>
  <% site.categories.each(function(category) { %>
  <a href="<%- url_for(category.path) %>"><%- category.name %><span class="cat-count"><%= category.posts.length %></span></a>
  <% }); %>
</div>
<% } %>
"""
sidebar_done = False
for root, dirs, files in os.walk(os.path.join(theme_dir, 'layout')):
    if sidebar_done:
        break
    for fname in files:
        if not fname.endswith('.ejs'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, encoding='utf-8') as f:
            c = f.read()
        if '</body>' in c and 'cat-sidebar' not in c:
            c = c.replace('</body>', sidebar_ejs + '\n</body>', 1)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(c)
            print(f'Injected category sidebar into {os.path.relpath(fpath, theme_dir)}')
            sidebar_done = True
            break
if not sidebar_done:
    print('WARNING: could not inject category sidebar')

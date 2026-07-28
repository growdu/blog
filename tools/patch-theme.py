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

# --- 4. Custom blog styling ---
custom_css = """<style id="custom-blog-style">
:root{--primary:#4f46e5;--primary-d:#4338ca;--primary-l:#6366f1;--accent:#0ea5e9;--text:#1e293b;--text-l:#64748b;--bg:#f8fafc}
.bg-color,.chip.bg-color{background-color:var(--primary)!important}
.btn.bg-color{background-color:var(--primary)!important}
.btn.bg-color:hover{background-color:var(--primary-d)!important}
a{color:var(--primary)}
a:hover{color:var(--primary-d)}
.header nav{background-color:var(--primary)!important}
/* Article typography */
#articleContent{font-size:16px;line-height:1.85;color:var(--text);letter-spacing:.015em}
#articleContent p{margin-bottom:1.3em}
#articleContent h2{margin-top:2em;margin-bottom:.8em;padding-bottom:.3em;border-bottom:2px solid #e2e8f0;font-weight:700}
#articleContent h3{margin-top:1.5em;margin-bottom:.6em;font-weight:600;color:var(--primary-d)}
#articleContent h4{margin-top:1.2em;font-weight:600}
#articleContent blockquote{border-left:4px solid var(--primary);background:#f1f5f9;padding:12px 20px;margin:16px 0;color:var(--text-l);border-radius:0 8px 8px 0}
#articleContent code{background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:.9em;color:var(--primary)}
#articleContent table{width:100%;border-collapse:collapse;margin:16px 0;display:block;overflow-x:auto}
#articleContent th,#articleContent td{border:1px solid #e2e8f0;padding:8px 12px;text-align:left;white-space:nowrap}
#articleContent th{background:var(--primary);color:#fff;font-weight:600}
#articleContent tr:nth-child(even){background:#f8fafc}
#articleContent img{border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.1);max-width:100%}
#articleContent ul,#articleContent ol{padding-left:1.8em;margin-bottom:1.2em}
#articleContent li{margin-bottom:.4em}
/* Reading progress bar */
.reading-progress{position:fixed;top:0;left:0;height:3px;width:0;background:linear-gradient(90deg,var(--primary),var(--accent));z-index:99999;transition:width .1s ease}
/* Card hover */
.card{transition:transform .25s ease,box-shadow .25s ease}
.card:hover{transform:translateY(-6px);box-shadow:0 12px 28px rgba(0,0,0,.12)}
/* Custom scrollbar */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:#f1f5f9}
::-webkit-scrollbar-thumb{background:var(--primary-l);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--primary)}
/* Section titles */
.section-title{text-align:center;margin:30px 0 20px}
.section-title h4{font-size:22px;font-weight:700;color:var(--text);display:inline-block;padding-bottom:8px;border-bottom:3px solid var(--primary)}
/* Statistics cards */
.stat-card{background:#fff;border-radius:12px;padding:24px 12px;text-align:center;box-shadow:0 2px 12px rgba(0,0,0,.08);transition:transform .2s}
.stat-card:hover{transform:translateY(-4px);box-shadow:0 8px 20px rgba(79,70,229,.15)}
.stat-card i{color:var(--primary)}
.stat-card h3{margin:8px 0 4px;font-size:32px;font-weight:800;color:var(--text)}
.stat-card p{margin:0;color:var(--text-l);font-size:14px}
/* Category cards */
.category-card{display:flex;flex-direction:column;align-items:center;padding:16px 8px;margin-bottom:12px;background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.06);transition:all .2s;color:var(--text);border:1px solid #e2e8f0}
.category-card:hover{background:var(--primary);color:#fff;transform:translateY(-3px);box-shadow:0 6px 16px rgba(79,70,229,.25);border-color:var(--primary)}
.category-card i{font-size:22px;margin-bottom:6px;color:var(--primary)}
.category-card:hover i{color:#fff}
.category-card .cat-name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.category-card small{color:var(--text-l);margin-top:2px;font-size:12px}
.category-card:hover small{color:rgba(255,255,255,.8)}
/* Hero overlay */
.bg-cover .container{position:relative;z-index:2}
.bg-cover::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:linear-gradient(135deg,rgba(79,70,229,.45) 0%,rgba(14,165,233,.25) 100%);z-index:1}
/* Nav shadow on scroll */
.nav-fixed{box-shadow:0 2px 12px rgba(0,0,0,.15)!important}
/* Footer */
footer{background:var(--text)!important}
footer a{color:var(--primary-l)!important}
/* Tag chips */
.chip{border-radius:6px!important;font-size:13px!important}
/* Article card title */
.card-title{font-weight:600!important}
</style>"""

custom_js = """<script id="custom-blog-script">
(function(){
  // Reading progress bar
  var bar=document.createElement('div');bar.className='reading-progress';document.body.appendChild(bar);
  function updateBar(){var st=window.scrollY,dh=document.documentElement.scrollHeight-window.innerHeight;bar.style.width=(dh>0?(st/dh*100):0)+'%';}
  window.addEventListener('scroll',updateBar,{passive:true});updateBar();
  // Nav shadow on scroll
  var nav=document.querySelector('header nav')||document.querySelector('.nav-wrapper');
  window.addEventListener('scroll',function(){if(nav){if(window.scrollY>50)nav.classList.add('nav-fixed');else nav.classList.remove('nav-fixed');}},{passive:true});
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

# --- 5. Homepage statistics + category navigation ---
index_path = os.path.join(theme_dir, 'layout', 'index.ejs')
if os.path.isfile(index_path):
    with open(index_path, encoding='utf-8') as f:
        idx = f.read()
    if 'stat-card' not in idx:
        stats_ejs = """
<% if (is_home() && page.current === 1) { %>
<div class="container" style="margin-top: 24px; margin-bottom: 10px;">
    <div class="row" style="margin-bottom: 0;">
        <div class="col s4">
            <div class="stat-card"><i class="fas fa-file-alt fa-2x"></i><h3><%= site.posts.length %></h3><p>篇文章</p></div>
        </div>
        <div class="col s4">
            <div class="stat-card"><i class="fas fa-folder fa-2x"></i><h3><%= site.categories.length %></h3><p>个分类</p></div>
        </div>
        <div class="col s4">
            <div class="stat-card"><i class="fas fa-tags fa-2x"></i><h3><%= site.tags.length %></h3><p>个标签</p></div>
        </div>
    </div>
</div>
<div class="container" style="margin-bottom: 20px;">
    <div class="section-title"><h4>分类导航</h4></div>
    <div class="row">
        <% site.categories.each(function(category) { %>
        <div class="col s6 m4 l3">
            <a href="<%- url_for(category.path) %>" class="category-card">
                <i class="fas fa-folder"></i>
                <span class="cat-name"><%= category.name %></span>
                <small><%= category.posts.length %> 篇</small>
            </a>
        </div>
        <% }); %>
    </div>
</div>
<% } %>
"""
        idx = idx.replace(
            '<article id="articles"',
            stats_ejs + '\n    <article id="articles"',
            1,
        )
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(idx)
        print('Injected statistics + category navigation into index.ejs')
    else:
        print('Statistics already present in index.ejs')
else:
    print('WARNING: index.ejs not found')

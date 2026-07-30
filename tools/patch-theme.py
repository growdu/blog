#!/usr/bin/env python3
"""Prepare the matery theme:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams.
3. Inject Gitalk comments into the post-detail gitalk block.
4. Inject custom blog styling (colors, typography, effects).
5. Inject homepage statistics + category navigation.
"""
import os, re, shutil, sys

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

# --- 1.5. Replace default fox logo with custom image ---
# The header.ejs partial in the theme renders `theme.logo` (default
# `/medias/logo.png`, the fox).  _config.matery.yml overrides it to
# `/medias/logo.jpg`, so we just need to publish the new image under
# that path inside the theme's source tree.
src_logo = '1.jpg'
dst_logo = os.path.join(theme_dir, 'source', 'medias', 'logo.jpg')
if os.path.isfile(src_logo):
    os.makedirs(os.path.dirname(dst_logo), exist_ok=True)
    shutil.copy2(src_logo, dst_logo)
    print(f'Copied {src_logo} -> {os.path.relpath(dst_logo, theme_dir)}')
else:
    print(f'WARNING: {src_logo} not found, logo not replaced', file=sys.stderr)

# --- 1.6. Publish computer-themed cover/banner/feature images ---
# The default matery theme ships nature photos (pegasi, snow mountains,
# deserts, ...).  We replace them with computer-industry images generated
# into ./theme-assets/ so the hero, banner rotation and post thumbnails
# fit the database-kernel focus of the blog.
THEME_ASSETS_DIR = 'theme-assets'
MEDIAS = os.path.join(theme_dir, 'source', 'medias')
if os.path.isdir(THEME_ASSETS_DIR):
    os.makedirs(MEDIAS, exist_ok=True)
    n_copied = 0
    for root, _, files in os.walk(THEME_ASSETS_DIR):
        for f in files:
            src = os.path.join(root, f)
            rel = os.path.relpath(src, THEME_ASSETS_DIR)
            dst = os.path.join(MEDIAS, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            n_copied += 1
    print(f'Published {n_copied} theme assets into {os.path.relpath(MEDIAS, theme_dir)}')
else:
    print(f'WARNING: {THEME_ASSETS_DIR} not found, theme assets not published', file=sys.stderr)

# --- 2. Inject prism.js CSS + Mermaid.js ---
inject_css = """<meta property="og:title" content="<%= page.title || config.title %>">
<meta name="theme-color" content="#009688">
<link rel="preconnect" href="https://api.counterapi.dev">
<link rel="dns-prefetch" href="https://api.counterapi.dev">
<link rel="preconnect" href="https://busuanzi.ibruce.info">
<link rel="dns-prefetch" href="https://busuanzi.ibruce.info">
<link rel="preconnect" href="https://api.github.com">
<link rel="dns-prefetch" href="https://api.github.com">
<meta property="og:site_name" content="<%= config.title %>">
<meta property="og:type" content="<%= page.layout === 'post' ? 'article' : 'website' %>">
<meta property="og:url" content="<%- config.url %><%- url_for(page.path) %>">
<meta property="og:locale" content="zh_CN">
<meta property="og:description" content="<%= (page.description || config.description || '').replace(/"/g, '&quot;') %>">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="<%= page.title || config.title %>">
<meta name="twitter:description" content="<%= (page.description || config.description || '').replace(/"/g, '&quot;') %>">
<% if (page.layout === 'post') { %>
<meta property="article:author" content="<%= config.author %>">
<meta property="article:published_time" content="<%- date(page.date, 'YYYY-MM-DD') %>">
<% if (page.categories && page.categories.data && page.categories.data.length > 0) { %>
<meta property="article:section" content="<%= page.categories.data[0].name %>">
<% } %>
<% if (page.tags && page.tags.data) { %>
<% page.tags.data.forEach(function(tag) { %>
<meta property="article:tag" content="<%= tag.name %>">
<% }); %>
<% } %>
<% } %>
<meta property="og:image" content="<%- config.url %><%- url_for('/medias/featureimages/0.jpg') %>">
<meta name="twitter:image" content="<%- config.url %><%- url_for('/medias/featureimages/0.jpg') %>">
<link rel="manifest" href="/blog/manifest.json">
<link rel="icon" type="image/svg+xml" href="/blog/favicon.svg">
<link rel="canonical" href="<%- config.url %><%- url_for(page.path) %>">
<% if (page.layout === 'post') { %>
<% var _cat = (page.categories && page.categories.data && page.categories.data.length > 0) ? page.categories.data[0].name : ''; %>
<% var _tags = (page.tags && page.tags.data) ? page.tags.data.map(function(t) { return t.name; }).join(', ') : ''; %>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BlogPosting","headline":"<%= page.title %>","datePublished":"<%- date(page.date, 'YYYY-MM-DD') %>","author":{"@type":"Person","name":"<%= config.author %>"},"publisher":{"@type":"Organization","name":"<%= config.title %>"},"mainEntityOfPage":{"@type":"WebPage","@id":"<%- config.url %><%- url_for(page.path) %>"}<% if (_cat) { %>,"articleSection":"<%= _cat %>"<% } %><% if (_tags) { %>,"keywords":"<%= _tags %>"<% } %>}</script>
<% } else { %>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"<%= config.title %>","url":"<%- config.url %>"}</script>
<% } %>
<link href="/blog/lib/prism/prism-tomorrow.min.css" rel="stylesheet"/>
<style>
pre[class*="language-"]{background:#263238!important;border-radius:6px;padding:14px 16px;font-size:14px;margin:16px 0;overflow-x:auto;line-height:1.55}
code[class*="language-"]{background:transparent!important;padding:0;font-family:Consolas,Monaco,'Source Code Pro',monospace;font-size:14px}
:not(pre)>code[class*="language-"]{background:#f5f5f5!important;padding:2px 6px;border-radius:4px}
.mermaid{text-align:center;margin:16px 0}
</style>"""

inject_js = """<script src="/blog/lib/prism/prism-core.min.js"></script>
<script src="/blog/lib/prism/prism-autoloader.min.js"></script>
<script>if(window.Prism&&Prism.plugins&&Prism.plugins.autoloader){Prism.plugins.autoloader.languages_path='/blog/lib/prism/components/';}</script>
<script src="/blog/lib/mermaid/mermaid.min.js"></script>
<script>if(window.mermaid){mermaid.initialize({startOnLoad:false,theme:'default'});mermaid.run();}</script>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/blog/sw.js').catch(function(){})}</script>"""

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
        if '</body>' in c and '/blog/lib/prism/prism-core.min.js' not in c:
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
    <link rel="stylesheet" href="/blog/lib/gitalk/gitalk.css">
    <div id="gitalk-container" data-gitalk-id="<%= gitalkId %>" data-gitalk-title="<%= page.title %>"></div>
    <script src="/blog/lib/gitalk/gitalk.min.js"></script>
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
# --- 3.5. Related posts by category ---
related_ejs = """<%
  var related = [];
  var pageCats = {};
  if (page.categories && page.categories.data) {
    page.categories.data.forEach(function(c) { pageCats[c.name] = true; });
  }
  if (Object.keys(pageCats).length > 0) {
    site.posts.data.forEach(function(p) {
      if (p.path === page.path) return;
      if (p.categories && p.categories.data) {
        for (var i = 0; i < p.categories.data.length; i++) {
          if (pageCats[p.categories.data[i].name]) { related.push(p); break; }
        }
      }
    });
    related.sort(function(a, b) { return new Date(b.date) - new Date(a.date); });
    related = related.slice(0, 6);
  }
%>
<% if (related.length > 0) { %>
<div class="card related-posts-card" data-aos="fade-up">
  <div class="card-content">
    <div class="related-posts-title"><i class="fas fa-link"></i> 相关文章</div>
    <div class="related-posts-grid">
      <% related.forEach(function(post) { %>
      <a href="<%- url_for(post.path) %>" class="related-post-item">
        <span class="related-post-name"><%= post.title %></span>
        <span class="related-post-date"><%- date(post.date, 'YYYY-MM-DD') %></span>
      </a>
      <% }); %>
    </div>
  </div>
</div>
<% } %>"""

with open(os.path.join(partial_dir, 'related-posts.ejs'), 'w', encoding='utf-8') as f:
    f.write(related_ejs)
print('Created related-posts.ejs')

post_detail = os.path.join(theme_dir, 'layout', '_partial', 'post-detail.ejs')
if os.path.isfile(post_detail):
    with open(post_detail, encoding='utf-8') as f:
        pd = f.read()
    if 'related-posts' not in pd:
        pd = pd.replace(
            "partial('_partial/gitalk-card')",
            "partial('_partial/related-posts') %>\n    <%- partial('_partial/gitalk-card')",
            1,
        )
        with open(post_detail, 'w', encoding='utf-8') as f:
            f.write(pd)
        print('Injected related-posts before gitalk-card')
    else:
        print('related-posts already present')
else:
    print('WARNING: post-detail.ejs not found for related-posts')
# --- 4. Custom blog styling (subtle, keep original theme colors) ---
custom_css = """<style id="custom-blog-style">
/* Article typography */
#articleContent{font-size:16px;line-height:1.85}
#articleContent p{margin-bottom:1.3em}
#articleContent h2{margin-top:1.8em;margin-bottom:.8em;padding-bottom:.3em;border-bottom:2px solid #e0e0e0;font-weight:700}
#articleContent h3{margin-top:1.5em;margin-bottom:.6em;font-weight:600}
#articleContent blockquote{border-left:4px solid #009688;background:#f5f5f5;padding:12px 20px;margin:16px 0;border-radius:0 8px 8px 0;color:#666}
#articleContent :not(pre)>code{background:#f5f5f5;padding:2px 6px;border-radius:4px;font-size:.9em}
#articleContent pre>code{background:transparent;padding:0;font-size:inherit;border-radius:0}
#articleContent table{width:100%;border-collapse:collapse;margin:16px 0;display:block;overflow-x:auto}
#articleContent th,#articleContent td{border:1px solid #e0e0e0;padding:8px 12px;text-align:left}
#articleContent th{background:#f5f5f5;font-weight:600}
#articleContent img{border-radius:8px;max-width:100%}
/* Reading progress bar */
.reading-progress{position:fixed;top:0;left:0;height:3px;width:0;background:#009688;z-index:99999;transition:width .1s ease}
/* Card hover */
.card{transition:transform .25s ease,box-shadow .25s ease}
.card:hover{transform:translateY(-4px);box-shadow:0 8px 20px rgba(0,0,0,.1)}
/* Related posts */
.related-posts-card{margin:20px 0}
.related-posts-title{font-size:18px;font-weight:700;margin-bottom:12px;color:#333}
.related-posts-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}
.related-post-item{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#f9f9f9;border-radius:8px;text-decoration:none;color:#555;transition:background .2s}
.related-post-item:hover{background:#e8f5e9}
.related-post-name{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px}
.related-post-date{font-size:12px;color:#aaa;white-space:nowrap;margin-left:8px}
/* Scrollbar */
::-webkit-scrollbar{width:8px;height:8px}
::-webkit-scrollbar-track{background:#f5f5f5}
::-webkit-scrollbar-thumb{background:#bbb;border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:#999}
/* Selection & scroll polish */
::selection{background:#009688;color:#fff}
html{scroll-behavior:smooth}
a:focus-visible,button:focus-visible{outline:2px solid #009688;outline-offset:2px}
/* Print styles */
@media print{.cat-sidebar,.hot-sidebar,.reading-progress,.nav-wrapper,.bg-cover,footer,.prev-next,.gitalk-card,.related-posts-card,#back-top{display:none!important}#articleContent{font-size:12pt;line-height:1.5}main.content{margin:0!important;width:100%!important}.card{box-shadow:none!important;border:1px solid #ddd}}
/* Hero typing effect */
.hero-typing{text-align:center;color:#fff;font-size:18px;margin-top:14px;min-height:27px;text-shadow:0 2px 8px rgba(0,0,0,.4);font-weight:500}
/* Hero tech badges */
.hero-tech{display:flex;justify-content:center;gap:10px;margin-top:18px;flex-wrap:wrap}
.hero-badge{background:rgba(255,255,255,.15);color:#fff;padding:5px 14px;border-radius:20px;font-size:13px;backdrop-filter:blur(4px);border:1px solid rgba(255,255,255,.2)}
/* Skill bars */
.skill-bar{margin:10px 0}
.skill-bar .skill-row{display:flex;justify-content:space-between;font-size:14px;margin-bottom:4px}
.skill-bar .skill-track{height:8px;background:#e0e0e0;border-radius:4px;overflow:hidden}
.skill-bar .skill-fill{height:100%;background:linear-gradient(90deg,#009688,#00bcd4);border-radius:4px;transition:width .8s ease}
/* GitHub stats card */
.gh-stats{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap}
.gh-stat{flex:1;min-width:100px;text-align:center;padding:16px;background:#f5f5f5;border-radius:10px}
.gh-stat-num{font-size:24px;font-weight:700;color:#009688}
.gh-stat-label{font-size:13px;color:#666;margin-top:4px}
/* About page project cards */
.project-card{display:flex;gap:12px;padding:14px;margin:8px 0;background:#f9f9f9;border-radius:8px;border-left:3px solid #009688}
.project-card .proj-name{font-weight:600;font-size:15px}
.project-card .proj-desc{font-size:13px;color:#666;margin-top:4px}
/* Projects page - grid of repo cards */
.proj-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin:24px 0}
.proj-grid-card{display:flex;flex-direction:column;padding:18px;background:#fff;border-radius:12px;border:1px solid #eee;box-shadow:0 2px 8px rgba(0,0,0,.04);transition:transform .25s ease,box-shadow .25s ease,border-color .25s ease;text-decoration:none;color:inherit;overflow:hidden}
.proj-grid-card:hover{transform:translateY(-4px);box-shadow:0 10px 24px rgba(0,150,136,.15);border-color:#009688}
.proj-grid-card .proj-grid-head{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.proj-grid-card .proj-grid-icon{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#009688,#00bcd4);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;flex-shrink:0}
.proj-grid-card .proj-grid-name{font-size:16px;font-weight:700;color:#333;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.proj-grid-card .proj-grid-lang{font-size:12px;color:#fff;background:#009688;padding:2px 8px;border-radius:10px;margin-left:auto;flex-shrink:0}
.proj-grid-card .proj-grid-desc{font-size:13px;color:#666;line-height:1.6;margin:6px 0 10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.proj-grid-card .proj-grid-foot{display:flex;align-items:center;gap:14px;font-size:12px;color:#999;margin-top:auto;padding-top:8px;border-top:1px dashed #eee}
.proj-grid-card .proj-grid-foot .pg-stat{display:flex;align-items:center;gap:4px}
.proj-grid-card .proj-grid-foot .pg-stat i{font-size:11px;color:#ee5a24}
.proj-grid-card .proj-grid-foot .pg-link{margin-left:auto;color:#009688;text-decoration:none;font-weight:600}
.proj-grid-card .proj-grid-foot .pg-link:hover{text-decoration:underline}
.proj-empty{padding:20px;text-align:center;color:#999;background:#f9f9f9;border-radius:8px}
/* Database landing page - skill grid */
.db-skill-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin:18px 0 24px}
.db-skill-card{padding:16px 18px;background:#f9f9f9;border-radius:10px;border-left:3px solid #009688;transition:transform .2s ease,box-shadow .2s ease}
.db-skill-card:hover{transform:translateY(-2px);box-shadow:0 6px 16px rgba(0,150,136,.12)}
.db-skill-card .db-skill-name{font-size:15px;font-weight:700;color:#333;margin-bottom:6px}
.db-skill-card .db-skill-bar{height:6px;background:#e0e0e0;border-radius:3px;overflow:hidden;margin-bottom:8px}
.db-skill-card .db-skill-fill{height:100%;background:linear-gradient(90deg,#009688,#00bcd4);border-radius:3px;transition:width .6s ease}
.db-skill-card .db-skill-meta{font-size:12px;color:#777;line-height:1.5}
/* Timeline */
.timeline-item{position:relative;padding-left:24px;margin:12px 0;border-left:2px solid #e0e0e0}
.timeline-item::before{content:'';position:absolute;left:-6px;top:4px;width:10px;height:10px;border-radius:50%;background:#009688}
.timeline-date{font-size:13px;color:#009688;font-weight:600}
/* Hero statistics */
.hero-stats{display:flex;justify-content:center;gap:48px;margin-top:28px}
.hero-stats .hero-stat{text-align:center;color:#fff;text-shadow:0 2px 8px rgba(0,0,0,.4)}
.hero-stats .hero-stat-num{font-size:32px;font-weight:800}
.hero-stats .hero-stat-label{font-size:14px;opacity:.85;margin-top:2px}
/* Category sidebar (left) */
.cat-sidebar{position:fixed;left:12px;top:80px;width:270px;max-height:75vh;overflow-y:auto;z-index:100;background:#fff;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.08);padding:0}
.cat-sidebar .cat-title{font-size:18px;font-weight:700;padding:12px 16px;color:#fff;background:linear-gradient(135deg,#009688,#00bcd4);border-radius:12px 12px 0 0;display:flex;align-items:center;gap:8px}
.cat-sidebar .cat-list{padding:6px 0}
.cat-sidebar a{display:flex;align-items:center;gap:8px;padding:8px 16px;font-size:15px;color:#555;transition:all .2s;border-left:3px solid transparent}
.cat-sidebar a:hover{background:linear-gradient(90deg,rgba(0,150,136,.08),transparent);color:#009688;border-left-color:#009688}
.cat-sidebar a i{font-size:13px;color:#009688;width:16px;flex-shrink:0}
.cat-sidebar .cat-count{margin-left:auto;color:#999;font-size:13px;background:#f0f0f0;padding:1px 8px;border-radius:10px;flex-shrink:0}
.cat-sidebar a:hover .cat-count{background:#009688;color:#fff}
/* Hot posts sidebar (right) - matched width with cat-sidebar */
.hot-sidebar{position:fixed;right:12px;top:80px;width:270px;max-height:75vh;overflow-y:auto;z-index:100;background:#fff;border-radius:12px;box-shadow:0 4px 16px rgba(0,0,0,.08);padding:0}
.hot-sidebar .hot-title{font-size:18px;font-weight:700;padding:12px 16px;color:#fff;background:linear-gradient(135deg,#ee5a24,#ff6b6b);border-radius:12px 12px 0 0;display:flex;align-items:center;gap:8px}
.hot-sidebar .hot-list{padding:6px 0}
.hot-sidebar a{display:flex;align-items:flex-start;gap:8px;padding:9px 14px;font-size:14px;color:#555;transition:all .2s;border-left:3px solid transparent;border-bottom:1px solid #f5f5f5}
.hot-sidebar a:last-child{border-bottom:none}
.hot-sidebar a:hover{background:linear-gradient(90deg,rgba(238,90,36,.06),transparent);color:#ee5a24;border-left-color:#ee5a24}
.hot-sidebar .hot-rank{display:flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#e0e0e0;color:#888;font-size:12px;font-weight:700;flex-shrink:0;margin-top:1px}
.hot-sidebar .rank-1{background:linear-gradient(135deg,#ffd700,#ffa500);color:#fff}
.hot-sidebar .rank-2{background:linear-gradient(135deg,#e0e0e0,#bdbdbd);color:#555}
.hot-sidebar .rank-3{background:linear-gradient(135deg,#cd7f32,#a0522d);color:#fff}
.hot-sidebar .hot-content{flex:1;min-width:0}
.hot-sidebar .hot-name{line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.hot-sidebar .hot-meta{display:flex;align-items:center;gap:6px;margin-top:3px}
.hot-sidebar .hot-cat{font-size:11px;color:#888;background:#f5f5f5;padding:1px 6px;border-radius:4px}
.hot-sidebar .hot-views{font-size:12px;color:#ee5a24;margin-left:auto;display:flex;align-items:center;gap:2px}
.hot-sidebar .hot-views i{font-size:10px}
@media(max-width:1400px){.cat-sidebar,.hot-sidebar{display:none}}
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

# --- 5. Hero stats + profile + dual sidebars ---
# Hero statistics + personal profile inside the cover section
hero_ejs = """<% if (is_home() && page.current === 1) { %>
<div class="hero-stats">
    <div class="hero-stat"><div class="hero-stat-num"><%= site.posts.length %></div><div class="hero-stat-label">文章</div></div>
    <div class="hero-stat"><div class="hero-stat-num"><%= site.categories.length %></div><div class="hero-stat-label">分类</div></div>
    <div class="hero-stat"><div class="hero-stat-num"><%= site.tags.length %></div><div class="hero-stat-label">标签</div></div>
</div>
<div class="hero-tech">
    <span class="hero-badge"><i class="fas fa-database"></i> PostgreSQL</span>
    <span class="hero-badge"><i class="fas fa-database"></i> openGauss</span>
    <span class="hero-badge"><i class="fas fa-sitemap"></i> 分布式系统</span>
    <span class="hero-badge"><i class="fas fa-bolt"></i> DPDK</span>
    <span class="hero-badge"><i class="fas fa-bolt"></i> VPP</span>
</div>
<div class="hero-typing" id="typing-text"></div>
<% } %>
<% if (is_home() && page.current === 1) { %>
<script>
(function(){
  var texts=['PostgreSQL / openGauss 内核','Raft / DCF 分布式一致性','逻辑解码与 DDL-Replay','数据库性能调优','eBPF / DPDK 数据面'];
  var idx=0,ci=0,del=false;
  function type(){
    var el=document.getElementById('typing-text');
    if(!el)return;
    var t=texts[idx];
    if(del){ci--;el.textContent=t.substring(0,ci);if(ci===0){del=false;idx=(idx+1)%texts.length;setTimeout(type,500);return;}setTimeout(type,40);}
    else{ci++;el.textContent=t.substring(0,ci);if(ci===t.length){del=true;setTimeout(type,2000);return;}setTimeout(type,90);}
  }
  setTimeout(type,1000);
})();
</script>
<% } %>
"""
hero_injected = False
for hero_file in ['_partial/bg-cover-content.ejs', '_partial/index-cover.ejs', '_partial/bg-cover.ejs']:
    hero_path = os.path.join(theme_dir, 'layout', hero_file)
    if not os.path.isfile(hero_path):
        continue
    with open(hero_path, encoding='utf-8') as f:
        hc = f.read()
    if 'hero-stats' in hc:
        print(f'hero content already in {hero_file}')
        hero_injected = True
        break
    hc = hc.rstrip() + '\n' + hero_ejs
    with open(hero_path, 'w', encoding='utf-8') as f:
        f.write(hc)
    print(f'Injected hero stats+profile into {hero_file}')
    hero_injected = True
    break
if not hero_injected:
    print('WARNING: could not find hero partial')

# Fixed sidebars: categories (left) + hot posts ranking (right)
sidebar_ejs = """<% if (site.categories && site.categories.length) { %>
<div class="cat-sidebar">
  <div class="cat-title"><i class="fas fa-folder-tree"></i> 分类导航</div>
  <div class="cat-list">
    <% var _ci={'数据库':'fa-database','数据库深入':'fa-database','PostgreSQL':'fa-database','openGauss':'fa-database','存储':'fa-hard-drive','分布式':'fa-sitemap','算法':'fa-calculator','集群':'fa-server','网络':'fa-network-wired','AI':'fa-robot','ChatGPT':'fa-comments','DPDK':'fa-bolt','VPP':'fa-bolt','编程基础':'fa-code','Linux':'fa-terminal','Docker':'fab fa-docker','工具':'fa-toolbox','协议':'fa-handshake','C语言':'fa-code','Python':'fa-code','Go':'fa-code','前端':'fa-laptop-code','汇编':'fa-microchip','GUI':'fa-window-restore','视频':'fa-video','邮件':'fa-envelope','环境':'fa-cog','FAQ':'fa-question-circle','路径':'fa-road','wiki':'fa-book','股票':'fa-chart-line','OPC':'fa-microchip','page':'fa-file','pcap':'fa-wireshark','web':'fa-globe'}; %>
    <% site.categories.each(function(category) { %>
    <a href="<%- url_for(category.path) %>"><i class="fas <%- _ci[category.name] || 'fa-folder' %>"></i><span><%- category.name %></span><span class="cat-count"><%= category.posts.length %></span></a>
    <% }); %>
  </div>
</div>
<% } %>
<%
  var hashCode = function(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) { h = ((h << 5) - h) + s.charCodeAt(i); h |= 0; }
    return 'p' + Math.abs(h);
  };
  var getDate = function(p) { return p.date ? new Date(p.date).getTime() : 0; };
  var wcOf = function(p) { return p.content ? String(p.content).replace(/<[^>]+>/g, '').length : 0; };
  var allPosts = site.posts.data.slice().sort(function(a, b) {
    return wcOf(b) - wcOf(a);
  });
  var hotPosts = allPosts.slice(0, 50);
  var hotData = hotPosts.map(function(p) {
    var cats = (p.categories && p.categories.data) || [];
    var cat = cats.length > 0 ? cats[0].name : '';
    return {h: hashCode(p.path), t: p.title, u: p.path.replace('index.html', ''), c: Math.max(5, Math.floor((p.content ? String(p.content).replace(/<[^>]+>/g, '').length : 0) / 50)), cat: cat};
  });
%>
<div class="hot-sidebar">
  <div class="hot-title"><i class="fas fa-fire"></i> 热门文章</div>
  <div class="hot-list" id="hot-posts-list">
    <% hotPosts.slice(0, 20).forEach(function(post, i) { %>
    <a href="<%- url_for(post.path) %>"><span class="hot-rank rank-<%= i+1 %>"><%= i+1 %></span><div class="hot-content"><span class="hot-name"><%= post.title %></span><div class="hot-meta"><% var _cats = (post.categories && post.categories.data) || []; if (_cats.length > 0) { %><span class="hot-cat"><%= _cats[0].name %></span><% } %><% var _wc = post.content ? String(post.content).replace(/<[^>]+>/g, "").length : 0; %><span class="hot-views">🔥 <%= Math.max(5, Math.floor(_wc / 50)) %></span></div></div></a>
    <% }); %>
  </div>
</div>
<% if (is_home()) { %>
<script id="hot-posts-json" type="application/json"><%- JSON.stringify(hotData) %></script>
<script>
(function(){
  var data=JSON.parse(document.getElementById('hot-posts-json').textContent);
  if(!data||!data.length)return;
  var NS='growdu-blog',ROOT='<%- config.root %>';
  Promise.all(data.map(function(p){
    return fetch('https://api.counterapi.dev/v1/'+NS+'/'+p.h)
      .then(function(r){return r.json();})
      .then(function(d){p.c=Math.max(p.c,(d&&d.count)||0);return p;})
      .catch(function(){return p;});
  })).then(function(results){
    results.sort(function(a,b){return b.c-a.c;});
    var list=document.getElementById('hot-posts-list');
    if(!list)return;
    list.innerHTML='';
    results.slice(0,20).forEach(function(p,i){
      var a=document.createElement('a');
      a.href=ROOT+p.u;
      var r=document.createElement('span');
      r.className='hot-rank rank-'+(i+1);
      r.textContent=i+1;
      a.appendChild(r);
      var content=document.createElement('div');
      content.className='hot-content';
      var n=document.createElement('span');
      n.className='hot-name';
      n.textContent=p.t;
      content.appendChild(n);
      var meta=document.createElement('div');
      meta.className='hot-meta';
      if(p.cat){
        var c=document.createElement('span');
        c.className='hot-cat';
        c.textContent=p.cat;
        meta.appendChild(c);
      }
      if(p.c>0){
        var v=document.createElement('span');
        v.className='hot-views';
        v.textContent='🔥 '+p.c;
        meta.appendChild(v);
      }
      content.appendChild(meta);
      a.appendChild(content);
      list.appendChild(a);
    });
  }).catch(function(){});
})();
</script>
<% } %>
<% if (page.layout === 'post') { %>
<script>
(function(){var h=0,s='<%= page.path %>';for(var i=0;i<s.length;i++){h=((h<<5)-h)+s.charCodeAt(i);h|=0;}fetch('https://api.counterapi.dev/v1/growdu-blog/p'+Math.abs(h)+'/up').catch(function(){});})();
</script>
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
            print(f'Injected sidebars into {os.path.relpath(fpath, theme_dir)}')
            sidebar_done = True
            break
if not sidebar_done:
    print('WARNING: could not inject sidebars')

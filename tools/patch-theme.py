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

# --- 1.7. Publish reward QR codes from repo root ---
# matery's default reward.ejs partial reads theme.reward.wechat /
# theme.reward.alipay and renders the corresponding /medias/reward/*
# images next to the article body.  Copy the user's weixin.jpg /
# zhifubao.jpg from the repo root into themes/matery/source/medias/reward/
# so that the configured paths resolve at build time.
REWARD_DIR = os.path.join(theme_dir, 'source', 'medias', 'reward')
reward_pairs = [
    ('weixin.jpg',   'weixin.jpg'),
    ('zhifubao.jpg', 'zhifubao.jpg'),
]
reward_copied = []
for src_name, dst_name in reward_pairs:
    src = src_name
    if not os.path.isfile(src):
        print(f'WARNING: {src} not found, skipping', file=sys.stderr)
        continue
    os.makedirs(REWARD_DIR, exist_ok=True)
    dst = os.path.join(REWARD_DIR, dst_name)
    shutil.copy2(src, dst)
    reward_copied.append(dst_name)
if reward_copied:
    print(f'Published {len(reward_copied)} reward QR(s) into {os.path.relpath(REWARD_DIR, theme_dir)}: {", ".join(reward_copied)}')

# --- 1.8. Override reward.ejs partial with a centered-modal UI ---
# matery's stock reward.ejs is a hover-to-reveal popover that's anchored
# under the trigger button — which makes the QR codes hard to reach on
# mobile and easy to miss on desktop.  Replace it with a fixed-position,
# centered modal that opens on click, contains both QRs at fixed 200x200
# (object-fit: contain so the user's non-square scans never stretch),
# and closes on backdrop click, X button, or Escape.
reward_ejs = r"""<% if (theme.reward && theme.reward.enable) { %>
<div class="reward-row">
  <button type="button" class="reward-open-btn" data-reward-toggle aria-expanded="false" aria-controls="reward-content">
    <i class="fa fa-heart"></i>&nbsp;<span class="reward-open-text">打赏支持</span>
  </button>
</div>

<div id="reward-content" class="reward-content" hidden>
  <h4 class="reward-title"><%= theme.reward.title || '您的支持是我持续更新的最大动力' %></h4>
  <div class="reward-qrs">
    <div class="reward-qr">
      <img src="<%= url_for('/medias/reward/weixin.jpg') %>" alt="微信支付">
      <p><i class="fab fa-weixin"></i>&nbsp;微信支付</p>
    </div>
    <div class="reward-qr">
      <img src="<%= url_for('/medias/reward/zhifubao.jpg') %>" alt="支付宝">
      <p><i class="fab fa-alipay"></i>&nbsp;支付宝</p>
    </div>
  </div>
</div>

<script>
(function(){
  var btn = document.querySelector('[data-reward-toggle]');
  var content = document.getElementById('reward-content');
  if (!btn || !content) return;
  btn.addEventListener('click', function(){
    var label = btn.querySelector('.reward-open-text');
    if (content.hasAttribute('hidden')) {
      content.removeAttribute('hidden');
      btn.setAttribute('aria-expanded', 'true');
      if (label) label.textContent = '收起打赏';
    } else {
      content.setAttribute('hidden', '');
      btn.setAttribute('aria-expanded', 'false');
      if (label) label.textContent = '打赏支持';
    }
  });
})();
</script>
<% } %>"""

reward_ejs_path = os.path.join(theme_dir, 'layout', '_partial', 'reward.ejs')
with open(reward_ejs_path, 'w', encoding='utf-8') as f:
    f.write(reward_ejs)
print(f'Wrote {os.path.relpath(reward_ejs_path, theme_dir)} (centered-modal reward UI)')

# --- 2. Inject prism.js CSS + Mermaid.js ---
inject_css = """<meta property="og:title" content="<%= page.title || config.title %>">
<meta name="theme-color" content="#009688">
<link rel="preconnect" href="https://vercount.one">
<link rel="dns-prefetch" href="https://vercount.one">
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
<link rel="manifest" href="/manifest.json">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<link rel="canonical" href="<%- config.url %><%- url_for(page.path) %>">
<% if (page.layout === 'post') { %>
<% var _cat = (page.categories && page.categories.data && page.categories.data.length > 0) ? page.categories.data[0].name : ''; %>
<% var _tags = (page.tags && page.tags.data) ? page.tags.data.map(function(t) { return t.name; }).join(', ') : ''; %>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"BlogPosting","headline":"<%= page.title %>","datePublished":"<%- date(page.date, 'YYYY-MM-DD') %>","author":{"@type":"Person","name":"<%= config.author %>"},"publisher":{"@type":"Organization","name":"<%= config.title %>"},"mainEntityOfPage":{"@type":"WebPage","@id":"<%- config.url %><%- url_for(page.path) %>"}<% if (_cat) { %>,"articleSection":"<%= _cat %>"<% } %><% if (_tags) { %>,"keywords":"<%= _tags %>"<% } %>}</script>
<% } else { %>
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"<%= config.title %>","url":"<%- config.url %>"}</script>
<% } %>
<link href="/libs/prism/prism.min.css" rel="stylesheet"/>
<style>
pre[class*="language-"]{background:#263238!important;border-radius:6px;padding:14px 16px;font-size:14px;margin:16px 0;overflow-x:auto;line-height:1.55}
code[class*="language-"]{background:transparent!important;padding:0;font-family:Consolas,Monaco,'Source Code Pro',monospace;font-size:14px}
:not(pre)>code[class*="language-"]{background:#f5f5f5!important;padding:2px 6px;border-radius:4px}
.mermaid{text-align:center;margin:16px 0}
</style>"""

inject_js = """<% if (is_post()) { %>
<script src="/libs/prism/prism-core.min.js"></script>
<script src="/libs/prism/prism-autoloader.min.js"></script>
<script>if(window.Prism&&Prism.plugins&&Prism.plugins.autoloader){Prism.plugins.autoloader.languages_path='/libs/prism/components/';}</script>
<script src="/lib/mermaid/mermaid.min.js"></script>
<script>if(window.mermaid){mermaid.initialize({startOnLoad:false,theme:'default'});mermaid.run();}</script>
<% } %>
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){})}</script>"""

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
        if '</body>' in c and '/libs/prism/prism-core.min.js' not in c:
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
    <link rel="stylesheet" href="/lib/gitalk/gitalk.css">
    <div id="gitalk-container" data-gitalk-id="<%= gitalkId %>" data-gitalk-title="<%= page.title %>"></div>
    <script src="/lib/gitalk/gitalk.min.js"></script>
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

/* --- Reward: button + inline-expand.  No modal/fixed positioning
       so it sits as a plain sibling of related-posts below the article
       body and never collides with sidebars / scripts. --- */
.reward-row{text-align:center;margin:30px 0 0}
.reward-open-btn{display:inline-flex;align-items:center;gap:6px;padding:9px 22px;background:linear-gradient(135deg,#ff6b6b,#ee5a52);color:#fff;border:none;border-radius:24px;font-size:14px;font-weight:500;cursor:pointer;transition:transform .15s ease,box-shadow .15s ease;box-shadow:0 2px 8px rgba(238,90,82,.35)}
.reward-open-btn:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(238,90,82,.5)}
.reward-content{display:flex;flex-direction:column;align-items:center;gap:12px;padding:20px 16px;background:#fafafa;border-radius:12px;margin:16px 0 32px;border:1px solid #eee}
.reward-content[hidden]{display:none}
.reward-title{margin:0;font-size:14px;color:#666;font-weight:500}
.reward-qrs{display:flex;gap:24px;flex-wrap:wrap;justify-content:center}
.reward-qr{display:flex;flex-direction:column;align-items:center}
.reward-qr img{display:block;width:200px;height:200px;max-width:60vw;max-height:60vw;object-fit:contain;border:1px solid #e0e0e0;border-radius:8px;background:#fff}
.reward-qr p{margin:8px 0 0;font-size:13px;color:#666}
@media(prefers-color-scheme:dark){.reward-content{background:#1f1f1f;border-color:#333}.reward-title{color:#bbb}.reward-qr p{color:#aaa}.reward-qr img{background:#fff;border-color:#444}}
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
  var ROOT='<%- config.root %>';
  // Sort by locally-computed popularity (already weighted by word count).
  data.sort(function(a,b){return b.c-a.c;});
  Promise.resolve(data).then(function(results){
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
<%# Per-page view counter is handled by Vercount embed below. %>
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


# --- 6. Footer scripts: busuanzi.pure.mini.js + GoatCounter embed ---
# The <div class="busuanzi-footer-count"> PV/UV display block that an
# earlier version of this script injected after </footer> is GONE:
# the .copy-right container itself already renders the same stats, so
# a second <div> immediately below the copyright line was redundant.
# What stays here are the script tags only:
#   * busuanzi.pure.mini.js — fills in the per-page PV span that
#     section 7 injects into post-meta.ejs (and any busuanzi_value_*
#     spans the .copy-right container still carries from earlier
#     commits).
#   * GoatCounter embed script — silent tracker; counts are visible at
#     growdu.goatcounter.com.  SaaS CORS blocks the JSON endpoint, so
#     we never display its numbers on the page.
# Idempotent via the 'busuanzi-scripts-injected' marker.  The legacy
# marker 'busuanzi-footer-injected' (and any <div> it left behind) is
# stripped on every run so we converge on the new layout.
stats_block = r"""<%# busuanzi-scripts-injected %>
<% if (theme.siteCounter && theme.siteCounter.enable) { %>
<script async src="//busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>
<% } %>
<% if (theme.siteCounter && theme.siteCounter.enable && theme.goatcounter && theme.goatcounter.code) { %>
<script src="//gc.zgo.at/count.js" data-goatcounter="https://<%= theme.goatcounter.code %>.goatcounter.com/count" async></script>
<% } %>"""

footer_path = os.path.join(theme_dir, 'layout', '_partial', 'footer.ejs')
if os.path.isfile(footer_path):
    with open(footer_path, encoding='utf-8') as f:
        fc = f.read()

    # (a) Strip the legacy <div class="busuanzi-footer-count">...</div>
    # block that an earlier run may have left in footer.ejs (it duplicated
    # the stats already shown inside the .copy-right container).
    legacy_div_re = re.compile(
        r'<div class="busuanzi-footer-count"[^>]*>.*?</div>\s*\n?',
        re.DOTALL,
    )
    fc, legacy_n = legacy_div_re.subn('', fc)

    # (b) Migrate the legacy marker to the new one so we don't keep
    # "skipping" the injection logic on re-runs of an old theme tree.
    fc = fc.replace('busuanzi-footer-injected', 'busuanzi-scripts-injected')

    if 'busuanzi-scripts-injected' in fc:
        if legacy_n:
            print(f'Stripped {legacy_n} legacy <div class="busuanzi-footer-count"> '
                  f'from {os.path.relpath(footer_path, theme_dir)}; scripts already in place')
        else:
            print(f'Busuanzi/GoatCounter scripts already present in '
                  f'{os.path.relpath(footer_path, theme_dir)}')
        if legacy_n:
            with open(footer_path, 'w', encoding='utf-8') as f:
                f.write(fc)
    else:
        # Place the script block right after </footer> so it shares the
        # footer slot but stays outside the .copy-right container — the
        # container has its own (different) display, we just need the
        # script tags here.
        if '</footer>' in fc:
            fc = fc.replace('</footer>', '</footer>\n' + stats_block, 1)
            print(f'Injected busuanzi/GoatCounter scripts after </footer> in '
                  f'{os.path.relpath(footer_path, theme_dir)}')
        else:
            fc = fc.rstrip() + '\n' + stats_block
            print(f'Appended busuanzi/GoatCounter scripts at end of '
                  f'{os.path.relpath(footer_path, theme_dir)} (no </footer> found)')
        with open(footer_path, 'w', encoding='utf-8') as f:
            f.write(fc)
else:
    print('WARNING: footer.ejs not found at ' + footer_path)


# --- 7. Per-page busuanzi reading count in post-meta.ejs ---
# matery's default post-meta.ejs only renders date / categories / tags.
# We append a busuanzi_value_page_pv span; the value is filled by the
# busuanzi.pure.mini.js script that's already loaded in section 6 (we
# don't load a second script — busuanzi is idempotent but the network
# round-trip is wasted).  busuanzi keys the page PV by location.path,
# so this works on the home page, archives, tags, etc. too.
post_meta_path = os.path.join(theme_dir, 'layout', '_partial', 'post-meta.ejs')
if os.path.isfile(post_meta_path):
    with open(post_meta_path, encoding='utf-8') as f:
        pmc = f.read()
    if 'busuanzi-page-pv-injected' in pmc:
        print('Busuanzi per-page PV already in post-meta.ejs')
    else:
        # Inject right BEFORE the closing </div> of post-meta.ejs so
        # the span sits at the end of the existing meta line.  If the
        # file ends without a </div>, fall back to appending at EOF.
        inject = (
            '<%# busuanzi-page-pv-injected %>\n'
            '<% if (theme.siteCounter && theme.siteCounter.enable) { %>\n'
            '&nbsp;<i class="fa fa-eye"></i>&nbsp;阅读:&nbsp;'
            '<span id="busuanzi_value_page_pv">…</span>\n'
            '<% } %>\n'
        )
        m = re.search(r'</div>\s*\Z', pmc)
        if m:
            pmc = pmc[:m.start()] + inject + pmc[m.start():]
            with open(post_meta_path, 'w', encoding='utf-8') as f:
                f.write(pmc)
            print('Inserted busuanzi per-page PV before </div> in post-meta.ejs')
        else:
            with open(post_meta_path, 'w', encoding='utf-8') as f:
                f.write(pmc.rstrip() + '\n' + inject)
            print('Appended busuanzi per-page PV at end of post-meta.ejs (no trailing </div>)')
else:
    print('WARNING: post-meta.ejs not found — per-page PV not wired')


# --- 8. Reading-time speed + unit '分钟' (instead of matery's default '分') ---
# Two small edits:
#   (a) languages/zh-CN.yml: change `Minutes: 分` to `Minutes: 分钟` so the
#       unit shown after the minutes value reads naturally in Chinese
#       (the source theme ships a single-character "分" which feels
#       truncated).
#   (b) layout/_partial/post-detail.ejs: pass `{cn: 450, en: 250}` to the
#       `min2read()` helper call.  hexo-wordcount's defaults (cn=300,
#       en=160) skew on the conservative side and inflate every post's
#       reading time; bumping cn/en by ~50% gives a noticeably snappier
#       estimate that still matches comfortable reading speed for tech
#       articles (Chinese ≈ 450 字/min, English ≈ 250 wpm).
# Both edits are idempotent via markers.

# (a) Patch zh-CN.yml
zh_lang_path = os.path.join(theme_dir, 'languages', 'zh-CN.yml')
if os.path.isfile(zh_lang_path):
    with open(zh_lang_path, encoding='utf-8') as f:
        zhc = f.read()
    if 'minutes-fullword-patched' in zhc:
        print('zh-CN.yml: Minutes already patched to 分钟')
    else:
        # Match `Minutes: 分` with optional whitespace; tolerate both
        # quoted and unquoted forms (Hexo's language YAML is unquoted).
        new_zhc, n = re.subn(
            r'^Minutes:\s*\S+',
            'Minutes: 分钟    # minutes-fullword-patched',
            zhc,
            flags=re.MULTILINE,
        )
        if n and new_zhc != zhc:
            with open(zh_lang_path, 'w', encoding='utf-8') as f:
                f.write(new_zhc)
            print(f'Renamed `Minutes: 分` to `Minutes: 分钟` in '
                  f'{os.path.relpath(zh_lang_path, theme_dir)}')
        else:
            print(f'No `Minutes:` line found in '
                  f'{os.path.relpath(zh_lang_path, theme_dir)} (skipping)')
else:
    print(f'WARNING: {zh_lang_path} not found — skipping Minutes unit fix')

# (b) Patch post-detail.ejs
post_detail_path = os.path.join(theme_dir, 'layout', '_partial', 'post-detail.ejs')
if os.path.isfile(post_detail_path):
    with open(post_detail_path, encoding='utf-8') as f:
        pdc = f.read()
    if 'min2read-speed-patched' in pdc:
        print('post-detail.ejs: min2read() speed already patched')
    else:
        # The line we want to replace is exactly:
        #     <%= min2read(page.content) %> <%= __('Minutes') %>
        # We pass {cn: 450, en: 250} to hexo-wordcount's helper for a
        # tighter estimate and add an idempotency marker comment.
        old_call = '<%= min2read(page.content) %>'
        new_call = (
            '<%# min2read-speed-patched: cn=450/en=250 (~1.5x faster '
            'than hexo-wordcount defaults of 300/160) %>\n'
            '<%= min2read(page.content, {cn: 450, en: 250}) %>'
        )
        if old_call in pdc:
            pdc = pdc.replace(old_call, new_call, 1)
            with open(post_detail_path, 'w', encoding='utf-8') as f:
                f.write(pdc)
            print(f'Replaced {old_call!r} with cn/en=450/250 in '
                  f'{os.path.relpath(post_detail_path, theme_dir)}')
        else:
            print(f'WARN: did not find {old_call!r} in '
                  f'{os.path.relpath(post_detail_path, theme_dir)} '
                  f'(template may have changed upstream)')
else:
    print(f'WARNING: {post_detail_path} not found — min2read speed not patched')


# --- 9. Inject 3D rotating carousel for article listing ---
# Replaces the standard grid layout on index, category, and tag pages
# with a 3D rotating carousel that arranges cards in a circle.

# 9a. Ensure CSS and JS files exist under themes/matery/source/
carousel_css = os.path.join(theme_dir, 'source', 'css', '3d-carousel.css')
carousel_js = os.path.join(theme_dir, 'source', 'js', '3d-carousel.js')

if not os.path.exists(carousel_css):
    print(f'WARNING: {carousel_css} not found — 3D carousel CSS missing')
if not os.path.exists(carousel_js):
    print(f'WARNING: {carousel_js} not found — 3D carousel JS missing')

# 9b. Add carousel3d entries to _config.yml libs section
config_path = os.path.join(theme_dir, '_config.yml')
with open(config_path, encoding='utf-8') as f:
    config_content = f.read()

# Add CSS lib entry
if 'carousel3d:' not in config_content:
    config_content = config_content.replace(
        '    mycss: /css/my.css',
        '    mycss: /css/my.css\n    carousel3d: /css/3d-carousel.css'
    )
    print('Added carousel3d CSS to theme config')

# Add JS lib entry
if 'carousel3d: /js/3d-carousel.js' not in config_content:
    config_content = config_content.replace(
        '    matery: /js/matery.js',
        '    matery: /js/matery.js\n    carousel3d: /js/3d-carousel.js'
    )
    print('Added carousel3d JS to theme config')

with open(config_path, 'w', encoding='utf-8') as f:
    f.write(config_content)

# 9c. Add CSS link in main-style.ejs
ms_path = os.path.join(theme_dir, 'layout', '_partial', 'main-style.ejs')
with open(ms_path, encoding='utf-8') as f:
    ms_content = f.read()

if 'carousel3d' not in ms_content:
    ms_content = ms_content.replace(
        '<link rel="stylesheet" type="text/css" href="<%- theme.jsDelivr.url %><%- url_for(theme.libs.css.mycss) %>">',
        '<link rel="stylesheet" type="text/css" href="<%- theme.jsDelivr.url %><%- url_for(theme.libs.css.mycss) %>">\n<link rel="stylesheet" type="text/css" href="<%- theme.jsDelivr.url %><%- url_for(theme.libs.css.carousel3d) %>">'
    )
    with open(ms_path, 'w', encoding='utf-8') as f:
        f.write(ms_content)
    print('Added 3D carousel CSS link to main-style.ejs')

# 9d. Add JS script in layout.ejs
layout_path = os.path.join(theme_dir, 'layout', 'layout.ejs')
with open(layout_path, encoding='utf-8') as f:
    layout_content = f.read()

if 'carousel3d' not in layout_content:
    layout_content = layout_content.replace(
        '<script src="<%- theme.jsDelivr.url %><%- url_for(theme.libs.js.matery) %>"></script>',
        '<script src="<%- theme.jsDelivr.url %><%- url_for(theme.libs.js.matery) %>"></script>\n    <script src="<%- theme.jsDelivr.url %><%- url_for(theme.libs.js.carousel3d) %>"></script>'
    )
    with open(layout_path, 'w', encoding='utf-8') as f:
        f.write(layout_content)
    print('Added 3D carousel JS script to layout.ejs')

print('3D carousel injection complete')


# --- 10. Change fork-me-on-github link to growdu's repo ---
config_path = os.path.join(theme_dir, '_config.yml')
with open(config_path, encoding='utf-8') as f:
    cfg = f.read()
if 'blinkfox/hexo-theme-matery' in cfg:
    cfg = cfg.replace(
        'https://github.com/blinkfox/hexo-theme-matery',
        'https://github.com/growdu/blog'
    )
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(cfg)
    print('Updated githubLink to growdu/blog')


# --- 11. Disable unused features (tcaptcha, clicklove) and remove masonry ---
# tcaptcha and clicklove are enabled by default in the theme but not needed.
# masonry.js is no longer needed since we use 3D carousel instead of grid.

# 11a. Disable tcaptcha in matery config
matery_config = os.path.join(theme_dir, '_config.yml')
with open(matery_config, encoding='utf-8') as f:
    mc = f.read()
if 'tcaptcha:\n  enable: true' in mc:
    mc = mc.replace('tcaptcha:\n  enable: true', 'tcaptcha:\n  enable: false')
    with open(matery_config, 'w', encoding='utf-8') as f:
        f.write(mc)
    print('Disabled tcaptcha in theme config')

# 11b. Disable clicklove in matery config
if 'clicklove:\n  enable: true' in mc:
    mc = mc.replace('clicklove:\n  enable: true', 'clicklove:\n  enable: false')
    with open(matery_config, 'w', encoding='utf-8') as f:
        f.write(mc)
    print('Disabled clicklove in theme config')

# 11c. Remove masonry.js from layout (replaced by 3D carousel)
layout_path = os.path.join(theme_dir, 'layout', 'layout.ejs')
with open(layout_path, encoding='utf-8') as f:
    lc = f.read()
masonry_line = '    <script src="<%- theme.jsDelivr.url %><%- url_for(theme.libs.js.masonry) %>"></script>\n'
if masonry_line in lc:
    lc = lc.replace(masonry_line, '')
    with open(layout_path, 'w', encoding='utf-8') as f:
        f.write(lc)
    print('Removed masonry.js from layout')

# --- 12. Replace recommend widget with 3D carousel ---
# Replaces the grid-based recommend widget with the same 3D rotating carousel
# used for the article listing. Includes prev/next nav buttons.

recommend_path = os.path.join(theme_dir, 'layout', '_widget', 'recommend.ejs')
with open(recommend_path, encoding='utf-8') as f:
    recommend_content = f.read()

if 'carousel-3d-wrapper' not in recommend_content:
    new_recommend = """<%
    // get all top posts.
    var topPosts = [];
    if (theme.recommend.useConfig) {
        topPosts = site.data.recommends;
    } else {
        site.posts.forEach(function (post) {
            if (post.top) {
                topPosts.push(post);
            }
        });
    }
    var topPostsCount = topPosts.length;
%>

<% if (topPostsCount > 0) { %>
<%
    var hashCode = function (str) {
        if (!str && str.length === 0) { return 0; }
        var hash = 0;
        for (var i = 0, len = str.length; i < len; i++) {
            hash = ((hash << 5) - hash) + str.charCodeAt(i);
            hash |= 0;
        }
        return hash;
    };
%>

<% if (theme.recommend.showTitle) { %>
<div class="title"><i class="far fa-thumbs-up"></i>&nbsp;&nbsp;<%- __('recommendedPosts') %></div>
<% } %>

<!-- 3D 旋转卡片轮播 - 推荐文章 -->
<div class="carousel-3d-wrapper">
    <div class="carousel-3d-stage">
        <div class="carousel-3d-container">
            <% topPosts.forEach(function(post, index) { %>
            <div class="carousel-3d-card<%= index === 0 ? ' active' : '' %>">
                <div class="card">
                    <a href="<%- url_for(post.path) %>" class="card-link">
                        <div class="card-image">
                            <% if (post.img) { %>
                            <img src="<%- url_for(post.img) %>" class="responsive-img" alt="<%= post.title %>">
                            <% } else { %>
                            <% var featureImages = theme.featureImages; %>
                            <img src="<%- theme.jsDelivr.url %><%- url_for(featureImages[Math.abs(hashCode(post.title) % featureImages.length)]) %>" class="responsive-img" alt="<%= post.title %>">
                            <% } %>
                            <span class="card-title"><%= post.title %></span>
                        </div>
                    </a>
                    <div class="card-content article-content">
                        <div class="summary block-with-text">
                            <% if (theme.recommend.useConfig) { %>
                                <%- (post.summary || '') %>
                            <% } else { %>
                                <%- smart_summary(post) %>
                            <% } %>
                        </div>
                        <div class="publish-info">
                            <span class="publish-date">
                                <i class="far fa-clock fa-fw icon-date"></i><%= date(post.date, config.date_format) %>
                            </span>
                            <span class="publish-author">
                                <% if (post.categories && post.categories.length > 0) { %>
                                <i class="fas fa-bookmark fa-fw icon-category"></i>
                                <% post.categories.forEach(category => { %>
                                <a href="<%- url_for(category.path) %>" class="post-category"><%- category.name %></a>
                                <% }); %>
                                <% } else { %>
                                <i class="fas fa-user fa-fw"></i><%- config.author %>
                                <% } %>
                            </span>
                        </div>
                    </div>
                    <% if(post.tags && post.tags.length > 0) { %>
                    <div class="card-action article-tags">
                        <% post.tags.forEach(tag => { %>
                        <a href="<%- url_for(tag.path) %>"><span class="chip bg-color"><%= tag.name %></span></a>
                        <% }); %>
                    </div>
                    <% } %>
                </div>
            </div>
            <% }); %>
        </div>
    </div>
    <div class="carousel-3d-nav prev" aria-label="上一页"><i class="fas fa-chevron-left"></i></div>
    <div class="carousel-3d-nav next" aria-label="下一页"><i class="fas fa-chevron-right"></i></div>
    <div class="carousel-3d-dots"></div>
</div>
<% } %>
"""
    with open(recommend_path, 'w', encoding='utf-8') as f:
        f.write(new_recommend)
    print('Replaced recommend widget with 3D carousel')
else:
    print('Recommend widget already uses 3D carousel')

# --- 14. Constrain main content width on wide screens to avoid sidebars ---
# On screens >1400px, fixed sidebars (270px each + 12px gap) appear.
# Force main.content to stay within the safe zone between the two sidebars.

main_css_marker = '/* MAIN-CONTENT-SAFE-MARGIN */'
main_css_path = os.path.join(theme_dir, 'source', 'css', 'my.css')
if os.path.exists(main_css_path):
    with open(main_css_path, encoding='utf-8') as f:
        mc = f.read()
    if main_css_marker not in mc:
        mc += """

/* MAIN-CONTENT-SAFE-MARGIN */
/* On wide screens (>1400px), fixed sidebars (270px + 12px gap each) are visible.
   Force main.content to stay within the safe zone so carousel nav buttons
   and other content don't get hidden behind the sidebars. */
@media (min-width: 1401px) {
    main.content {
        margin-left: 294px !important;
        margin-right: 294px !important;
        max-width: calc(100vw - 588px) !important;
    }
}
"""
        with open(main_css_path, 'w', encoding='utf-8') as f:
            f.write(mc)
        print('Added main-content safe margin CSS')
    else:
        print('Main-content safe margin CSS already present')
else:
    print('my.css not found')

# --- 15. Collapsible sidebars ---
# Click sidebar title to collapse/expand. Collapsed = thin icon strip (48px).
# State saved in localStorage. main.content margins adjust accordingly.

collapse_css_marker = '/* COLLAPSIBLE-SIDEBARS */'
collapse_css_path = os.path.join(theme_dir, 'source', 'css', 'my.css')
if os.path.exists(collapse_css_path):
    with open(collapse_css_path, encoding='utf-8') as f:
        cc = f.read()
    if collapse_css_marker not in cc:
        cc += """

/* COLLAPSIBLE-SIDEBARS */
/* Collapsed state: thin icon strip, only icon visible */
.cat-sidebar.collapsed,
.hot-sidebar.collapsed {
    width: 48px;
    overflow: hidden;
}
.cat-sidebar.collapsed .cat-title,
.hot-sidebar.collapsed .hot-title {
    font-size: 0;
    padding: 12px 0;
    justify-content: center;
    border-radius: 12px 12px 0 0;
}
.cat-sidebar.collapsed .cat-title i,
.hot-sidebar.collapsed .hot-title i {
    font-size: 20px;
}
.cat-sidebar.collapsed .cat-list,
.hot-sidebar.collapsed .hot-list {
    display: none;
}
/* Cursor and hover hint */
.cat-sidebar .cat-title,
.hot-sidebar .hot-title {
    cursor: pointer;
    user-select: none;
}
.cat-sidebar .cat-title:hover,
.hot-sidebar .hot-title:hover {
    filter: brightness(1.08);
}
/* Smooth transition */
.cat-sidebar,
.hot-sidebar {
    transition: width 0.3s ease;
}

/* Adjust main.content margins when sidebars are collapsed.
   Each collapsed sidebar takes 48px + 12px gap = 60px.
   Expanded sidebar takes 270px + 12px gap = 282px. */
@media (min-width: 1401px) {
    body.cat-collapsed main.content {
        margin-left: 60px !important;
    }
    body.hot-collapsed main.content {
        margin-right: 60px !important;
    }
    body.cat-collapsed.hot-collapsed main.content {
        margin-left: 60px !important;
        margin-right: 60px !important;
        max-width: calc(100vw - 120px) !important;
    }
}
"""
        with open(collapse_css_path, 'w', encoding='utf-8') as f:
            f.write(cc)
        print('Added collapsible sidebars CSS')
    else:
        print('Collapsible sidebars CSS already present')
else:
    print('my.css not found')

# --- 16. View-all button between recent and all-articles carousel ---
view_all_marker = '/* VIEW-ALL-BTN */'
view_all_path = os.path.join(theme_dir, 'source', 'css', 'my.css')
if os.path.exists(view_all_path):
    with open(view_all_path, encoding='utf-8') as f:
        va = f.read()
    if view_all_marker not in va:
        va += """

/* VIEW-ALL-BTN */
.view-all-btn-wrap {
    text-align: center;
    margin: 8px 0 16px;
}
.view-all-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 22px;
    background: linear-gradient(135deg, #009688, #00bcd4);
    color: #fff !important;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    box-shadow: 0 2px 8px rgba(0, 150, 136, 0.25);
    transition: transform 0.2s, box-shadow 0.2s;
}
.view-all-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(0, 150, 136, 0.4);
    color: #fff !important;
}
body.dark .view-all-btn {
    background: linear-gradient(135deg, #00bcd4, #009688);
}
"""
        with open(view_all_path, 'w', encoding='utf-8') as f:
            f.write(va)
        print('Added view-all-btn CSS')
else:
    print('my.css not found')

# --- 17. All-posts page header (替代 bg-cover) ---
all_page_marker = '/* ALL-PAGE-HEADER */'
all_page_path = os.path.join(theme_dir, 'source', 'css', 'my.css')
if os.path.exists(all_page_path):
    with open(all_page_path, encoding='utf-8') as f:
        ap = f.read()
    if all_page_marker not in ap:
        ap += """

/* ALL-PAGE-HEADER */
.all-page {
    padding-top: 20px;
}
.all-page-header {
    text-align: center;
    padding: 30px 20px 20px;
    margin-bottom: 10px;
}
.all-page-header h1 {
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0 0 8px;
    color: #333;
}
.all-page-subtitle {
    color: #888;
    font-size: 14px;
    margin: 0 0 16px;
}
.all-page-back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 18px;
    background: linear-gradient(135deg, #009688, #00bcd4);
    color: #fff !important;
    border-radius: 18px;
    font-size: 13px;
    text-decoration: none !important;
    box-shadow: 0 2px 8px rgba(0, 150, 136, 0.25);
    transition: transform 0.2s, box-shadow 0.2s;
}
.all-page-back:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(0, 150, 136, 0.4);
    color: #fff !important;
}
body.dark .all-page-header h1 { color: #ddd; }
body.dark .all-page-subtitle { color: #aaa; }
"""
        with open(all_page_path, 'w', encoding='utf-8') as f:
            f.write(ap)
        print('Added all-page-header CSS')
else:
    print('my.css not found')

# --- 18. Recommended page layout improvements ---
rec_marker = '/* REC-PAGE-LAYOUT */'
rec_path = os.path.join(theme_dir, 'source', 'css', 'my.css')
if os.path.exists(rec_path):
    with open(rec_path, encoding='utf-8') as f:
        rc = f.read()
    if rec_marker not in rc:
        rc += """

/* REC-PAGE-LAYOUT */
.rec-page-header {
    padding: 24px 20px 8px;
    margin-bottom: 4px;
    text-align: center;
}
.rec-page-nav {
    display: inline-flex;
    gap: 16px;
    align-items: center;
}
.rec-page-back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 22px;
    background: rgba(0,0,0,0.08);
    color: #444 !important;
    border-radius: 22px;
    font-size: 15px;
    font-weight: 500;
    text-decoration: none !important;
    transition: background 0.2s, transform 0.2s;
}
.rec-page-back:hover {
    background: rgba(0,0,0,0.16);
    color: #222 !important;
    transform: translateX(-2px);
}
.rec-page-all-top {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 22px;
    background: linear-gradient(135deg, #009688, #00bcd4);
    color: #fff !important;
    border-radius: 22px;
    font-size: 15px;
    font-weight: 500;
    text-decoration: none !important;
    box-shadow: 0 2px 10px rgba(0, 150, 136, 0.3);
    transition: transform 0.2s, box-shadow 0.2s;
}
.rec-page-all-top:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0, 150, 136, 0.45);
    color: #fff !important;
}
body.dark .rec-page-all-top {
    background: linear-gradient(135deg, #00bcd4, #009688);
}
.rec-section-title {
    text-align: center;
    font-size: 1.3rem;
    font-weight: 600;
    margin: 18px 10px 6px;
    color: #555;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
}
.rec-section-count {
    font-size: 13px;
    font-weight: 400;
    color: #999;
}
.rec-page-actions {
    text-align: center;
    margin: 24px 0 36px;
}
.rec-page-all-btn {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 14px 40px;
    background: linear-gradient(135deg, #009688, #00bcd4);
    color: #fff !important;
    border-radius: 26px;
    font-size: 17px;
    font-weight: 500;
    text-decoration: none !important;
    box-shadow: 0 4px 16px rgba(0, 150, 136, 0.35);
    transition: transform 0.2s, box-shadow 0.2s;
}
.rec-page-all-btn:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 22px rgba(0, 150, 136, 0.5);
    color: #fff !important;
}
body.dark .rec-page-back { background: rgba(255,255,255,0.1); color: #ccc !important; }
body.dark .rec-page-back:hover { background: rgba(255,255,255,0.2); color: #fff !important; }
body.dark .rec-section-title { color: #bbb; }

/* /recommended/ 页面背景: 首页风格的渐变(顶部青绿, 渐隐到白) */
main.rec-page {
    background: linear-gradient(180deg,
        rgba(0, 150, 136, 0.10) 0%,
        rgba(0, 188, 212, 0.05) 25%,
        transparent 100%);
    min-height: 100vh;
    padding-top: 4px;
}
.rec-page-header {
    background: linear-gradient(135deg, rgba(0, 150, 136, 0.15), rgba(0, 188, 212, 0.10));
    border-radius: 0 0 28px 28px;
    padding: 28px 20px 20px;
    margin-bottom: 10px;
    margin-top: 0;
}

"""
        with open(rec_path, 'w', encoding='utf-8') as f:
            f.write(rc)
        print('Added rec-page-layout CSS')
else:
    print('my.css not found')
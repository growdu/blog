#!/usr/bin/env python3
"""Prepare the matery theme:
1. Remove the default menu so _config.matery.yml is the sole source.
2. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams.
3. Inject Gitalk comments into post pages.
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

# --- 2. Inject prism.js CSS + Mermaid.js for code highlighting and diagrams ---
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

# --- 3. Inject Gitalk comments into post pages ---
partial_dir = os.path.join(theme_dir, 'layout', '_partial')
os.makedirs(partial_dir, exist_ok=True)

# The inner card-only partial (for injection INSIDE an existing container)
gitalk_card_ejs = """<% if (theme.gitalk && theme.gitalk.enable) { %>
<div class="card" data-aos="fade-up">
  <div class="card-content">
    <% if (theme.gitalk.clientID && theme.gitalk.clientID.length > 0) { %>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.css">
    <div id="gitalk-container"></div>
    <script src="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.min.js"></script>
    <script>
      var pathHash = function(s) {
        var h = 0;
        for (var i = 0; i < s.length; i++) {
          h = ((h << 5) - h) + s.charCodeAt(i); h |= 0;
        }
        return 'p' + Math.abs(h);
      };
      var gitalk = new Gitalk({
        clientID: '<%= theme.gitalk.clientID %>',
        clientSecret: '<%= theme.gitalk.clientSecret %>',
        repo: '<%= theme.gitalk.repo %>',
        owner: '<%= theme.gitalk.owner %>',
        admin: ['<%= theme.gitalk.owner %>'],
        id: pathHash(location.pathname),
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
print('Created gitalk-card.ejs (card-only)')

# The full-wrapper partial (for injection OUTSIDE any container)
gitalk_full_ejs = """<% if (theme.gitalk && theme.gitalk.enable) { %>
<main class="content">
  <div class="container">
    <%- partial('_partial/gitalk-card') %>
  </div>
</main>
<% } %>"""

with open(os.path.join(partial_dir, 'gitalk-comments.ejs'), 'w', encoding='utf-8') as f:
    f.write(gitalk_full_ejs)
print('Created gitalk-comments.ejs (full wrapper)')

# Remove theme's built-in gitalk references to avoid duplicate comment sections
post_detail = os.path.join(theme_dir, 'layout', '_partial', 'post-detail.ejs')
if os.path.isfile(post_detail):
    with open(post_detail, encoding='utf-8') as f:
        pd = f.read()
    original = pd
    for pat in ['<%- partial("_partial/gitalk") %>', "<%- partial('_partial/gitalk') %>"]:
        pd = pd.replace(pat, '')
    if pd != original:
        with open(post_detail, 'w', encoding='utf-8') as f:
            f.write(pd)
        print('Removed theme built-in gitalk from _partial/post-detail.ejs')


def inject_partial(filepath, partial_ref, markers):
    """Insert partial_ref into filepath before the first line matching any marker.
    markers: list of substrings to search for (tried in order).
    Returns True if injected, False if file not found or already present."""
    if not os.path.isfile(filepath):
        print(f'  {os.path.relpath(filepath, theme_dir)} not found')
        return False
    with open(filepath, encoding='utf-8') as f:
        raw = f.read()
    if 'gitalk' in raw:
        print(f'  gitalk already present in {os.path.relpath(filepath, theme_dir)}')
        return True
    lines = raw.split('\n')
    insert_idx = None
    for marker in markers:
        for i, line in enumerate(lines):
            if marker in line:
                insert_idx = i
                print(f'  Found "{marker}" at line {i+1} in {os.path.relpath(filepath, theme_dir)}')
                break
        if insert_idx is not None:
            break
    if insert_idx is None:
        insert_idx = len(lines)
        print(f'  No marker found, appending at end of {os.path.relpath(filepath, theme_dir)}')
    lines.insert(insert_idx, partial_ref)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  Injected into {os.path.relpath(filepath, theme_dir)} at line {insert_idx+1}')
    return True


# Strategy: inject the card-only partial into post-detail.ejs (which contains
# the article body and typically prev-next inside the same container).
# This guarantees the comment card shares the article's container width.
print('--- Injecting gitalk ---')
card_ref = '<%- partial("_partial/gitalk-card") %>'
full_ref = '<%- partial("_partial/gitalk-comments") %>'

# Try post-detail.ejs first (article body lives here, inside main.content > container)
done = inject_partial(
    post_detail, card_ref,
    ['prev-next', 'prev_next', 'post-prev', 'pager', 'paging']
)

if not done:
    # Fallback: inject full-wrapper into post.ejs
    post_layout = os.path.join(theme_dir, 'layout', 'post.ejs')
    done = inject_partial(
        post_layout, full_ref,
        ['prev-next', 'prev_next', 'post-prev', 'pager', 'paging', 'post-detail']
    )

if not done:
    print('WARNING: could not find a post layout to inject gitalk into')

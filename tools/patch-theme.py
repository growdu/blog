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

gitalk_ejs = (
    '<% if (theme.gitalk && theme.gitalk.enable && theme.gitalk.clientID) { %>\n'
    '<div class="container" style="margin-top: 30px; margin-bottom: 30px;">\n'
    '  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.css">\n'
    '  <div id="gitalk-container"></div>\n'
    '  <script src="https://cdn.jsdelivr.net/npm/gitalk@1/dist/gitalk.min.js"></script>\n'
    '  <script>\n'
    '    var pathHash = function(s) {\n'
    '      var h = 0;\n'
    '      for (var i = 0; i < s.length; i++) {\n'
    '        h = ((h << 5) - h) + s.charCodeAt(i); h |= 0;\n'
    '      }\n'
    '      return \'p\' + Math.abs(h);\n'
    '    };\n'
    '    var gitalk = new Gitalk({\n'
    '      clientID: \'<%= theme.gitalk.clientID %>\',\n'
    '      clientSecret: \'<%= theme.gitalk.clientSecret %>\',\n'
    '      repo: \'<%= theme.gitalk.repo %>\',\n'
    '      owner: \'<%= theme.gitalk.owner %>\',\n'
    '      admin: [\'<%= theme.gitalk.owner %>\'],\n'
    '      id: pathHash(location.pathname),\n'
    '      distractionFreeMode: false,\n'
    '      language: \'zh-CN\'\n'
    '    });\n'
    '    gitalk.render(\'gitalk-container\');\n'
    '  </script>\n'
    '</div>\n'
    '<% } %>'
)
with open(os.path.join(partial_dir, 'gitalk.ejs'), 'w', encoding='utf-8') as f:
    f.write(gitalk_ejs)
print('Created gitalk partial')

post_detail_path = os.path.join(theme_dir, 'layout', 'post-detail.ejs')
if os.path.isfile(post_detail_path):
    with open(post_detail_path, encoding='utf-8') as f:
        pd = f.read()
    if 'gitalk' not in pd and 'giscus' not in pd:
        pd += '\n<%- partial("_partial/gitalk") %>\n'
        with open(post_detail_path, 'w', encoding='utf-8') as f:
            f.write(pd)
        print('Injected gitalk into post-detail.ejs')
    elif 'giscus' in pd:
        pd = pd.replace('<%- partial("_partial/giscus") %>', '<%- partial("_partial/gitalk") %>')
        with open(post_detail_path, 'w', encoding='utf-8') as f:
            f.write(pd)
        print('Replaced giscus with gitalk in post-detail.ejs')

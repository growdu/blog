#!/usr/bin/env python3
"""
Transform Hugo-style docs/ content into Hexo source/ directory.

Creates:
  source/_posts/  - markdown posts with Hexo front matter
  source/images/  - all images from docs/ (paths rewritten to images/...)

Does NOT modify docs/ — runs in CI on a fresh checkout.
"""
import os, re, shutil, subprocess, sys

DOCS = 'docs'
SRC = 'source'
POSTS = os.path.join(SRC, '_posts')
IMGS = os.path.join(SRC, 'images')
IMG_EXT = {'.png','.jpg','.jpeg','.gif','.svg','.webp','.bmp','.ico'}

# Posts to feature in the homepage recommend section (relative to docs/)
# Higher top value = shown first in the recommend carousel
FEATURED_POSTS = {
    '00-intro.md': 100,
    '01-how_to_learn_program.md': 90,
    'cluster/分布式存储需要解决的问题.md': 85,
    'es/oh-my-search.md': 80,
    'db/logical_decode/逻辑解码DDL-Replay框架设计/index.md': 75,
    'cluster/DCF/一文读懂openguass dcf网络模块.md': 70,
    'cluster/分布式一致性协议.md': 65,
    'cluster/分布式系统设计必知必会.md': 60,
    'pgsql/postgresql基操.md': 55,
    'linux/linux内核指北.md': 50,
    'dpdk/dpdk常用接口指北.md': 45,
    'docker/docker基础指北.md': 40,
    'ai/07_ChatGPT为什么能对话一篇引用17万次的论文.md': 35,
    'db/logical_decode/逻辑解码/index.md': 30,
    'language/rust/rust设计原则.md': 25,
    'tools/那些你不得不会的提高工作效率的软件神器.md': 20,
    'network/从原理到实践，彻底告别 IPv6 上网不稳定的问题.md': 15,
    'ai/01_开场白目录.md': 10,
}


def read_section_categories():
    """Map section dir -> Chinese display name from _index.md."""
    cats = {}
    for section in os.listdir(DOCS):
        idx = os.path.join(DOCS, section, '_index.md')
        if not os.path.isfile(idx):
            continue
        with open(idx, encoding='utf-8') as f:
            txt = f.read()
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', txt, re.MULTILINE)
        if m:
            cats[section] = m.group(1).strip()
    return cats


def git_date(filepath):
    """Get the earliest commit date across ALL branches.

    Files migrated from repo root to docs/ and some were converted from
    single .md files to page bundles (dir/index.md), so we search
    multiple historical path candidates on every branch."""
    rel = os.path.relpath(filepath, DOCS)
    candidates = [f'docs/{rel}', rel]
    if os.path.basename(filepath) == 'index.md':
        parent = os.path.dirname(rel)
        if parent:
            candidates.append(f'docs/{parent}.md')
            candidates.append(f'{parent}.md')
    earliest = None
    for path in candidates:
        try:
            r = subprocess.run(
                ['git', 'log', '--all', '--reverse', '--format=%ai', '--', path],
                capture_output=True, text=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                d = r.stdout.strip().split('\n')[0].strip()
                if earliest is None or d < earliest:
                    earliest = d
        except Exception:
            continue
    if not earliest:
        return '2024-01-01 00:00:00'
    # Drop the trailing `+0800` / `+0000` offset.  Hexo's date path
    # generation goes through `node_modules/hexo/dist/plugins/processor/
    # common.js:51` `timezone()` which double-applies the offset when
    # the CI container TZ is UTC, shifting dates by one day for any
    # article that crosses UTC midnight.  Emitting a wall-clock string
    # without offset (and clearing `timezone:` in _config.yml) keeps
    # the rendered Y/M/D identical to the author-time wall clock.
    return earliest.split(' +')[0].split(' -')[0]


def extract_title(content):
    m = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else None


def fallback_title(filepath):
    base = os.path.splitext(os.path.basename(filepath))[0]
    if base == 'index':
        return os.path.basename(os.path.dirname(filepath))
    return base


def split_fm(content):
    """Return (fm_text, body). fm_text=None if no front matter."""
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n', content, re.DOTALL)
    if m:
        return m.group(1), content[m.end():]
    m = re.match(r'^---\r?\n---\r?\n', content)
    if m:
        return '', content[m.end():]
    return None, content


def has_fm_title(fm):
    return fm is not None and bool(re.search(r'^title\s*:', fm, re.MULTILINE))


def yaml_escape(s):
    return s.replace('\\','\\\\').replace('"','\\"')


def rewrite_images(content, file_dir):
    """Rewrite ![alt](rel_path) -> ![alt](images/<resolved>)."""
    def repl(m):
        alt, path = m.group(1), m.group(2)
        if path.startswith(('http://','https://','data:','#')):
            return m.group(0)
        path = path.lstrip('./')
        resolved = os.path.normpath(os.path.join(file_dir, path))
        return f'![{alt}](images/{resolved})'
    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, content)


def copy_images():
    for root, _, files in os.walk(DOCS):
        for f in files:
            if os.path.splitext(f)[1].lower() in IMG_EXT:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, DOCS)
                dst = os.path.join(IMGS, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)


def process(filepath, cats):
    rel = os.path.relpath(filepath, DOCS)
    fdir = os.path.dirname(rel)

    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    if os.path.basename(filepath) == '_index.md':
        return False

    fm, body = split_fm(content)
    src = body if fm is not None else content

    title = extract_title(src) or fallback_title(filepath)
    if has_fm_title(fm):
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE)
        if m:
            title = m.group(1).strip()

    date = git_date(filepath)
    section = rel.split(os.sep)[0] if os.sep in rel else ''
    cat = cats.get(section, section or '随笔')

    # rewrite images, strip first H1 (title is in front matter)
    body_out = rewrite_images(src, fdir)
    body_out = re.sub(r'^#\s+.+\n?', '', body_out, count=1, flags=re.MULTILINE)

    top_val = FEATURED_POSTS.get(rel)
    top_line = f'\ntop: {top_val}' if top_val else ''
    fm_out = f'---\ntitle: "{yaml_escape(title)}"\ndate: {date}\nauthor: growdu{top_line}\ncategories:\n  - {cat}\ntags:\n  - {cat}\n---\n'

    if os.path.basename(filepath) == 'index.md':
        name = os.path.basename(os.path.dirname(filepath))
        parent = os.path.dirname(fdir)
        out = os.path.join(POSTS, parent, f'{name}.md')
    else:
        out = os.path.join(POSTS, fdir, os.path.basename(filepath))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(fm_out + body_out)
    return True
def process_html(filepath, cats):
    """Sync a .html (or .htm) file from docs/ into source/_posts/.

    Source files in docs/<section>/<name>.html become Hexo posts at
    source/_posts/<section>/<name>.html with no `layout` field, so
    they inherit `_config.yml`'s `default_layout: post`. The
    html renderer (scripts/html-renderer.js) strips the surrounding
    <html>/<head>/<body> wrapper; the resulting body lands in
    matery's `post.ejs` article slot, giving HTML posts the same
    header/footer/reward/comments/related/prev-next chrome as
    markdown posts — matching the user's "本来就是 html 格式"
    expectation: keep the rich HTML body, but surface it with the
    blog's normal chrome.

    Title extraction:
        1. <title>...</title> at the top of the file (case-insensitive).
        2. Stripping any inner HTML tags from the title.
        3. Fallback to filename (via fallback_title()).
    The <title> tag is stripped from the body after extraction so
    the rendered page does not carry it twice.

    Date: same git_date() walk as markdown posts.

    Images in the body are NOT rewritten — pass-through rendering
    keeps the HTML verbatim. Users who want images should reference
    them by absolute path (e.g. /blog/images/foo.png) or external URL,
    or place them next to the HTML file and reference them relatively.
    """
    rel = os.path.relpath(filepath, DOCS)
    fdir = os.path.dirname(rel)
    base = os.path.basename(filepath)

    if base in ('_index.html', '_index.htm'):
        return False

    with open(filepath, encoding='utf-8') as f:
        html_text = f.read()

    # title extraction from <title> tag (case-insensitive), with
    # optional inner HTML stripped.
    title_m = re.search(
        '<title[^>]*>(.*?)</title>',
        html_text, re.IGNORECASE | re.DOTALL,
    )
    title = None
    if title_m:
        inner = title_m.group(1)
        inner = re.sub(r'<[^>]+>', '', inner).strip()
        if inner:
            title = inner
    if not title:
        title = fallback_title(filepath)

    date = git_date(filepath)
    section = rel.split(os.sep)[0] if os.sep in rel else ''
    cat = cats.get(section, section or '随笔')

    top_val = FEATURED_POSTS.get(rel)
    top_line = f'\ntop: {top_val}' if top_val else ''
    fm_out = (
        f'---\n'
        f'title: "{yaml_escape(title)}"\n'
        f'date: {date}\n'
        f'author: growdu{top_line}\n'
        f'categories:\n'
        f'  - {cat}\n'
        f'tags:\n'
        f'  - {cat}\n'
        f'---\n'
    )

    body_out = html_text
    if title_m:
        body_out = re.sub(
            r'<title[^>]*>.*?</title>',
            '',
            body_out,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Rename the file (not the front matter title) so hexo\'s filename-
    # derived slug carries a -html suffix.  Hexo 7\'s post processor
    # sets `data.slug = info.title` from the filename, OVERWRITING any
    # `slug:` value set in the front matter (see node_modules/hexo/dist/
    # plugins/processor/post.js line 49: `data.slug = info.title;`).
    # The suffix keeps HTML posts out of any markdown twin\'s permalink
    # without relying on a front-matter field that hexo silently ignores.
    out_base, out_ext = os.path.splitext(base)
    if out_base.endswith('-html'):
        out_basename = base
    else:
        out_basename = f'{out_base}-html{out_ext}'

    if base in ('index.html', 'index.htm'):
        name = os.path.basename(os.path.dirname(filepath))
        parent = os.path.dirname(fdir)
        out = os.path.join(POSTS, parent, out_basename)
    else:
        out = os.path.join(POSTS, fdir, out_basename)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(fm_out + body_out)
    return True


def create_theme_pages():
    """Create Hexo pages that the matery theme expects for the
    categories and tags overview pages.  hexo-generator-category/tag
    only produce per-category/per-tag pages, not the index listing."""
    pages = [
        ('categories/index.md', '分类', 'categories'),
        ('tags/index.md', '标签', 'tags'),
    ]
    for rel, title, layout in pages:
        path = os.path.join(SRC, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fm = f'---\ntitle: {title}\ndate: 2024-01-01 00:00:00\ntype: "{layout}"\nlayout: "{layout}"\n---\n\n'
        with open(path, 'w', encoding='utf-8') as f:
            f.write(fm)

    # About page
    about_path = os.path.join(SRC, 'about', 'index.md')
    os.makedirs(os.path.dirname(about_path), exist_ok=True)
    about_md = """---
title: "关于我"
date: 2026-07-29 00:00:00
---

# 关于我

资深后端研发工程师，专注数据库内核与分布式系统。深耕 PostgreSQL/openGauss 内核开发，熟悉 DCF、Raft 等一致性协议，对 DPDK/VPP 高性能数据面有丰富实践经验。热爱技术分享，记录编程之路的每一步。

## GitHub 数据

<div id="gh-stats" class="gh-stats">
  <div class="gh-stat"><div class="gh-stat-num">--</div><div class="gh-stat-label">加载中</div></div>
</div>
<script>
fetch('https://api.github.com/users/growdu')
  .then(function(r){return r.json()})
  .then(function(d){
    var el=document.getElementById('gh-stats');
    if(el&&d) el.innerHTML=
      '<div class="gh-stat"><div class="gh-stat-num">'+d.public_repos+'</div><div class="gh-stat-label">公开仓库</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.followers+'</div><div class="gh-stat-label">关注者</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.following+'</div><div class="gh-stat-label">关注中</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+(d.created_at?d.created_at.substring(0,4):'--')+'</div><div class="gh-stat-label">加入GitHub</div></div>';
  })
  .catch(function(){});
</script>

## 技术栈

<div class="skill-bar">
  <div class="skill-row"><span>PostgreSQL / openGauss 内核开发</span><span>95%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:95%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>分布式一致性协议 (Raft / DCF)</span><span>90%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:90%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>C / C++ 系统编程</span><span>90%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:90%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>DPDK / VPP 高性能数据面</span><span>85%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:85%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>Linux 系统与网络编程</span><span>88%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:88%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>高可用集群架构设计</span><span>85%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:85%"></div></div>
</div>
<div class="skill-bar">
  <div class="skill-row"><span>Python / Shell 自动化</span><span>80%</span></div>
  <div class="skill-track"><div class="skill-fill" style="width:80%"></div></div>
</div>

## 重点项目

<div class="project-card">
  <div>
    <div class="proj-name">openGauss DCF 分布式一致性框架</div>
    <div class="proj-desc">深度参与 openGauss DCF (Distributed Consensus Framework) 模块开发，涉及投票系统、写入机制、运行机制等核心组件</div>
  </div>
</div>
<div class="project-card">
  <div>
    <div class="proj-name">逻辑解码 DDL Replay 框架</div>
    <div class="proj-desc">设计并实现逻辑解码 DDL 重放框架，支持 DDL 操作的逻辑复制</div>
  </div>
</div>
<div class="project-card">
  <div>
    <div class="proj-name">oh-my-search 搜索引擎</div>
    <div class="proj-desc">基于 Elasticsearch 构建的搜索解决方案</div>
  </div>
</div>
<div class="project-card">
  <div>
    <div class="proj-name">Corosync / Pacemaker 高可用集群</div>
    <div class="proj-desc">深入研究并实践 Corosync 仲裁系统、Pacemaker 集群资源管理，涉及 QDevice、Totem 协议等</div>
  </div>
</div>

## 编程之路

<div class="timeline-item">
  <div class="timeline-date">持续更新</div>
  <div>数据库内核开发、分布式系统设计、高性能网络编程的持续学习与实践</div>
</div>
<div class="timeline-item">
  <div class="timeline-date">核心技术方向</div>
  <div>PostgreSQL/openGauss 内核、DCF/Raft 一致性协议、DPDK/VPP 数据面、高可用架构</div>
</div>
<div class="timeline-item">
  <div class="timeline-date">知识沉淀</div>
  <div>473+ 篇技术笔记，涵盖数据库、分布式系统、算法、网络、编程基础等领域</div>
</div>

## 联系方式

- **GitHub**: https://github.com/growdu
- **Email**: growdu@gmail.com
- **QQ**: 2689304284

## 关于本博客

本博客记录编程之路的学习笔记和技术实践，涵盖数据库、分布式系统、高性能网络等领域。文章通过 Git 提交自动发布，使用 Hexo + matery 主题构建，部署在 GitHub Pages。
"""
    with open(about_path, 'w', encoding='utf-8') as f:
        f.write(about_md)


def main():
    # Preserve custom pages (source/all/, source/recommended/) across regeneration
    import tempfile
    preserved = tempfile.mkdtemp()
    all_path = os.path.join(SRC, 'all')
    rec_path = os.path.join(SRC, 'recommended')
    all_preserved = os.path.isdir(all_path)
    rec_preserved = os.path.isdir(rec_path)
    if all_preserved:
        shutil.move(all_path, os.path.join(preserved, 'all'))
    if rec_preserved:
        shutil.move(rec_path, os.path.join(preserved, 'recommended'))
    if os.path.exists(SRC):
        shutil.rmtree(SRC)
    if all_preserved:
        shutil.move(os.path.join(preserved, 'all'), all_path)
    if rec_preserved:
        shutil.move(os.path.join(preserved, 'recommended'), rec_path)
    shutil.rmtree(preserved)
    os.makedirs(POSTS)

    verification_dir = os.path.join(SRC, '.well-known')
    os.makedirs(verification_dir, exist_ok=True)
    verification_path = os.path.join(
        verification_dir, 'vercount-verify-zd5pj09shdfkbm6h83ra5zzk.txt'
    )
    with open(verification_path, 'w', encoding='utf-8') as f:
        f.write('vercount-domain-verify=growdu.github.io,zd5pj09shdfkbm6h83ra5zzk')
    print('Created Vercount verification file')

    cats = read_section_categories()
    print(f'Categories: {len(cats)}')

    copy_images()
    print('Images copied')

    n_md = 0
    n_html = 0
    for root, _, files in os.walk(DOCS):
        for f in sorted(files):
            ext = os.path.splitext(f)[1].lower()
            fp = os.path.join(root, f)
            try:
                if ext == '.md':
                    if process(fp, cats):
                        n_md += 1
                elif ext in ('.html', '.htm'):
                    # Naming convention: if an .html shares a basename
                    # with an .md in the same directory, the .html MUST
                    # carry a -html suffix (e.g. 'foo.html' ->
                    # 'foo-html.html') so the pair is visually distinct
                    # in the docs/ tree and the generated permalinks
                    # don't collide.  Detect violations here and fail
                    # loud — better to break the build than silently
                    # produce two posts with the same URL.
                    base_no_ext = os.path.splitext(f)[0]
                    if not base_no_ext.endswith('-html'):
                        twin_md = os.path.join(root, base_no_ext + '.md')
                        if os.path.isfile(twin_md):
                            print(
                                f'ERROR {fp}: shares basename with {twin_md} '
                                f'but is not suffixed with -html. Rename the .html '
                                f'file to {os.path.join(root, base_no_ext + "-html.html")} '
                                f'(see docs/blog/同名文章-html-与-md-版本管理.md).',
                                file=sys.stderr,
                            )
                            sys.exit(2)
                    if process_html(fp, cats):
                        n_html += 1
            except Exception as e:
                print(f'ERROR {fp}: {e}', file=sys.stderr)
    print(f'Markdown posts: {n_md}')
    print(f'HTML docs:      {n_html}')


    # robots.txt for SEO
    robots_path = os.path.join(SRC, 'robots.txt')
    with open(robots_path, 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nAllow: /\n\nSitemap: https://growdu.github.io/blog/sitemap.xml\n')
    print('Created robots.txt')


    # PWA manifest (re-include icons[] on every regen so a fresh CI
    # checkout doesn't silently drop the 48x48 favicon + 192x192 logo
    # entries; aa9cfb6 originally restored them after a similar bug).
    manifest_path = os.path.join(SRC, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('{\n  "name": "编程之路",\n  "short_name": "编程之路",\n  "description": "资深后端研发工程师的技术博客",\n  "start_url": "/blog/",\n  "display": "standalone",\n  "background_color": "#ffffff",\n  "theme_color": "#009688",\n  "lang": "zh-CN",\n  "icons": [\n    {\n      "src": "/blog/favicon.png",\n      "sizes": "48x48",\n      "type": "image/png"\n    },\n    {\n      "src": "/blog/medias/logo.jpg",\n      "sizes": "192x192",\n      "type": "image/jpeg"\n    }\n  ]\n}\n')
    print('Created manifest.json')

    # Custom SVG favicon (database icon)
    favicon_path = os.path.join(SRC, 'favicon.svg')
    with open(favicon_path, 'w', encoding='utf-8') as f:
        f.write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#009688"/><ellipse cx="32" cy="18" rx="16" ry="6" fill="none" stroke="#fff" stroke-width="2.5"/><path d="M16 18v14a16 6 0 0 0 32 0V18" fill="none" stroke="#fff" stroke-width="2.5"/><path d="M16 32v14a16 6 0 0 0 32 0V32" fill="none" stroke="#fff" stroke-width="2.5"/></svg>')
    print('Created favicon.svg')


    # Service worker for offline reading
    sw_path = os.path.join(SRC, 'sw.js')
    with open(sw_path, 'w', encoding='utf-8') as f:
        f.write("""const CACHE='blog-v3';self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==CACHE).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin)return;const put=async(req,res)=>{try{if(res&&res.status===200&&res.clone){await caches.open(CACHE).then(c=>c.put(req,res.clone()));}}catch(_){}};if(e.request.headers.get('accept')&&e.request.headers.get('accept').includes('text/html')){e.respondWith(fetch(e.request).then(r=>{put(e.request,r);return r;}).catch(()=>caches.match(e.request)));}else{e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request).then(r=>{put(e.request,r);return r;}).catch(()=>caches.match(e.request))));}});""")
    print('Created sw.js')


    # 404 page
    notfound_path = os.path.join(SRC, '404.html')
    with open(notfound_path, 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>404</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{display:flex;align-items:center;justify-content:center;min-height:100vh;background:linear-gradient(135deg,#f5f7fa,#c3cfe2);font-family:sans-serif}.box{text-align:center;padding:48px 40px;background:#fff;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,.1)}h1{font-size:80px;color:#009688;font-weight:800}p{color:#666;margin:16px 0 24px}a{display:inline-block;padding:10px 28px;background:#009688;color:#fff;text-decoration:none;border-radius:24px;font-weight:600}</style>
</head><body><div class="box"><h1>404</h1><p>抱歉，您访问的页面不存在</p><a href="/blog/">返回首页</a></div></body></html>""")
    print('Created 404.html')

    # Database landing page
    create_database_landing_page()
    print('Created database landing page')

def create_database_landing_page():
    """Copy the curated database landing page from tools/templates/ into
    Hexo's source/ tree. The template is plain markdown + front matter,
    editable in any editor with full syntax highlighting.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    template = os.path.join(here, 'templates', 'database.md')
    db_path = os.path.join(SRC, 'database', 'index.md')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with open(template, encoding='utf-8') as f:
        content = f.read()
    with open(db_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Created ' + os.path.relpath(db_path, '.'))



    # Projects page (custom page with card grid for growdu's GitHub projects)
    create_projects_page()
    print('Created projects landing page')

    create_theme_pages()
    print('Theme pages created')


def create_projects_page():
    """Generate the /projects/ page as a card grid of growdu's repos."""
    # All non-fork, non-archived growdu repos, sorted by latest commit.
    # Tuple: (name, description, language, stars, url).
    projects = [
        ('ai_all_in_one', '面向普通人的 AI 工具集合，封装主流大模型与办公 AI，一条命令跑起来。',                      'Go',        0, 'https://github.com/growdu/ai_all_in_one'),
        ('blog',         '博客站点源码，本仓库 Hexo + matery 主题的构建来源。',                                      'Python',    0, 'https://github.com/growdu/blog'),
        ('ai_toubiao',   'AI 招投标助手，自动解析招标文件、生成应答方案，提升售前效率。',                          'Go',        1, 'https://github.com/growdu/ai_toubiao'),
        ('growdu',       '个人 GitHub profile README 配置仓库。',                                                  '',          1, 'https://github.com/growdu/growdu'),
        ('ai_teacher',   'AI 教师视频工作室，自动生成教学视频、字幕与讲稿。',                                     'Java',      0, 'https://github.com/growdu/ai_teacher'),
        ('learn_pg',     'PostgreSQL 内核学习笔记，边读源码边注释，吃透关键模块。',                               'Go',        1, 'https://github.com/growdu/learn_pg'),
        ('dbt',          '日常数据库诊断与运维小工具合集，覆盖 PostgreSQL / openGauss 等场景。',                  'C',         0, 'https://github.com/growdu/dbt'),
        ('ebpf_all',     'eBPF 一站式学习与实验仓库，覆盖内核观测、网络、安全、性能等场景。',                    'Rust',      0, 'https://github.com/growdu/ebpf_all'),
        ('loving',       '提升生育率的小工具集合。',                                                              'Vue',       0, 'https://github.com/growdu/loving'),
        ('aistock',      '面向个人的 AI 量化交易，集成大模型的选股、回测与策略生成实验。',                         'Python',    1, 'https://github.com/growdu/aistock'),
        ('dbk',          'database kernel ai cli：让 AI 直接参与数据库内核开发、调试与性能分析的 CLI。',           'Python',    0, 'https://github.com/growdu/dbk'),
        ('Ace',          '千分/腰子分/百分等常见纸牌游戏的脚本与统计工具。',                                     'Makefile',  0, 'https://github.com/growdu/Ace'),
        ('ebpf_dev',     'eBPF 开发环境 Dockerfile，开箱即用的内核观测调试容器。',                                'Dockerfile',0, 'https://github.com/growdu/ebpf_dev'),
        ('children_study_guide', '孩子学习调优指南，整理从小学到高中各阶段的学习方法与资源。',                    'HTML',      0, 'https://github.com/growdu/children_study_guide'),
        ('db_god',       '数据库修仙之路，系统梳理数据库内核知识图谱，从单机存储到分布式事务。',                  'JavaScript',0, 'https://github.com/growdu/db_god'),
        ('docker-compose-home', '常用服务的 docker-compose 配置合集，可直接被 Dockge 等面板挂载。',               '',          0, 'https://github.com/growdu/docker-compose-home'),
        ('k8s_god',      'k8s 修仙指南，从零搭建、调优到生产化部署的全景实战笔记。',                             'JavaScript',0, 'https://github.com/growdu/k8s_god'),
        ('autotest',     '自动化测试脚本与样例合集，覆盖前后端常见场景。',                                        'JavaScript',0, 'https://github.com/growdu/autotest'),
        ('docusaurus_custom_table_width', 'Docusaurus 表格列宽自定义小插件，解决表格列内容截断问题。',           'JavaScript',0, 'https://github.com/growdu/docusaurus_custom_table_width'),
        ('java-work',    'Java 学习与测试代码，按专题整理常见用法与踩坑记录。',                                   'Java',      0, 'https://github.com/growdu/java-work'),
        ('docsify-blog', 'docsify 风格的博客模板，自动渲染 Markdown 目录，开箱即用。',                          'HTML',      0, 'https://github.com/growdu/docsify-blog'),
        ('anycode',      'database developer program anywhere：基于 Web 的在线数据库开发环境。',                  'Vue',       0, 'https://github.com/growdu/anycode'),
        ('dockerfile',   '日常 Dockerfile 集合，按用途分类便于复用。',                                           'Dockerfile',0, 'https://github.com/growdu/dockerfile'),
        ('db021',        '从零开始写数据库，手写存储引擎、SQL 解析与执行器。',                                   'C',         0, 'https://github.com/growdu/db021'),
        ('ctest',        'C 语言函数测试合集，涵盖常见系统调用与库函数的单元测试。',                             '',          0, 'https://github.com/growdu/ctest'),
        ('growdu.github.io', 'GitHub Pages 上的早期博客版本，hexo-renderer 与 matery 主题实践。',                  'JavaScript',1, 'https://github.com/growdu/growdu.github.io'),
        ('deploy_vps',   '一键部署 shadowsocks 的安装脚本与运维工具。',                                          'Shell',     0, 'https://github.com/growdu/deploy_vps'),
        ('auto_email',   '自动收发邮件机器人，基于规则与 AI 的邮件分类、回复与提醒。',                            'Python',    0, 'https://github.com/growdu/auto_email'),
        ('growdu.io',    'Hexo + matery 主题的博客源码，配套 GitHub Pages 部署实践。',                            'JavaScript',1, 'https://github.com/growdu/growdu.io'),
        ('easy_blog',    '将 GitHub 仓库一键变成可阅读博客，自动生成 Markdown 文章索引。',                         'Python',    1, 'https://github.com/growdu/easy_blog'),
        ('mofang',       '魔方相关的小实验与可视化页面。',                                                        'HTML',      0, 'https://github.com/growdu/mofang'),
        ('namer',        '随机起名小工具，支持多场景多风格。',                                                    'CSS',       0, 'https://github.com/growdu/namer'),
        ('leetcode',     'LeetCode 刷题笔记与模板代码，按专题整理常见套路与高频题解。',                          'C',         0, 'https://github.com/growdu/leetcode'),
        ('install-guide','开发工具的安装与配置指南，覆盖 macOS / Linux 常见环境。',                              '',          0, 'https://github.com/growdu/install-guide'),
        ('go-work',      'Go 语言学习与练习代码。',                                                               'Go',        0, 'https://github.com/growdu/go-work'),
        ('CSharpTest',   'C# 语言的测试与示例代码。',                                                             'C#',        1, 'https://github.com/growdu/CSharpTest'),
    ]



    def card(name, desc, lang, stars, url):
        initial = name[0].upper()
        lang_badge = ('<span class="proj-grid-lang">' + lang + '</span>') if lang else ''
        star = ('<span class="pg-stat"><i class="fa-solid fa-star"></i>' + str(stars) + '</span>') if stars > 0 else ''
        return (''.join([
            '<a class="proj-grid-card" href="' + url + '" target="_blank" rel="noopener">',
            '<div class="proj-grid-head">',
            '<div class="proj-grid-icon">' + initial + '</div>',
            '<div class="proj-grid-name">' + name + '</div>',
            lang_badge,
            '</div>',
            '<div class="proj-grid-desc">' + desc + '</div>',
            '<div class="proj-grid-foot">',
            star,
            '<span class="pg-link">查看仓库 →</span>',
            '</div>',
            '</a>'
        ]))

    cards_html = chr(10).join(card(*p) for p in projects)

    fm = '---\ntitle: 我的开源项目\ndate: 2026-07-29 00:00:00\ntype: "projects"\nlayout: "page"\n---\n\n'
    intro = chr(10).join([
        '# 我的开源项目',
        '',
        '这里收录了我在 GitHub 上开源的主要项目，覆盖数据库内核、eBPF、AI 工具、博客系统等多个方向。每个项目都配有独立仓库，欢迎前往围观、Star 或 Fork。',
        '',
        '> 数据来自 [github.com/growdu](https://github.com/growdu)，共 ' + str(len(projects)) + ' 个非 fork 项目，按最近提交时间排序。',
        '',
        '<div class="proj-grid">',
        cards_html,
        '</div>',
        '',
        '更多小实验和练手项目可以在 [GitHub 个人主页](https://github.com/growdu) 上翻到，欢迎一起交流。',
    ])

    proj_path = os.path.join(SRC, 'projects', 'index.md')
    os.makedirs(os.path.dirname(proj_path), exist_ok=True)
    with open(proj_path, 'w', encoding='utf-8') as f:
        f.write(fm + intro + chr(10))
    print('Created ' + os.path.relpath(proj_path, '.') + ' (' + str(len(projects)) + ' cards)')


if __name__ == '__main__':
    main()

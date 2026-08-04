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
    'cluster/分布式存储需要解决的问题.md': 80,
    'es/oh-my-search.md': 70,
    'db/logical_decode/逻辑解码DDL-Replay框架设计/index.md': 60,
    'cluster/DCF/一文读懂openguass dcf网络模块.md': 50,
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
    return earliest if earliest else '2024-01-01 00:00:00'


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
    source/_posts/<section>/<name>.html with front matter that has
    `layout: false` so the entire HTML body is published as a
    standalone page (matching the user's "本来就是 html 格式"
    expectation — the document is already formatted, just publish
    it).

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
    # Pin a stable slug that disambiguates from any markdown twin in the
    # same section.  hexo would otherwise lowercase the title and slugify
    # both `ddl同步架构.md` (title "ddl同步架构") and `ddl同步架构.html`
    # (title "DDL同步架构") to the same `ddl同步架构` slug, causing the
    # HTML file to overwrite the markdown file's permalink.  Suffixing
    # with -html makes the URL distinct (and it stays human-readable).
    slug = f'{title}-html'
    fm_out = (
        f'---\n'
        f'title: "{yaml_escape(title)}"\n'
        f'date: {date}\n'
        f'author: growdu{top_line}\n'
        f'slug: "{yaml_escape(slug)}"\n'
        f'categories:\n'
        f'  - {cat}\n'
        f'tags:\n'
        f'  - {cat}\n'
        f'layout: false\n'
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

    if base in ('index.html', 'index.htm'):
        name = os.path.basename(os.path.dirname(filepath))
        parent = os.path.dirname(fdir)
        out = os.path.join(POSTS, parent, f'{name}.html')
    else:
        out = os.path.join(POSTS, fdir, base)

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
    if os.path.exists(SRC):
        shutil.rmtree(SRC)
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


    # PWA manifest
    manifest_path = os.path.join(SRC, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('{"name":"编程之路","short_name":"编程之路","description":"资深后端研发工程师的技术博客","start_url":"/blog/","display":"standalone","background_color":"#ffffff","theme_color":"#009688","lang":"zh-CN"}')
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
    """Generate a rich database landing page that reflects growdu's
    day-to-day work as a database kernel engineer (PostgreSQL /
    openGauss DCF / 分布式一致性)."""
    db_path = os.path.join(SRC, 'database', 'index.md')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    fm = '---\ntitle: 数据库专题\ndate: 2026-07-29 00:00:00\ntype: "database"\nlayout: "page"\n---\n\n'

    lines = [
        '# 数据库专题',
        '',
        '> 数据库内核是计算机系统软件中最复杂的领域之一。本专题收录我在 PostgreSQL / openGauss 内核开发、分布式一致性（Raft / DCF）、逻辑解码与双向同步、存储引擎等方向的实战笔记与源码解读，希望对同样走在这条路上的同行有所启发。',
        '',
        '作为长期在 PostgreSQL 与 openGauss 内核一线搬砖的工程师，我日常的工作内容大致涵盖：**内核源码阅读与 Bug 定位**、**新特性设计（如 DDL-Replay 双向同步）**、**分布式一致性模块开发（DCF / Raft）**、**性能调优与故障排查**。下面把博客里相关的文章按主题串成一张导览图，方便按需取用。',
        '',
        '## 核心技术栈',
        '',
        '<div class="db-skill-grid">',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">PostgreSQL 内核</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:95%"></div></div>',
        '    <div class="db-skill-meta">进程模型 · 存储引擎 · WAL · 复制 · 执行器 · MVCC</div>',
        '  </div>',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">openGauss / DCF</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:90%"></div></div>',
        '    <div class="db-skill-meta">分布式一致性 · 日志复制 · 投票机制 · 网络模块</div>',
        '  </div>',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">分布式协议</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:88%"></div></div>',
        '    <div class="db-skill-meta">Raft · 多数派 · Quorum 动态调整 · Leader 选举</div>',
        '  </div>',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">逻辑解码与双向同步</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:85%"></div></div>',
        '    <div class="db-skill-meta">pgoutput · pglogical · DDL-Replay · 跨版本迁移</div>',
        '  </div>',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">多数据库架构对比</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:80%"></div></div>',
        '    <div class="db-skill-meta">PostgreSQL / MySQL / SQLServer / TDengine 横向评测</div>',
        '  </div>',
        '  <div class="db-skill-card">',
        '    <div class="db-skill-name">性能调优与故障排查</div>',
        '    <div class="db-skill-bar"><div class="db-skill-fill" style="width:85%"></div></div>',
        '    <div class="db-skill-meta">Checkpoint · WAL · 锁等待 · 慢 SQL · 崩溃恢复</div>',
        '  </div>',
        '</div>',
        '',
        '## 学习路径建议',
        '',
        '如果你刚接触数据库内核开发，建议按下面这条路线循序渐进，每一档都附上对应的站内文章入口：',
        '',
        '1. **入门**：[PostgreSQL 基操](/blog/categories/PostgreSQL/) → [源码编译](/blog/tags/源码编译/) → [启动流程](/blog/tags/启动流程/)。先把一份能跑、能断点的内核源码环境搭起来。',
        '2. **存储与 WAL**：[FSM 文件解析](/blog/tags/存储/) → [full_page_writes](/blog/tags/full_page_writes/) → [WAL 机制浅析](/blog/tags/wal/) → [崩溃恢复](/blog/tags/崩溃恢复/)。理解"数据页 + WAL + 检查点"这一数据库的基石三角。',
        '3. **进程与执行器**：[BgWriter](/blog/tags/BgWriter/) → [Checkpoint](/blog/tags/Checkpoint/) → [WalWriter](/blog/tags/WalWriter/) → [insert 语句执行过程](/blog/tags/executor/)。把后台进程和查询执行的主干打通。',
        '4. **复制与高可用**：[流复制与 WAL 日志](/blog/tags/复制/) → [同步流复制原理](/blog/tags/同步流复制/) → [WalReceiver / WalSender 交互](/blog/tags/WalReceiver/) → [repmgr 实现原理](/blog/tags/repmgr/) → [伪双写](/blog/tags/伪双写/)。',
        '5. **事务与并发控制**：[事务管理](/blog/tags/事务管理/) → [并发控制](/blog/tags/并发控制/) → [MVCC 源码解读](/blog/tags/MVCC/) → [锁等待排查](/blog/tags/锁/)。',
        '6. **逻辑解码与双向同步**：[逻辑复制源码分析](/blog/tags/逻辑复制/) → [PG15 逻辑复制支持 DDL](/blog/tags/逻辑解码/) → [pglogical 详解](/blog/tags/pglogical/) → [DDL-Replay 框架设计](/blog/tags/DDL-Replay/) → [AI 逻辑解码](/blog/tags/AI/)。',
        '7. **分布式一致性**：[Raft 重要概念](/blog/tags/Raft/) → [一文读懂 openGauss DCF 网络模块](/blog/tags/DCF/) → [DCF 投票系统详解](/blog/tags/DCF/) → [DCF 运行机制](/blog/tags/DCF/) → [DCF 写入机制](/blog/tags/DCF/) → [Raft 协议动态调整 quorum](/blog/tags/Raft/)。',
        '',
        '## 专题导览',
        '',
        '### PostgreSQL 内核',
        '',
        'PostgreSQL 是研究数据库内核最好的教科书。本节文章覆盖源码结构、进程模型、执行器、统计信息、对象管理等。',
        '',
        '- [PostgreSQL 主结构](/blog/tags/PostgreSQL/) — 一张图看懂内核子目录划分与启动链路。',
        '- [postmaster 启动代码解析（--boot / --single）](/blog/tags/postmaster/) — 两个特殊启动模式的差异与适用场景。',
        '- [PostgreSQL 时间线解析](/blog/tags/PostgreSQL/) — 时间线（Timeline）在 PITR 与复制里的关键作用。',
        '- [源码对象管理](/blog/tags/源码/) — pg_class / pg_attribute / pg_type 背后的对象系统。',
        '- [触发器详解](/blog/tags/触发器/) — 行级 / 语句级触发器的执行时机与性能开销。',
        '- [统计信息](/blog/tags/统计信息/) — pg_stat 系列视图与查询规划器的统计来源。',
        '- [扩展机制（pg_extension）](/blog/tags/扩展/) — contrib 与第三方扩展的工作方式。',
        '- [pg_io_调优](/blog/tags/性能调优/) — 内核视角的 I/O 配置与诊断。',
        '',
        '### 存储与 WAL',
        '',
        '存储引擎是数据库最核心的子系统。下面的文章从页结构、FSM、VM 一直追到 WAL、checkpoint、崩溃恢复。',
        '',
        '- [PostgreSQL 存储总览](/blog/tags/存储/) — 表 / 索引 / toast 文件的组织方式。',
        '- [FSM 文件解析](/blog/tags/FSM/) — Free Space Map 的页面级空间管理。',
        '- [full_page_writes](/blog/tags/full_page_writes/) — 为什么需要整页写入，以及关掉它的代价。',
        '- [WAL 机制浅析](/blog/tags/WAL/) — XLOG 记录格式、LSN、刷盘策略。',
        '- [pg_checksum](/blog/tags/pg_checksum/) — 数据页校验开启与性能影响。',
        '- [共享内存](/blog/tags/共享内存/) — shmem、clog、subtrans 等共享数据结构。',
        '- [数据库崩溃恢复](/blog/tags/崩溃恢复/) — REDO 流程与一致性恢复原理。',
        '- [数据表文件底层结构布局分析](/blog/tags/存储/) — heap page 的物理布局与 tuple 指针。',
        '',
        '### 复制与高可用',
        '',
        '从物理复制、逻辑复制到 repmgr 自动化与伪双写方案，把可用性这一块的内容一次说清。',
        '',
        '- [PostgreSQL 流复制与 WAL 日志](/blog/tags/流复制/) — 物理复制的核心链路。',
        '- [同步流复制原理与代码浅析](/blog/tags/同步流复制/) — synchronous_commit 与多数派同步。',
        '- [流复制同异步分析](/blog/tags/异步复制/) — async / sync / remote_apply 的取舍。',
        '- [WalReceiver 与 Startup 交互](/blog/tags/WalReceiver/) — 备机启动、回放与晋升流程。',
        '- [WalSender 源码分析](/blog/tags/WalSender/) — 主机的复制槽管理。',
        '- [复制槽实操](/blog/tags/复制槽/) — 防止 WAL 被过早回收的实战经验。',
        '- [repmgr 实现原理](/blog/tags/repmgr/) — 自动 failover 与 witness 节点。',
        '- [HAProxy 支持 PostgreSQL 伪双写](/blog/tags/HAProxy/) — 双写避免脑裂的工程方案。',
        '- [PostgreSQL 伪双写](/blog/tags/伪双写/) — 在没有共享存储的情况下做"类双活"。',
        '- [详解完整恢复及基于时间点的恢复（PITR）](/blog/tags/PITR/) — backup_label 与 recovery_target 的关系。',
        '',
        '### 事务与并发控制',
        '',
        'MVCC 是 PostgreSQL 的灵魂，事务与并发控制则是工程化路上最容易踩坑的子系统。',
        '',
        '- [事务管理](/blog/tags/事务管理/) — xid 分配、CLOG、Hint Bits。',
        '- [并发控制](/blog/tags/并发控制/) — 行级锁、表级锁、Advisory Lock 与死锁检测。',
        '- MVCC 实现细节 — 通过 HeapTupleHeader 的 xmin/xmax 跟踪事务可见性。',
        '- 多版本可见性判断 — HeapTupleSatisfiesXXX 系列宏的实现。',
        '- 两阶段提交与 PREPARE TRANSACTION — 跨库分布式事务的落地方式。',
        '- 锁等待排查 — pg_stat_activity / pg_locks 的联合诊断套路。',
        '',
        '### 逻辑解码与双向同步',
        '',
        '这是我个人投入最多的方向：从最初梳理逻辑复制源码，到后来为内核加上 DDL 同步支持，整个过程沉淀在这里。',
        '',
        '- [逻辑复制源码分析](/blog/tags/逻辑复制/) — pgoutput plugin 与 reorder buffer。',
        '- [PostgreSQL 逻辑复制 - DML](/blog/tags/逻辑复制/) — 从 WAL 到逻辑变更的转换路径。',
        '- [PG15 逻辑复制支持 DDL](/blog/tags/逻辑解码/) — 内核侧为 DDL 同步打下的底座。',
        '- [pglogical 详解](/blog/tags/pglogical/) — 第三方双向同步方案的核心机制。',
        '- [逻辑解码 DDL-Replay 框架设计](/blog/tags/DDL-Replay/) — 自研框架的整体架构。',
        '- [DDL 同步架构](/blog/tags/双向同步/) — 同构、异构数据库之间的 DDL 同步模式。',
        '- [AI 逻辑解码](/blog/tags/AI/) — 把大模型引入逻辑解码，自动修复 DDL 不一致。',
        '- [LogLogicalMessage 详解](/blog/tags/LogLogicalMessage/) — 自定义消息通道的协议细节。',
        '- [polardb 逻辑解码源码解读](/blog/tags/polardb/) — 阿里 PolarDB 在逻辑解码上的增强。',
        '',
        '### openGauss DCF（分布式一致性框架）',
        '',
        "openGauss 的 DCF 是国内为数不多的工业级 Multi-Paxos 实现，与 etcd / braft 在工程思路上异曲同工。这组文章从网络层一路拆到投票层。",
        '',
        '- [一文读懂 openGauss DCF 网络模块](/blog/tags/DCF/) — TCP/QUIC 选型、心跳与连接管理。',
        '- [DCF 网络模块详解](/blog/tags/DCF/) — 报文编解码、连接复用、批量发送。',
        '- [DCF 运行机制](/blog/tags/DCF/) — 节点生命周期与角色切换。',
        '- [DCF 写入机制](/blog/tags/DCF/) — 从客户端写入到多数派落盘的全链路。',
        '- [DCF 投票系统详解](/blog/tags/DCF/) — Leader 选举与 Term 管理。',
        '- [openGauss 源码阅读](/blog/tags/openGauss/) — DCF 周边模块的辅助阅读笔记。',
        '- [openGauss 技术架构](/blog/tags/openGauss/) — 整体架构、存储、SQL 引擎的鸟瞰。',
        '- [常用压缩算法编程](/blog/tags/压缩/) — DCF 日志压缩所用到的基础算法。',
        '',
        '### 分布式协议（Raft / 一致性）',
        '',
        '分布式一致性是数据库从单机走向分布式的灵魂。Raft 以可读性著称，是入门一致性协议的最佳选择。',
        '',
        '- [Raft 重要概念](/blog/tags/Raft/) — Leader / Follower / Candidate 与 Term。',
        '- [Raft 协议动态调整 quorum](/blog/tags/Raft/) — 业务驱动的多数派动态变更方案。',
        '- [C-Raft 分布式存储方案](/blog/tags/C-Raft/) — 用 C 语言实现的轻量 Raft 库。',
        '- [c-rart](/blog/tags/Raft/) — 极简 Raft 实现，便于教学。',
        '',
        '### 多数据库对比与选型',
        '',
        '工程实践中往往要在多种数据库之间做选型，下面是我对几种主流数据库的横向分析与落地经验。',
        '',
        '- [PostgreSQL](/blog/categories/PostgreSQL/) — 强事务、丰富生态、可扩展性极强的"瑞士军刀"。',
        '- [MySQL](/blog/categories/MySQL/) — 互联网时代的事实标准，分库分表套路成熟。',
        '- [SQLServer](/blog/categories/SQLServer/) — 企业级特性的集大成者，与 .NET 生态深度绑定。',
        '- [TDengine](/blog/categories/TDengine/) — 面向 IoT 的时序数据库，存储压缩比惊人。',
        '- [PolarDB 竞争力分析](/blog/categories/数据库深入/) — 云原生分布式数据库的工程亮点。',
        '- [多数据库模式命名空间问题](/blog/tags/命名空间/) — 同名数据库在多源汇聚时的冲突与解决。',
        '- [命名空间](/blog/tags/命名空间/) — 跨库统一视图的设计思路。',
        '',
        '### 性能调优与故障排查',
        '',
        "生产环境里 90% 的稳定性问题来自错误的配置、不合理的查询、以及对内核机制的误解。这里整理了一些高频排查套路。",
        '',
        '- [Checkpointer 机制浅析](/blog/tags/Checkpoint/) — 检查点触发时机与刷盘策略。',
        '- [WAL Writer](/blog/tags/WalWriter/) — 异步刷盘的延迟与吞吐平衡。',
        '- [统计信息采样](/blog/tags/统计信息/) — ANALYZE 频率与规划器稳定性的关系。',
        '- [PG 复制 keepalive](/blog/tags/keepalive/) — 跨地域复制的网络参数调优。',
        '- [PG IO 调优](/blog/tags/性能调优/) — shared_buffers / wal_buffers / effective_cache_size 的取舍。',
        '- [HA 元信息常见存储方式](/blog/tags/HA/) — etcd / 自建表 / 文件系统的权衡。',
        '- [多地多中心方案调研](/blog/tags/多中心/) — 同城双活、两地三中心、单元化架构对比。',
        '- [code-server 调试 PostgreSQL](/blog/tags/debug/) — 云端断点调试 PostgreSQL 的工程实践。',
        '',
        '## 实战经验沉淀',
        '',
        '- **内核 Bug 定位**：熟悉 gdb / perf / bpftrace 的组合用法，能从 panic 日志反推到具体的代码行。',
        '- **补丁贡献**：曾向 PostgreSQL 社区提交过若干小补丁（包括 PG15 逻辑复制 DDL 支持），熟悉社区 patch 提交流程与 code review 风格。',
        '- **性能优化**：在 openGauss 内核侧主导过 WAL 写入路径优化、复制槽回收策略改造等专项，单节点写入吞吐有数倍提升。',
        '- **架构设计**：完整设计过一套基于 DCF 的两地三中心高可用方案，覆盖网络分区、脑裂、自动切换、降级运行等场景。',
        '- **自动化工具**：写过一个内部用的"内核健康巡检"脚本，能在分钟级自动扫描数百个 PG 实例并给出风险项。',
        '',
        '## 推荐阅读顺序',
        '',
        '如果你只想读 5 篇文章理解数据库内核的脉络，我会推荐：',
        '',
        '1. [PostgreSQL 主结构](/blog/tags/PostgreSQL/)',
        '2. [WAL 机制浅析](/blog/tags/WAL/)',
        '3. [PostgreSQL 流复制与 WAL 日志](/blog/tags/流复制/)',
        '4. [一文读懂 openGauss DCF 网络模块](/blog/tags/DCF/)',
        '5. [逻辑解码 DDL-Replay 框架设计](/blog/tags/DDL-Replay/)',
        '',
        '这五篇涵盖了存储、复制、分布式一致性与逻辑同步四条主线，足以勾勒出数据库内核的整体图景。',
        '',
        '## 写在最后',
        '',
        '数据库内核开发是一个“慢就是快”的领域：每一次对一行代码的深入理解，最终都会在某个深夜的故障排查里兑现回报。本专题会持续更新，把每一段新的源码阅读笔记、每一次新的故障复盘都沉淀下来。也欢迎通过 [GitHub](https://github.com/growdu) 与我交流。',
        '',
    ]

    body = chr(10).join(lines)

    with open(db_path, 'w', encoding='utf-8') as f:
        f.write(fm + body)
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

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

    cats = read_section_categories()
    print(f'Categories: {len(cats)}')

    copy_images()
    print('Images copied')

    n = 0
    for root, _, files in os.walk(DOCS):
        for f in sorted(files):
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    if process(fp, cats):
                        n += 1
                except Exception as e:
                    print(f'ERROR {fp}: {e}', file=sys.stderr)
    print(f'Posts: {n}')


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


    # Service worker for offline reading
    sw_path = os.path.join(SRC, 'sw.js')
    with open(sw_path, 'w', encoding='utf-8') as f:
        f.write("""const CACHE='blog-v1';self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;const u=new URL(e.request.url);if(u.origin!==location.origin)return;if(e.request.headers.get('accept')&&e.request.headers.get('accept').includes('text/html')){e.respondWith(fetch(e.request).then(r=>{const c=r.clone();caches.open(CACHE).then(c=>c.put(e.request,c));return r}).catch(()=>caches.match(e.request)))}else{e.respondWith(caches.match(e.request).then(c=>c||fetch(e.request).then(r=>{const c=r.clone();caches.open(CACHE).then(c=>c.put(e.request,c));return r}).catch(()=>caches.match(e.request))))}});""")
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
    db_path = os.path.join(SRC, 'database', 'index.md')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db_md = """---
title: 数据库专题
date: 2025-04-16 00:00:00
type: "database"
---

# 数据库专题

本站数据库方向文章涵盖以下领域：

| 方向 | 说明 |
|------|------|
| [数据库深入](/blog/categories/数据库深入/) | 数据库原理、架构与深度分析 |
| [PostgreSQL](/blog/categories/PostgreSQL/) | PostgreSQL 内核与运维 |
| [openGauss](/blog/categories/openGauss/) | openGauss DCF、逻辑解码等 |
| [存储](/blog/categories/存储/) | 存储引擎与分布式存储 |
| [OPC](/blog/categories/OPC/) | OPC 相关技术 |

> 后续将持续更新数据库内核、性能优化、分布式架构等方向的文章。
"""
    with open(db_path, 'w', encoding='utf-8') as f:
        f.write(db_md)
    print('Created database landing page')

    create_theme_pages()
    print('Theme pages created')


if __name__ == '__main__':
    main()

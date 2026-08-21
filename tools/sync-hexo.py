#!/usr/bin/env python3
"""
Transform Hugo-style docs/ content into Hexo source/ directory.

Creates:
  source/_posts/  - markdown posts with Hexo front matter
  source/images/  - all images from docs/ (paths rewritten to images/...)

Does NOT modify docs/ — runs in CI on a fresh checkout.
"""
import os, re, shutil, subprocess, sys, json
from urllib.parse import quote

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
    """Map top-level section dir -> Chinese display name from _index.md."""
    titles = {}
    for section in os.listdir(DOCS):
        idx = os.path.join(DOCS, section, '_index.md')
        if not os.path.isfile(idx):
            continue
        with open(idx, encoding='utf-8') as f:
            txt = f.read()
        m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', txt, re.MULTILINE)
        if m:
            titles[section] = m.group(1).strip()
    return titles


def read_cascade_categories():
    """Walk docs/**/_index.md and collect `cascade.categories` per subdir.

    Returns {subdir_path_relative_to_docs: [list of category names]}.
    """
    cascades = {}
    for root, dirs, files in os.walk(DOCS):
        if '_index.md' not in files:
            continue
        idx = os.path.join(root, '_index.md')
        with open(idx, encoding='utf-8') as f:
            txt = f.read()
        m = re.search(
            r'cascade:\s*\n\s*categories:\s*\n((?:\s*-\s*.+\n)+)',
            txt, re.MULTILINE
        )
        if m:
            items = []
            for line in m.group(1).split('\n'):
                item_m = re.match(r'\s*-\s*(.+)', line)
                if item_m:
                    items.append(item_m.group(1).strip())
            if items:
                rel = os.path.relpath(root, DOCS)
                cascades[rel] = items
    return cascades


def resolve_post_categories(rel, section_titles, cascades):
    """Resolve final category list for a post at relative path `rel`.

    1. Top-level section title (primary, drives URL slugs)
    2. Cascade categories from nearest ancestor _index.md (going up)

    De-duplicated; primary stays first.
    """
    section = rel.split(os.sep)[0] if os.sep in rel else ''
    primary = section_titles.get(section, section or '随笔')
    cats = [primary]
    seen = {primary}
    fdir = os.path.dirname(rel)
    if fdir:
        parts = fdir.split(os.sep)
        for i in range(1, len(parts) + 1):
            sub = os.sep.join(parts[:i])
            if sub in cascades:
                for c in cascades[sub]:
                    if c not in seen:
                        cats.append(c)
                        seen.add(c)
    return cats


def categories_yaml(cats):
    """Render a list of category strings as a YAML list body."""
    return '\n'.join(f'  - {c}' for c in cats)


def collect_database_posts(section_titles, cascades):
    """Collect database posts and their generated permalinks for the landing page."""
    posts = []
    for root, _, files in os.walk(DOCS):
        for filename in sorted(files):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ('.md', '.html', '.htm') or filename == '_index.md':
                continue
            filepath = os.path.join(root, filename)
            rel = os.path.relpath(filepath, DOCS)
            with open(filepath, encoding='utf-8') as f:
                content = f.read()
            fm, body = split_fm(content)
            src = body if fm is not None else content
            if ext == '.md':
                title = extract_title(src) or fallback_title(filepath)
                if has_fm_title(fm):
                    title_match = re.search(
                        r'^title:\s*["\']?(.+?)["\']?\s*$', fm, re.MULTILINE
                    )
                    if title_match:
                        title = title_match.group(1).strip()
            else:
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.I | re.S)
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else fallback_title(filepath)
            categories = resolve_post_categories(rel, section_titles, cascades)
            if '数据库' not in categories and 'PostgreSQL 源码修炼之路' not in categories:
                continue
            fdir = os.path.dirname(rel)
            if filename == 'index.md':
                slug = os.path.basename(fdir)
            else:
                slug = os.path.splitext(filename)[0]
                if ext in ('.html', '.htm') and not slug.endswith('-html'):
                    slug += '-html'
            date = git_date(filepath)
            # Hexo derives the permalink slug from the post's full path under
            # source/_posts. A page-bundle index.md is flattened to
            # <parent>/<bundle-name>.md by process(), so its link must not
            # include the bundle directory a second time.
            source_dir = os.path.dirname(fdir) if filename == 'index.md' and fdir else fdir
            post_path = os.path.join(source_dir, slug) if source_dir and source_dir != '.' else slug
            url = f'/{date[:4]}/{date[5:7]}/{date[8:10]}/{quote(post_path)}/'
            posts.append({'title': title, 'url': url, 'date': date})
    unique = {post['url']: post for post in posts}
    return sorted(unique.values(), key=lambda post: post['date'], reverse=True)


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


def read_matery_about_config():
    """Read profile/myProjects/mySkills from _config.matery.yml.

    Lightweight YAML parser tailored to the structure used by the about
    section. Handles comments, quoted strings, multiline `|` blocks, and
    the 0/2/4/6-space indent structure used in _config.matery.yml.

    Returns (profile, my_projects, my_skills) as dicts.
    """
    config_path = '_config.matery.yml'
    if not os.path.isfile(config_path):
        return {}, {'enable': False, 'data': {}}, {'enable': False, 'data': {}}

    with open(config_path, encoding='utf-8') as f:
        lines = f.readlines()

    profile = {}
    my_projects = {'enable': False, 'data': {}}
    my_skills = {'enable': False, 'data': {}}
    my_education = {'enable': False, 'data': []}
    my_honors = {'enable': False, 'data': []}
    my_timeline = {'enable': False, 'data': []}

    # Sections whose `data:` is a list of dicts (vs dict of dicts).
    LIST_DATA_SECTIONS = {'myEducation', 'myHonors', 'myTimeline'}

    # Map top-level section name -> mutable target dict so we can
    # look up enable flag and data container uniformly.
    section_data_map = {
        'myProjects': my_projects,
        'mySkills': my_skills,
        'myEducation': my_education,
        'myHonors': my_honors,
        'myTimeline': my_timeline,
    }

    current_top = None
    current_data_target = None
    current_data_key = None
    current_list_item = None
    current_dict_item = None  # dict we are currently populating with key/value pairs
    current_list_key = None   # key whose list we are currently appending to
    in_multiline = False
    multiline_target = None
    multiline_block_indent = None
    multiline_value = []

    def strip_comment(s):
        in_q = False
        q_char = ''
        for i, c in enumerate(s):
            if c in ('"', "'") and (i == 0 or s[i-1] != '\\'):
                if not in_q:
                    in_q = True; q_char = c
                elif c == q_char:
                    in_q = False
            elif c == '#' and not in_q:
                return s[:i].rstrip()
        return s.rstrip()

    def flush_multiline():
        nonlocal in_multiline, multiline_value, multiline_target
        if multiline_target == 'profile_intro':
            # Drop leading blank lines, then lstrip the first content line
            # so the introduction starts flush-left even if the YAML
            # author indented the first line relative to the indicator.
            while multiline_value and not multiline_value[0].strip():
                multiline_value.pop(0)
            if multiline_value:
                multiline_value[0] = multiline_value[0].lstrip()
            profile['introduction'] = '\n'.join(multiline_value).rstrip()
        in_multiline = False
        multiline_value = []
        multiline_target = None

    def unquote(v):
        """Strip matching outer quotes from a YAML scalar."""
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            return v[1:-1]
        return v

    for raw in lines:
        stripped = raw.rstrip('\n').rstrip('\r')
        if not stripped.strip():
            if in_multiline:
                multiline_value.append('')
            continue
        if stripped.lstrip().startswith('#'):
            continue

        indent = len(stripped) - len(stripped.lstrip())
        content = strip_comment(stripped[indent:])

        if in_multiline:
            # YAML literal block scalars use the indent of the FIRST
            # non-empty content line as the block indent.
            if multiline_block_indent is None and stripped.strip():
                multiline_block_indent = indent
            if multiline_block_indent is not None and indent >= multiline_block_indent:
                line_text = stripped[multiline_block_indent:]
                multiline_value.append(line_text)
                continue
            else:
                flush_multiline()

        if not content:
            continue

        # Top-level key (indent 0)
        if indent == 0 and content.endswith(':'):
            # Flush any pending list-of-dicts item from the previous
            # section before transitioning.
            if current_list_item is not None and current_data_target in LIST_DATA_SECTIONS:
                section_data_map[current_data_target]['data'].append(current_list_item)
                current_list_item = None
                current_dict_item = None
            current_list_key = None
            current_top = content[:-1].strip()
            current_data_target = None
            current_data_key = None
            continue

        # 2-space indent (subkey of top-level section)
        if indent == 2 and ':' in content:
            key, _, value = content.partition(':')
            key = key.strip()
            value = value.strip()

            if current_top == 'profile':
                if key == 'introduction' and value == '|':
                    in_multiline = True
                    multiline_target = 'profile_intro'
                    multiline_block_indent = None
                    multiline_value = []
                else:
                    profile[key] = unquote(value)
            elif current_top in section_data_map:
                target = section_data_map[current_top]
                if key == 'enable':
                    target['enable'] = (value == 'true')
                elif key == 'data' and value == '':
                    current_data_target = current_top
            current_data_key = None
            current_list_item = None
            continue

        # 4-space indent (item in data dict or list)
        if indent == 4 and current_data_target:
            current_list_key = None  # exiting any prior list-collecting scope
            if current_data_target in LIST_DATA_SECTIONS:
                # List-of-dicts: each `- key: ...` starts a new item.
                if content.startswith('- '):
                    if current_list_item is not None:
                        section_data_map[current_data_target]['data'].append(current_list_item)
                    current_list_item = {}
                    current_dict_item = current_list_item
                    # Inline `- key: value` populates the new item's
                    # first field; otherwise the key comes from a
                    # following 6-space indent line.
                    rest = content[2:].strip()
                    if ':' in rest:
                        k, _, v = rest.partition(':')
                        current_dict_item[k.strip()] = unquote(v.strip())
                continue
            if content.endswith(':'):
                item_name = content[:-1].strip()
                current_data_key = item_name
                section_data_map[current_data_target]['data'][item_name] = {}
                current_dict_item = section_data_map[current_data_target]['data'][item_name]
            continue

        # 6-space indent (property of data item)
        if indent == 6 and ':' in content:
            key, _, value = content.partition(':')
            key = key.strip()
            value = unquote(value.strip())
            current_list_key = None  # a fresh 6-space key resets nested-list mode
            if current_dict_item is not None:
                if value == '' and not content.startswith('- '):
                    # Empty value: a following 8-space `- xxx` list
                    # populates this key as a list.
                    current_dict_item[key] = []
                    current_list_key = key
                elif content.startswith('- '):
                    current_dict_item.setdefault(key, []).append(value)
                else:
                    current_dict_item[key] = value
                continue
            continue

        # 8-space indent: items in a list under the current key.
        if indent >= 8 and current_dict_item is not None and current_list_key:
            target_list = current_dict_item.get(current_list_key)
            if isinstance(target_list, list):
                if content.startswith('- '):
                    target_list.append(unquote(content[2:].strip()))
                elif ':' in content:
                    _, _, vv = content.partition(':')
                    target_list.append(unquote(vv.strip()))
            continue

    if in_multiline:
        flush_multiline()
    if current_list_item is not None and current_data_target in LIST_DATA_SECTIONS:
        section_data_map[current_data_target]['data'].append(current_list_item)

    return profile, my_projects, my_skills, my_education, my_honors, my_timeline


def build_about_markdown(profile, my_projects, my_skills,
                           my_education=None, my_honors=None,
                           my_timeline=None):
    """Build source/about/index.md content from matery config + static sections.

    `my_education`, `my_honors`, `my_timeline` are optional list-of-dicts
    sections. `my_timeline` renders right under the bio intro as a
    vertical timeline; the others render after the project cards.
    """
    my_education = my_education or {'enable': False, 'data': []}
    my_honors = my_honors or {'enable': False, 'data': []}
    my_timeline = my_timeline or {'enable': False, 'data': []}

    intro = profile.get('introduction') or (
        '资深后端研发工程师，专注数据库内核与分布式系统。'
    )

    # Skill bars
    skill_lines = []
    if my_skills.get('enable') and my_skills.get('data'):
        for name, props in my_skills['data'].items():
            bg = props.get('background', 'linear-gradient(to right, #336791 0%, #4B8BBE 100%)')
            pct = props.get('percent', '80%')
            skill_lines.append(
                f'<div class="skill-bar">\n'
                f'  <div class="skill-row"><span>{name}</span><span>{pct}</span></div>\n'
                f'  <div class="skill-track"><div class="skill-fill" '
                f'style="width:{pct};background:{bg}"></div></div>\n'
                f'</div>'
            )
    skills_block = '\n'.join(skill_lines) if skill_lines else ''

    # Project cards (richer: time / company / role / achievements / tech)
    project_lines = []
    if my_projects.get('enable') and my_projects.get('data'):
        for name, props in my_projects['data'].items():
            icon = props.get('icon', 'fas fa-code')
            bg = props.get('iconBackground',
                           'linear-gradient(to bottom right, #3367D6 0%, #0084FF 100%)')
            url = props.get('url', '')
            time = props.get('time', '')
            company = props.get('company', '')
            role = props.get('role', '')
            desc = props.get('desc', '')
            tech = props.get('tech', '')
            achievements = props.get('achievements') or []

            meta_bits = [b for b in (company, role, time) if b]
            meta_sep = ' · '.join(meta_bits)
            meta_html = (
                f'<div class="proj-meta">{meta_sep}</div>' if meta_bits else ''
            )
            ach_html = ''
            if achievements:
                items = ''.join(f'<li>{a}</li>' for a in achievements)
                ach_html = f'<ul class="proj-achievements">{items}</ul>'
            tech_html = (
                f'<div class="proj-tech">技术栈: {tech}</div>' if tech else ''
            )
            url_attr = f' data-url="{url}"' if url else ''

            project_lines.append(
                f'<div class="project-card"{url_attr}>\n'
                f'  <div class="proj-icon" style="background:{bg};"><i class="{icon}"></i></div>\n'
                f'  <div class="proj-body">\n'
                f'    <div class="proj-name">{name}</div>\n'
                f'    {meta_html}\n'
                f'    <div class="proj-desc">{desc}</div>\n'
                f'    {ach_html}\n'
                f'    {tech_html}\n'
                f'  </div>\n'
                f'</div>'
            )
    projects_block = '\n'.join(project_lines) if project_lines else ''

    # Education cards
    edu_lines = []
    if my_education.get('enable') and my_education.get('data'):
        for ed in my_education['data']:
            school = ed.get('school', '')
            major = ed.get('major', '')
            degree = ed.get('degree', '')
            period = ed.get('period', '')
            honor = ed.get('honor', '')
            major_line = ' · '.join(b for b in (major, degree) if b)
            honor_html = (
                f'<div class="edu-honor"><i class="fas fa-award"></i> {honor}</div>'
                if honor else ''
            )
            edu_lines.append(
                f'<div class="edu-item">\n'
                f'  <div class="edu-school">{school}</div>\n'
                f'  <div class="edu-major">{major_line}</div>\n'
                f'  <div class="edu-period">{period}</div>\n'
                f'  {honor_html}\n'
                f'</div>'
            )
    edu_block = '\n'.join(edu_lines) if edu_lines else ''

    # Bio timeline
    timeline_lines = []
    if my_timeline.get('enable') and my_timeline.get('data'):
        for t in my_timeline['data']:
            period = t.get('period', '')
            title = t.get('title', '')
            desc = t.get('desc', '')
            timeline_lines.append(
                f'<div class="timeline-item">\n'
                f'  <div class="timeline-date">{period}</div>\n'
                f'  <div class="timeline-title">{title}</div>\n'
                f'  <div class="timeline-desc">{desc}</div>\n'
                f'</div>'
            )
    timeline_block = '\n'.join(timeline_lines) if timeline_lines else ''

    # Honors list
    honor_lines = []
    if my_honors.get('enable') and my_honors.get('data'):
        for h in my_honors['data']:
            name = h.get('name', '')
            level = h.get('level', '')
            year = h.get('year', '')
            year_html = (
                f'<span class="honor-year">{year}</span>\n  '
                if year else ''
            )
            honor_lines.append(
                f'<div class="honor-item">\n'
                f'  <span class="honor-name">{name}</span>\n'
                f'  <span class="honor-level">{level}</span>\n'
                f'  {year_html}</div>'
            )
    honor_block = '\n'.join(honor_lines) if honor_lines else ''

    # Compose optional sections
    edu_section = (
        f'\n## 教育背景\n\n<div class="edu-grid">\n{edu_block}\n</div>\n'
        if edu_block else ''
    )
    honor_section = (
        f'\n## 个人荣誉\n\n<div class="honor-list">\n{honor_block}\n</div>\n'
        if honor_block else ''
    )
    timeline_section = (
        f'\n<div class="about-timeline">\n{timeline_block}\n</div>\n'
        if timeline_block else ''
    )

    # Compose the template as a plain string and use str.format_map
    # so we can keep literal CSS braces (single { is fine in format()
    # when we use a SafeFormatter or escape via {{}}).
    template = """---
title: "关于我"
date: 2026-07-29 00:00:00
---

# 关于我

{intro}{timeline_section}
## 重点项目

{projects_block}{edu_section}{honor_section}
## GitHub 数据

<div id="gh-stats" class="gh-stats">
  <div class="gh-stat"><div class="gh-stat-num">--</div><div class="gh-stat-label">加载中</div></div>
</div>
<script>
fetch('https://api.github.com/users/growdu')
  .then(function(r){{return r.json()}})
  .then(function(d){{
    var el=document.getElementById('gh-stats');
    if(el&&d) el.innerHTML=
      '<div class="gh-stat"><div class="gh-stat-num">'+d.public_repos+'</div><div class="gh-stat-label">公开仓库</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.followers+'</div><div class="gh-stat-label">关注者</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+d.following+'</div><div class="gh-stat-label">关注中</div></div>'+
      '<div class="gh-stat"><div class="gh-stat-num">'+(d.created_at?d.created_at.substring(0,4):'--')+'</div><div class="gh-stat-label">加入GitHub</div></div>';
  }})
  .catch(function(){{}});
</script>

## 技术栈

{skills_block}

## 联系方式

- **GitHub**: https://github.com/growdu
- **Email**: growdu@gmail.com
- **QQ**: 2689304284
"""
    return template.format(
        intro=intro,
        timeline_section=timeline_section,
        skills_block=skills_block,
        projects_block=projects_block,
        edu_section=edu_section,
        honor_section=honor_section,
    )



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


def process(filepath, section_titles, cascades):
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
    post_cats = resolve_post_categories(rel, section_titles, cascades)

    # rewrite images, strip first H1 (title is in front matter)
    body_out = rewrite_images(src, fdir)
    body_out = re.sub(r'^#\s+.+\n?', '', body_out, count=1, flags=re.MULTILINE)

    top_val = FEATURED_POSTS.get(rel)
    top_line = f'\ntop: {top_val}' if top_val else ''
    cats_block = categories_yaml(post_cats)
    fm_out = f'---\ntitle: "{yaml_escape(title)}"\ndate: {date}\nauthor: growdu{top_line}\ncategories:\n{cats_block}\ntags:\n{cats_block}\n---\n'

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
def process_html(filepath, section_titles, cascades):
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
    post_cats = resolve_post_categories(rel, section_titles, cascades)

    top_val = FEATURED_POSTS.get(rel)
    top_line = f'\ntop: {top_val}' if top_val else ''
    cats_block = categories_yaml(post_cats)
    fm_out = (
        f'---\n'
        f'title: "{yaml_escape(title)}"\n'
        f'date: {date}\n'
        f'author: growdu{top_line}\n'
        f'categories:\n{cats_block}\n'
        f'tags:\n{cats_block}\n'
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

    # About page - generated from _config.matery.yml profile/myProjects/mySkills
    # so updates to the config (e.g. career dates, project list) flow through
    # to the rendered page automatically on the next sync.
    about_path = os.path.join(SRC, 'about', 'index.md')
    os.makedirs(os.path.dirname(about_path), exist_ok=True)
    _profile, _my_projects, _my_skills, _my_education, _my_honors, _my_timeline = read_matery_about_config()
    about_md = build_about_markdown(
        _profile, _my_projects, _my_skills,
        _my_education, _my_honors, _my_timeline,
    )
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

    section_titles = read_section_categories()
    cascade_map = read_cascade_categories()
    print(f'Section titles: {len(section_titles)}, cascade dirs: {len(cascade_map)}')

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
                    if process(fp, section_titles, cascade_map):
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
                    if process_html(fp, section_titles, cascade_map):
                        n_html += 1
            except Exception as e:
                print(f'ERROR {fp}: {e}', file=sys.stderr)
    print(f'Markdown posts: {n_md}')
    print(f'HTML docs:      {n_html}')


    # robots.txt for SEO
    robots_path = os.path.join(SRC, 'robots.txt')
    with open(robots_path, 'w', encoding='utf-8') as f:
        f.write('User-agent: *\nAllow: /\n\nSitemap: https://growdu.cn/sitemap.xml\n')
    print('Created robots.txt')


    # PWA manifest (re-include icons[] on every regen so a fresh CI
    # checkout doesn't silently drop the 48x48 favicon + 192x192 logo
    # entries; aa9cfb6 originally restored them after a similar bug).
    manifest_path = os.path.join(SRC, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write('{\n  "name": "编程之路",\n  "short_name": "编程之路",\n  "description": "资深后端研发工程师的技术博客",\n  "start_url": "/",\n  "scope": "/",\n  "display": "standalone",\n  "background_color": "#ffffff",\n  "theme_color": "#009688",\n  "lang": "zh-CN",\n  "icons": [\n    {\n      "src": "/favicon.png",\n      "sizes": "48x48",\n      "type": "image/png"\n    },\n    {\n      "src": "/medias/logo.jpg",\n      "sizes": "192x192",\n      "type": "image/jpeg"\n    }\n  ]\n}\n')
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


    # 404 page (upgraded with search + recent posts)
    notfound_path = os.path.join(SRC, '404.html')
    with open(notfound_path, 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>404 · 页面走丢了 | growdu</title>
<meta name="description" content="页面不存在。试试在首页搜索，或浏览热门文章。">
<style>
:root{--c1:#009688;--c1l:#4dd0e1;--bg:#f8fafc;--card:#fff;--fg:#263238;--muted:#607d8b;--line:rgba(0,0,0,0.08)}
@media (prefers-color-scheme: dark){:root{--bg:#0f1417;--card:#1e272c;--fg:#eceff1;--muted:#b0bec5;--line:rgba(255,255,255,0.08)}}
*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;background:var(--bg);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--fg);display:flex;align-items:center;justify-content:center;padding:32px 16px}
.wrap{max-width:680px;width:100%}
.card{background:var(--card);border-radius:18px;padding:48px 40px;box-shadow:0 8px 32px rgba(0,0,0,0.06);text-align:center}
.brand{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:24px;color:var(--c1);font-weight:700;font-size:18px}
.brand img{width:32px;height:32px;border-radius:50%}
h1{font-size:96px;font-weight:900;color:var(--c1);line-height:1;letter-spacing:-2px;margin:0 0 8px}
h1 small{font-size:24px;color:var(--muted);font-weight:600;display:block;margin-top:6px;letter-spacing:0}
.lead{color:var(--muted);font-size:15px;margin:0 0 28px;line-height:1.7}
.search{display:flex;gap:8px;margin:0 0 28px}
.search input{flex:1;padding:12px 16px;font-size:14px;border:1px solid var(--line);border-radius:24px;background:var(--bg);color:var(--fg);outline:none;transition:border-color .15s}
.search input:focus{border-color:var(--c1)}
.search button{padding:0 22px;background:var(--c1);color:#fff;border:none;border-radius:24px;font-weight:600;cursor:pointer;font-size:14px;transition:background .15s}
.search button:hover{background:#00796b}
.divider{display:flex;align-items:center;gap:12px;margin:28px 0 16px;color:var(--muted);font-size:12px}
.divider::before,.divider::after{content:"";flex:1;height:1px;background:var(--line)}
.recent{list-style:none;text-align:left;margin:0 0 24px}
.recent li{padding:10px 0;border-bottom:1px solid var(--line)}
.recent li:last-child{border-bottom:none}
.recent a{color:var(--fg);text-decoration:none;display:flex;align-items:flex-start;gap:8px;font-size:14px;line-height:1.5}
.recent a:hover{color:var(--c1)}
.recent .title{flex:1}
.recent .cat{font-size:11px;color:var(--muted);background:var(--bg);padding:2px 8px;border-radius:10px;flex-shrink:0}
.actions{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:8px}
.btn{display:inline-flex;align-items:center;gap:6px;padding:10px 22px;border-radius:22px;font-size:14px;font-weight:600;text-decoration:none;transition:all .15s}
.btn-primary{background:var(--c1);color:#fff}
.btn-primary:hover{background:#00796b;transform:translateY(-1px)}
.btn-ghost{border:1px solid var(--line);color:var(--fg)}
.btn-ghost:hover{border-color:var(--c1);color:var(--c1)}
footer{text-align:center;color:var(--muted);font-size:12px;margin-top:20px}
footer a{color:var(--muted);text-decoration:none}
footer a:hover{color:var(--c1)}
@media (max-width:600px){.card{padding:32px 20px}h1{font-size:72px}.lead{font-size:14px}.actions{flex-direction:column;align-items:stretch}}
</style>
</head>
<body>
<div class="wrap">
<div class="card">
  <div class="brand">
    <img src="/medias/logo.jpg" alt="growdu">
    <span>growdu · 技术学习实践</span>
  </div>
  <h1>404<small>页面走丢了</small></h1>
  <p class="lead">你访问的页面可能搬走了、链接已过期，或者根本不存在。<br>试试下面的搜索框，或浏览最近文章 —</p>
  <form class="search" id="search-form" autocomplete="off">
    <input type="search" id="q" name="q" placeholder="搜索文章标题、标签…" autofocus>
    <button type="submit">搜索</button>
  </form>
  <div class="divider">最近发布</div>
  <ul class="recent" id="recent-list">
    <li style="color:var(--muted);font-size:13px;text-align:center;padding:14px 0">加载中…</li>
  </ul>
  <div class="actions">
    <a href="/" class="btn btn-primary"><i>←</i> 返回首页</a>
    <a href="javascript:history.length>1?history.back():location.href='/'" class="btn btn-ghost">返回上一页</a>
  </div>
</div>
<footer>
  <a href="/atom.xml">RSS</a> · <a href="/about/">关于</a> · <a href="mailto:growdu@gmail.com">联系</a>
</footer>
</div>
<script>
// 1) Search submit -> redirect to a Google site: search if no inline index,
//    otherwise push to history with q for a client-side filter.
(function(){
  var form = document.getElementById('search-form');
  var input = document.getElementById('q');
  if (!form) return;
  form.addEventListener('submit', function(e){
    e.preventDefault();
    var q = (input.value || '').trim();
    if (!q) { input.focus(); return; }
    // Inline index (preferred): fetch /search.xml, filter, show modal.
    fetch('/search.xml').then(function(r){return r.text();}).then(function(xml){
      var doc = new DOMParser().parseFromString(xml, 'text/xml');
      var entries = [].slice.call(doc.querySelectorAll('entry'));
      var hits = entries.filter(function(en){
        return (en.querySelector('title') || {}).textContent.indexOf(q) >= 0;
      }).slice(0, 10);
      if (hits.length) {
        var list = document.getElementById('recent-list');
        list.innerHTML = hits.map(function(en){
          var t = en.querySelector('title').textContent;
          var u = en.querySelector('url').textContent;
          return '<li><a href="'+u+'"><span class="title">'+t+'</span></a></li>';
        }).join('');
        document.querySelector('.divider').textContent = '搜索结果 ('+hits.length+')';
      } else {
        document.getElementById('recent-list').innerHTML = '<li style="text-align:center;color:var(--muted);padding:14px 0">没有匹配，换个词试试</li>';
        document.querySelector('.divider').textContent = '搜索结果';
      }
    }).catch(function(){
      // Fallback: Google site search
      window.location.href = 'https://www.google.com/search?q='+encodeURIComponent(q+' site:growdu.cn');
    });
  });
})();

// 2) Render recent posts from a pre-built JSON written by sync-hexo.py
fetch('/recent-posts.json').then(function(r){return r.json();}).then(function(posts){
  if (!Array.isArray(posts) || !posts.length) return;
  var html = posts.map(function(p){
    return '<li><a href="'+p.url+'"><span class="title">'+p.title+'</span><span class="cat">'+p.cat+'</span></a></li>';
  }).join('');
  document.getElementById('recent-list').innerHTML = html;
}).catch(function(){});
</script>
</body>
</html>""")
    print('Created 404.html')

    # Recent posts JSON: consumed by the 404 page.
    # Source: source/_posts/**/*.md, sorted by `top` desc then `date` desc.
    # Skips `blog/` meta-docs and any path starting with `_index`.
    # (json is already imported at module level)
    import glob as _glob
    import re as _re
    posts_root = os.path.join(SRC, '_posts')
    META_CATS = ('blog', 'tools', 'page')  # skip meta-doc categories
    if os.path.isdir(posts_root):
        scored = []
        for fp in _glob.glob(os.path.join(posts_root, '**', '*.md'), recursive=True):
            try:
                with open(fp, encoding='utf-8') as f:
                    txt = f.read(4000)
            except OSError:
                continue
            rel = os.path.relpath(fp, posts_root).replace('\\', '/')
            parts = rel.split('/')
            cat = parts[0] if len(parts) > 1 else ''
            slug = parts[-1].replace('.md', '').replace('.html', '')
            if not slug or slug.startswith('_index') or cat in META_CATS:
                continue
            tm = _re.search(r'^title:\s*["\']?([^"\'\n]+)["\']?', txt, _re.M)
            dm = _re.search(r'^date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', txt, _re.M)
            top_m = _re.search(r'^top:\s*([0-9]+)', txt, _re.M)
            title = tm.group(1).strip() if tm else slug
            date_str = dm.group(1) if dm else '1970-01-01'
            top_n = int(top_m.group(1)) if top_m else 0
            scored.append((top_n, date_str, cat, slug, title))
        scored.sort(key=lambda x: (-x[0], -int(x[1].replace('-', ''))))
        recent = []
        for (_t, _d, c, s, t) in scored[:6]:
            url = ('/' + s + '/') if not c else ('/' + c + '/' + s + '/')
            recent.append({'title': t, 'url': url, 'cat': c or s})
        if recent:
            recent_path = os.path.join(SRC, 'recent-posts.json')
            with open(recent_path, 'w', encoding='utf-8') as f:
                json.dump(recent, f, ensure_ascii=False, indent=2)
            print('Wrote recent-posts.json (%d items)' % len(recent))
    # Database landing page
    database_posts = collect_database_posts(section_titles, cascade_map)
    create_database_landing_page(database_posts)
    print('Created database landing page')

def create_database_landing_page(database_posts):
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
    start_marker = '<!-- DATABASE_POSTS_START -->'
    end_marker = '<!-- DATABASE_POSTS_END -->'
    if start_marker not in content or end_marker not in content:
        raise ValueError('database template is missing DATABASE_POSTS markers')
    if database_posts:
        post_list = '\n'.join(
            f'- [{post["title"]}]({post["url"]})' for post in database_posts
        )
    else:
        post_list = '数据库系列文章正在整理中。'
    content = content.replace(start_marker, post_list, 1)
    content = content.replace(end_marker, '', 1)
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

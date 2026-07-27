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


def git_date(path):
    try:
        r = subprocess.run(['git','log','-1','--format=%ai','--',path],
                           capture_output=True, text=True, check=True)
        d = r.stdout.strip()
        return d if d else '2024-01-01 00:00:00'
    except Exception:
        return '2024-01-01 00:00:00'


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

    fm_out = f'---\ntitle: "{yaml_escape(title)}"\ndate: {date}\ncategories:\n  - {cat}\ntags:\n  - {cat}\n---\n'

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

    create_theme_pages()
    print('Theme pages created')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Localize CDN dependencies in the matery theme for faster China access.

Replaces CDN URLs (jsdelivr/cdnjs/unpkg) with local paths under /blog/lib/.
Only replaces URLs whose files actually exist in node_modules/ — if a package
isn't installed, the original CDN URL is kept (graceful fallback).

Generates tools/cdn-manifest.json listing files to copy from node_modules.

Run AFTER patch-theme.py and theme clone, BEFORE sync-hexo.py.
The manifest is consumed by tools/copy-vendor.py AFTER sync-hexo.py.
"""
import os, re, json, sys

THEME = 'themes/matery'
CONFIG = os.path.join(THEME, '_config.yml')
ROOT = '/blog/lib/'
MANIFEST_PATH = 'tools/cdn-manifest.json'

copies = []  # list of [node_modules_path, source_lib_path]


def extract_pkg_file(url_or_path):
    """Extract (npm_package, file_path) from a CDN URL or versioned npm path."""
    s = url_or_path.strip().strip('"\'').strip()
    if not s:
        return None

    cdn_type = None
    for prefix, ctype in [
        ('https://cdn.jsdelivr.net/npm/', 'jsdelivr'),
        ('http://cdn.jsdelivr.net/npm/', 'jsdelivr'),
        ('https://cdnjs.cloudflare.com/ajax/libs/', 'cdnjs'),
        ('http://cdnjs.cloudflare.com/ajax/libs/', 'cdnjs'),
        ('https://unpkg.com/', 'unpkg'),
        ('http://unpkg.com/', 'unpkg'),
    ]:
        if s.startswith(prefix):
            s = s[len(prefix):]
            cdn_type = ctype
            break

    if not cdn_type:
        if not re.search(r'@\d+\.\d+\.\d+/', s):
            return None
        cdn_type = 'jsdelivr'

    if '/' not in s:
        return None

    if cdn_type == 'cdnjs':
        parts = s.split('/', 2)
        if len(parts) < 3:
            return None
        pkg = parts[0]
        file_path = parts[2]
    else:
        idx = s.find('/')
        pkg_ver = s[:idx]
        file_path = s[idx + 1:]
        if pkg_ver.startswith('@'):
            last_at = pkg_ver.rfind('@')
            pkg = pkg_ver[:last_at] if last_at > 0 else pkg_ver
        else:
            pkg = pkg_ver.split('@')[0] if '@' in pkg_ver else pkg_ver

    if not file_path:
        return None
    return pkg, file_path


def local_name(pkg):
    if pkg.startswith('@'):
        parts = pkg.split('/', 1)
        return parts[1] if len(parts) > 1 else pkg
    return pkg


def make_local_url(pkg, file_path):
    return ROOT + local_name(pkg) + '/' + file_path


def make_copy_instruction(pkg, file_path):
    return [f'node_modules/{pkg}/{file_path}', f'source/lib/{local_name(pkg)}/{file_path}']


def file_installed(pkg, file_path):
    """Check if the file exists in node_modules."""
    return os.path.isfile(f'node_modules/{pkg}/{file_path}')


def process_value(val):
    """Returns (new_value, changed). Only replaces if file is installed."""
    if not val:
        return val, False
    result = extract_pkg_file(val)
    if not result:
        return val, False
    pkg, file_path = result
    if not file_installed(pkg, file_path):
        print(f'  SKIP (not installed): {pkg}/{file_path}')
        return val, False
    local_url = make_local_url(pkg, file_path)
    ci = make_copy_instruction(pkg, file_path)
    if ci not in copies:
        copies.append(ci)
    return local_url, True


# --- Process theme _config.yml ---
if not os.path.isfile(CONFIG):
    print(f'ERROR: {CONFIG} not found', file=sys.stderr)
    sys.exit(1)

with open(CONFIG, encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
config_changes = 0
in_libs = False
in_jsdelivr = False

for line in lines:
    stripped = line.rstrip('\n')

    if re.match(r'^jsDelivr:\s*$', stripped):
        in_jsdelivr = True
        in_libs = False
        new_lines.append(line)
        continue
    if re.match(r'^libs:\s*$', stripped):
        in_libs = True
        in_jsdelivr = False
        new_lines.append(line)
        continue
    if re.match(r'^\S', stripped):
        in_jsdelivr = False
        in_libs = False

    if in_jsdelivr and re.match(r'^\s+url:\s*\S', stripped):
        new_line = re.sub(r'^(\s+url:\s*).*', r'\1', line)
        new_lines.append(new_line)
        config_changes += 1
        print('  jsDelivr.url -> empty')
        continue

    if in_libs:
        m = re.match(r'^(\s+\w+:\s*)(.+?)\s*$', stripped)
        if m:
            prefix, val = m.group(1), m.group(2)
            new_val, changed = process_value(val)
            if changed:
                new_lines.append(f'{prefix}{new_val}\n')
                config_changes += 1
                print(f'  {prefix.strip()}: {val} -> {new_val}')
                continue

    new_lines.append(line)

with open(CONFIG, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f'Config: {config_changes} replacements')

# --- Process .ejs files for hardcoded CDN URLs ---
ejs_changes = 0
for root_dir, dirs, files in os.walk(os.path.join(THEME, 'layout')):
    for fname in files:
        if not fname.endswith('.ejs'):
            continue
        fpath = os.path.join(root_dir, fname)
        with open(fpath, encoding='utf-8') as f:
            c = f.read()
        original = c

        for pattern in [
            r'https?://cdn\.jsdelivr\.net/npm/([^\s"\'<>]+)',
            r'https?://cdnjs\.cloudflare\.com/ajax/libs/([^\s"\'<>]+)',
            r'https?://unpkg\.com/([^\s"\'<>]+)',
        ]:
            def repl(m):
                result = extract_pkg_file(m.group(0))
                if not result:
                    return m.group(0)
                pkg, file_path = result
                if not file_installed(pkg, file_path):
                    return m.group(0)
                local = make_local_url(pkg, file_path)
                ci = make_copy_instruction(pkg, file_path)
                if ci not in copies:
                    copies.append(ci)
                return local
            c = re.sub(pattern, repl, c)

        if c != original:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(c)
            ejs_changes += 1
            print(f'  EJS: {os.path.relpath(fpath, THEME)}')

print(f'EJS files: {ejs_changes} modified')

# --- Write manifest ---
with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
    json.dump(copies, f, indent=2, ensure_ascii=False)

pkgs = sorted(set(c[0].split('/')[1] for c in copies))
print(f'\nManifest: {len(copies)} files, packages: {pkgs}')

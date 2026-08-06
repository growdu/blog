#!/usr/bin/env python3
"""
add-tags.py - Batch-add tags/categories to Hexo blog post frontmatter.
Idempotent: won't duplicate tags/categories already present.

Usage: python3 tools/add-tags.py [--dry-run]
"""

import os
import re
import sys
import argparse

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'source', '_posts')


def parse_frontmatter(content):
    """Return (frontmatter_lines, body_start_index)."""
    lines = content.split('\n')
    if not lines or lines[0].strip() != '---':
        return [], 0
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return lines[:i + 1], i + 1
    return [], 0


def find_yaml_list_section(fm_lines, key):
    """Find the start/end indices of a YAML list section like 'tags:' or 'categories:'.
    Returns (start_idx, end_idx, items) where items is list of (line_idx, value).
    Returns (None, None, []) if not found."""
    key_pattern = re.compile(rf'^{key}:\s*$')
    inline_pattern = re.compile(rf'^{key}:\s*\[(.+)\]$')
    inline_single = re.compile(rf'^{key}:\s+(.+)$')

    for i, line in enumerate(fm_lines):
        # Check for inline list: tags: [a, b, c]
        m = inline_pattern.match(line)
        if m:
            items = []
            for item in re.findall(r"'([^']+)'|\"([^\"]+)\"|([^,\s\[\]]+)", m.group(1)):
                val = item[0] or item[1] or item[2]
                if val.strip():
                    items.append((i, val.strip()))
            return i, i + 1, items

        # Check for inline single: tags: TagName
        m = inline_single.match(line)
        if m:
            return i, i + 1, [(i, m.group(1).strip())]

        # Check for multi-line: tags:\n  - Tag1\n  - Tag2
        m = key_pattern.match(line)
        if m:
            items = []
            end = i + 1
            for j in range(i + 1, len(fm_lines)):
                item_match = re.match(r'^(\s+)-\s+(.+)$', fm_lines[j])
                if item_match:
                    items.append((j, item_match.group(2).strip()))
                    end = j + 1
                else:
                    # Check for nested list: - [subcat1, subcat2]
                    nested_match = re.match(r'^(\s+)-\s*$', fm_lines[j])
                    if nested_match:
                        # Skip nested list items (they belong to this item)
                        nested_indent = nested_match.group(1)
                        end = j + 1
                        for k in range(j + 1, len(fm_lines)):
                            if re.match(rf'^{nested_indent}\s+-\s+', fm_lines[k]):
                                end = k + 1
                            else:
                                break
                        continue
                    break
            return i, end, items

    return None, None, []


def find_simple_yaml_value(fm_lines, key):
    """Find a simple YAML key: value line. Returns (line_idx, value) or (None, None)."""
    for i, line in enumerate(fm_lines):
        m = re.match(rf'^{key}:\s+(.+)$', line)
        if m:
            return i, m.group(1).strip()
    return None, None


def add_to_yaml_list(fm_lines, key, new_values):
    """Add new values to a YAML list section. Preserves existing values.
    Converts inline format to multi-line format.
    Returns True if modified."""
    start, end, existing_items = find_yaml_list_section(fm_lines, key)
    if start is None:
        print(f"    WARNING: '{key}:' section not found")
        return False

    existing_values = {v for _, v in existing_items}
    to_add = [v for v in new_values if v not in existing_values]
    if not to_add:
        return False

    # Determine indentation from existing items
    if existing_items:
        _, first_val = existing_items[0]
        # Get the indentation of first list item
        first_line = fm_lines[existing_items[0][0]]
        indent_match = re.match(r'^(\s+)-\s+', first_line)
        indent = indent_match.group(1) if indent_match else '  '
    else:
        indent = '  '

    # If currently inline format, convert to multi-line first
    current_line = fm_lines[start]
    if re.match(rf'^{key}:\s*\S', current_line) and not re.match(rf'^{key}:\s*$', current_line):
        # Convert inline to multi-line
        new_lines = [f'{key}:']
        for _, val in existing_items:
            new_lines.append(f'{indent}- {val}')
        for val in to_add:
            new_lines.append(f'{indent}- {val}')
        fm_lines[start:end] = new_lines
        return True

    # Already multi-line format: insert new tags at end of section
    for val in to_add:
        fm_lines.insert(end, f'{indent}- {val}')
        end += 1

    return True


def set_parallel_categories(fm_lines, new_categories):
    """Set categories as parallel (independent) categories in Hexo.
    Hexo treats each sub-list as a separate category path.
    Format:
      categories:
      - [数据库深入]
      - [SQLServer]
    """
    start, end, existing_items = find_yaml_list_section(fm_lines, 'categories')
    if start is None:
        print("    WARNING: 'categories:' section not found")
        return False

    # Collect existing categories
    existing_cats = {v for _, v in existing_items}

    # For parallel categories, each becomes its own sub-list
    all_cats = existing_cats | set(new_categories)

    if all_cats == existing_cats:
        return False

    # Get indentation
    indent = '  '
    if existing_items:
        first_line = fm_lines[existing_items[0][0]]
        indent_match = re.match(r'^(\s+)-\s+', first_line)
        if indent_match:
            indent = indent_match.group(1)

    # Rebuild categories section as parallel categories
    new_lines = ['categories:']
    for cat in sorted(all_cats):
        new_lines.append(f'{indent}- [{cat}]')

    fm_lines[start:end] = new_lines
    return True


def process_file(filepath, tags_to_add=None, categories_to_add=None):
    """Read, modify, and write a single markdown file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    fm_lines, body_start = parse_frontmatter(content)
    if not fm_lines:
        print(f"  SKIP: no frontmatter -> {filepath}")
        return False, []

    changes = []
    modified = False

    if tags_to_add:
        if add_to_yaml_list(fm_lines, 'tags', tags_to_add):
            changes.extend(tags_to_add)
            modified = True

    if categories_to_add:
        if set_parallel_categories(fm_lines, categories_to_add):
            changes.extend(categories_to_add)
            modified = True

    if not modified:
        return False, []

    # Reconstruct content
    rest_lines = content.split('\n')[body_start:]
    new_content = '\n'.join(fm_lines) + '\n' + '\n'.join(rest_lines)

    return True, changes


def write_file(filepath, fm_lines, rest_lines):
    """Write modified content back to file."""
    new_content = '\n'.join(fm_lines) + '\n' + '\n'.join(rest_lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)


def main():
    parser = argparse.ArgumentParser(description='Add tags/categories to Hexo posts')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without writing')
    args = parser.parse_args()

    # ===================================================================
    # TAG_MAP: { relative_path_from__posts: {tags: [...], categories: [...]} }
    # ===================================================================
    TAG_MAP = {}

    # --- pgsql/ (53 files) ---
    pgsql_tags = {
        # Root - keyword matched
        'pgsql/wal机制浅析.md': ['WAL'],
        'pgsql/postgresql——流复制和wal日志（八）.md': ['流复制', 'WAL', '复制'],
        'pgsql/pg_replication.md': ['复制', '流复制'],
        'pgsql/postgresql启动流程.md': ['启动流程', '源码'],
        'pgsql/postgresql源码编译.md': ['源码编译', '源码'],
        'pgsql/Postgres中postmaster代码解析(--boot和--single).md': ['postmaster', '源码'],
        'pgsql/pg源码对象管理.md': ['源码'],
        'pgsql/pg_io_调优.md': ['性能调优'],
        'pgsql/数据库崩溃恢复.md': ['崩溃恢复'],
        'pgsql/checkpoint机制浅析.md': ['Checkpoint'],
        'pgsql/pg_complie_and_run.md': ['源码编译'],
        'pgsql/PostgreSQL 时间线解析.md': ['PITR'],
        'pgsql/pgsql_main_structure.md': [],
        'pgsql/postgresql基操.md': [],
        'pgsql/sql_test.md': [],
        'pgsql/insert_data.md': [],  # not really executor content without reading it

        # replication/
        'pgsql/replication/postgresql流复制同异步分析.md': ['异步复制', '流复制', '复制'],
        'pgsql/replication/PostgreSQL 同步流复制原理和代码浅析-阿里云开发者社区.md': ['同步流复制', '流复制', '复制'],
        'pgsql/replication/pg_slot.md': ['复制槽'],
        'pgsql/replication/PostgreSQL复制槽实操.md': ['复制槽'],
        'pgsql/replication/pg_walreceiver.md': ['WalReceiver'],
        'pgsql/replication/PostgreSQL数据库复制——后台一等公民进程WalReceiver&startup交互_postgressql walreceive线程_肥叔菌的博客-CSDN博客.md': ['WalReceiver'],
        'pgsql/replication/pg_walsender.md': ['WalSender'],
        'pgsql/replication/PostgreSQL的后台进程walsender分析 - 关系型数据库 - 亿速云.md': ['WalSender'],
        'pgsql/replication/pg_replication_keepalive.md': ['keepalive', '流复制'],
        'pgsql/replication/pg_logic_decode.md': ['逻辑解码', '逻辑复制'],
        'pgsql/replication/详解完整恢复及基于时间点的恢复.md': ['PITR'],
        'pgsql/replication/docker搭建Postgresql主备集群.md': ['复制'],
        'pgsql/replication/postgresql startup处理 - postgresql内核分析 - SegmentFault 思否.md': ['源码'],
        'pgsql/replication/Postgresql存储、索引及系统优化、主备切换.md': ['MVCC', '性能调优'],

        # storage/
        'pgsql/storage/pgsql_storage.md': ['存储'],
        'pgsql/storage/full_page_writes.md': ['full_page_writes'],
        'pgsql/storage/pg_checksum.md': ['pg_checksum'],
        'pgsql/storage/pg共享内存.md': ['共享内存'],
        'pgsql/storage/PosgreSQL FSM文件解析 – 蛋挞.md': ['FSM', '存储'],
        'pgsql/storage/xlog.md': ['WAL'],
        'pgsql/storage/干货  PostgreSQL数据表文件底层结构布局分析 - 知乎.md': ['存储'],
        'pgsql/storage/file/pgsql_page.md': ['存储'],
        'pgsql/storage/mm/pg_page.md': ['共享内存'],
        'pgsql/storage/mm/pgsql内存管理.md': ['共享内存'],

        # process/
        'pgsql/process/BgWriter.md': ['BgWriter'],
        'pgsql/process/Checkpoint.md': ['Checkpoint'],
        'pgsql/process/WalWriter.md': ['WalWriter'],

        # executor/
        'pgsql/executor/PostgreSQL的insert语句执行过程分析 - 墨天轮.md': ['executor'],

        # debug/
        'pgsql/debug/code-server调试postgresql.md': ['debug'],

        # ha/
        'pgsql/ha/repmgr实现原理.md': ['repmgr'],

        # extension/
        'pgsql/extension/pgsql扩展.md': ['扩展'],

        # kernel/
        'pgsql/kernel/Postgresql触发器详解.md': ['触发器'],

        # repmgr/
        'pgsql/repmgr/pgsql_repmgr.md': ['repmgr'],
        'pgsql/repmgr/repmgr_cluster.md': ['repmgr'],

        # stats/
        'pgsql/stats/stats.md': ['统计信息'],

        # pg_command/ - no new tags
        'pgsql/pg_command/pg_ctl.md': [],
        'pgsql/pg_command/initdb.md': [],
    }

    # --- db/ (44 files) ---
    db_tags = {
        # logical_decode/
        'db/logical_decode/逻辑复制源码分析.md': ['逻辑复制'],
        'db/logical_decode/postgresql逻辑复制-DML.md': ['逻辑复制'],
        'db/logical_decode/逻辑复制解惑.md': ['逻辑复制'],
        'db/logical_decode/逻辑复制验证步骤.md': ['逻辑复制'],
        'db/logical_decode/逻辑复制支持ddl问题.md': ['逻辑复制', '逻辑解码'],
        'db/logical_decode/逻辑复制支持DDL需求分析.md': ['逻辑复制'],
        'db/logical_decode/逻辑复制支持DDL开发交付计划.md': ['逻辑复制'],
        'db/logical_decode/支持ddl评审相关问题.md': ['逻辑复制', '逻辑解码'],
        'db/logical_decode/指定列同步对逻辑复制支持DDL的影响.md': ['逻辑复制'],
        'db/logical_decode/polardb逻辑解码源码解读.md': ['polardb', '逻辑解码'],
        'db/logical_decode/ai逻辑解码.md': ['逻辑解码'],
        'db/logical_decode/LogLogicalMessage详解.md': ['LogLogicalMessage', '逻辑解码'],
        'db/logical_decode/逻辑解码.md': ['逻辑解码'],
        'db/logical_decode/逻辑解码支持DDL.md': ['逻辑解码', '逻辑复制'],
        'db/logical_decode/pg15逻辑复制支持DDL.md': ['逻辑复制', '逻辑解码'],
        'db/logical_decode/pglogical详解.md': ['pglogical', '逻辑复制'],
        'db/logical_decode/pglogical支持DDL搭建教程.md': ['pglogical', '逻辑复制'],
        'db/logical_decode/pglogical.so.md': ['pglogical'],
        'db/logical_decode/逻辑解码DDL-Replay框架设计.md': ['DDL-Replay', '逻辑解码', '双向同步'],
        'db/logical_decode/逻辑解码ddl replay支持sqlserver模式.md': ['DDL-Replay', '逻辑解码'],
        'db/logical_decode/DDL.md': ['逻辑解码'],
        'db/logical_decode/logical_use.md': ['逻辑复制'],
        # ai_coding/
        'db/logical_decode/ai_coding/ddl_design_improve.md': ['DDL-Replay', '逻辑复制', '双向同步'],
        'db/logical_decode/ai_coding/逻辑复制支持DDLAI提示词.md': ['逻辑复制'],
        'db/logical_decode/ai_coding/ddl存储生命周期.md': ['逻辑解码', '逻辑复制'],
        'db/logical_decode/ai_coding/ddl写入wal日志的影响.md': ['逻辑解码', 'WAL'],
        'db/logical_decode/ai_coding/逻辑复制支持ddl ai配置流程.md': ['逻辑复制'],
        'db/logical_decode/ai_coding/逻辑复制支持DDL概要设计.md': ['逻辑复制', 'DDL-Replay'],
        'db/logical_decode/ai_coding/逻辑复制支持同步系统表概要设计.md': ['逻辑复制'],
        'db/logical_decode/ai_coding/新增逻辑复制同步系统表.md': ['逻辑复制'],

        # sqlserver/ (also add SQLServer category)
        'db/sqlserver/sqlserver模式逻辑复制支持ddl.md': ['逻辑复制'],
        'db/sqlserver/逻辑复制同步ddl适配bbf面临的挑战.md': ['逻辑复制'],
        'db/sqlserver/支持逻辑复制同步ddl适配sqlserver方案.md': ['逻辑复制'],
        'db/sqlserver/babelfish ddl已知限制.md': [],
        'db/sqlserver/bbf创建分区表.md': [],
        'db/sqlserver/内核执行babelfish上下文需要考虑的问题.md': [],

        # postgresql/
        'db/postgresql/使用meson编译pg.md': ['源码编译'],
        'db/postgresql/part1.md': ['源码'],
        'db/postgresql/pg常用函数.md': [],

        # mysql/ (also add MySQL category)
        'db/mysql/macos安装mysql.md': [],

        # taos/ (also add TDengine category)
        'db/taos/taos基本使用.md': [],

        # root
        'db/ddl同步架构.md': ['双向同步', '逻辑复制', 'DDL-Replay'],
        'db/命名空间.md': ['命名空间'],
        'db/多数据库模式命名空间问题.md': ['命名空间'],
    }

    # --- openguass/ (4 files) ---
    openguass_tags = {
        'openguass/openguass dcf启动详解.md': ['DCF'],
        'openguass/opengauss dcf搭建 - 墨天轮.md': ['DCF'],
        'openguass/openguass架构详解.md': [],
        'openguass/openguass升级机制.md': [],
    }

    # --- cluster/ (relevant files only) ---
    cluster_tags = {
        'cluster/DCF/一文读懂openguass dcf网络模块.md': ['DCF'],
        'cluster/DCF/dcf投票系统详解.md': ['DCF'],
        'cluster/DCF/dcf写入机制.md': ['DCF'],
        'cluster/DCF/dcf运行机制.md': ['DCF'],
        'cluster/DCF/openguass dcf源码阅读.md': ['DCF', '源码'],
        'cluster/DCF/常用压缩算法编程.md': ['压缩'],
        'cluster/raft/raft重要概念.md': ['Raft'],
        'cluster/raft/raft协议动态调整quorum.md': ['Raft'],
        'cluster/raft/c-raft分布式存储方案.md': ['C-Raft', 'Raft'],
        'cluster/raft/c-rart.md': ['Raft', 'C-Raft'],
        'cluster/ha/ha元信息常见存储方式.md': ['HA'],
        'cluster/ha/调整corosync网络波动时间操作文档.md': ['HA'],
        'cluster/ha/业界高可用解决方案.md': ['HA'],
        'cluster/ha/中移动数据库停库问题分析.md': ['HA'],
        'cluster/postgresql/postgresql伪双写.md': ['伪双写'],
        'cluster/postgresql/haproxy支持postgresql伪双写.md': ['HAProxy', '伪双写'],
        'cluster/postgresql/haproxy使用extern-check支持伪双写配置验证.md': ['HAProxy', '伪双写'],
        'cluster/postgresql/事务管理.md': ['事务管理', '并发控制', '锁'],
        'cluster/multi_cluster/多地多中心方案调研.md': ['多中心'],
        'cluster/repmgr网络割裂问题.md': ['repmgr'],
    }

    # --- database/ (1 file) ---
    database_tags = {
        'database/polardb竞争力分析.md': ['polardb'],
    }

    # --- Category additions (for MySQL, SQLServer, TDengine pages) ---
    category_additions = {
        'db/sqlserver/sqlserver模式逻辑复制支持ddl.md': ['SQLServer'],
        'db/sqlserver/逻辑复制同步ddl适配bbf面临的挑战.md': ['SQLServer'],
        'db/sqlserver/支持逻辑复制同步ddl适配sqlserver方案.md': ['SQLServer'],
        'db/sqlserver/babelfish ddl已知限制.md': ['SQLServer'],
        'db/sqlserver/bbf创建分区表.md': ['SQLServer'],
        'db/sqlserver/内核执行babelfish上下文需要考虑的问题.md': ['SQLServer'],
        'db/mysql/macos安装mysql.md': ['MySQL'],
        'db/taos/taos基本使用.md': ['TDengine'],
    }

    # Merge all
    for path, tags in {**pgsql_tags, **db_tags, **openguass_tags, **cluster_tags, **database_tags}.items():
        TAG_MAP[path] = {'tags': tags}

    # Add categories
    for path, cats in category_additions.items():
        if path not in TAG_MAP:
            TAG_MAP[path] = {}
        TAG_MAP[path]['categories'] = cats

    # ===================================================================
    # Process files
    # ===================================================================
    modified_files = []
    unchanged_files = []
    not_found = []

    for rel_path, config in TAG_MAP.items():
        abs_path = os.path.join(SRC, rel_path)
        if not os.path.exists(abs_path):
            not_found.append(rel_path)
            continue

        tags = config.get('tags', [])
        cats = config.get('categories', [])

        if not tags and not cats:
            unchanged_files.append((rel_path, 'no changes needed'))
            continue

        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        fm_lines, body_start = parse_frontmatter(content)
        if not fm_lines:
            unchanged_files.append((rel_path, 'no frontmatter'))
            continue

        changes_made = []
        file_modified = False

        if tags:
            if add_to_yaml_list(fm_lines, 'tags', tags):
                changes_made.append(f'tags: +{tags}')
                file_modified = True

        if cats:
            if set_parallel_categories(fm_lines, cats):
                changes_made.append(f'categories: +{cats}')
                file_modified = True

        if not file_modified:
            unchanged_files.append((rel_path, 'tags/categories already present'))
            continue

        if not args.dry_run:
            rest_lines = content.split('\n')[body_start:]
            write_file(abs_path, fm_lines, rest_lines)

        modified_files.append((rel_path, changes_made))
        print(f"  MODIFIED: {rel_path} -> {', '.join(changes_made)}")

    # ===================================================================
    # Summary
    # ===================================================================
    print(f"\n{'=' * 60}")
    print(f"SUMMARY ({'DRY RUN - no files modified' if args.dry_run else 'Files modified'})")
    print(f"{'=' * 60}")
    print(f"  Modified:  {len(modified_files)}")
    print(f"  Unchanged: {len(unchanged_files)}")
    print(f"  Not found: {len(not_found)}")

    if not_found:
        print(f"\n  NOT FOUND:")
        for f in not_found:
            print(f"    {f}")

    return 0


if __name__ == '__main__':
    sys.exit(main())

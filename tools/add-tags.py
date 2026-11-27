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
        'source-tracks/postgresql/L5-wal-and-recovery/wal机制浅析.md': ['WAL'],
        'source-tracks/postgresql/L6-replication-ha/postgresql——流复制和wal日志（八）.md': ['流复制', 'WAL', '复制'],
        'source-tracks/postgresql/L6-replication-ha/pg_replication.md': ['复制', '流复制'],
        'source-tracks/postgresql/L1-getting-started/postgresql启动流程.md': ['启动流程', '源码'],
        'source-tracks/postgresql/L1-getting-started/postgresql源码编译.md': ['源码编译', '源码'],
        'source-tracks/postgresql/L1-getting-started/Postgres中postmaster代码解析(--boot和--single).md': ['postmaster', '源码'],
        'source-tracks/postgresql/L2-storage-engine/pg源码对象管理.md': ['源码'],
        'source-tracks/postgresql/L8-extensions-perf/pg_io_调优.md': ['性能调优'],
        'source-tracks/postgresql/L5-wal-and-recovery/数据库崩溃恢复.md': ['崩溃恢复'],
        'source-tracks/postgresql/L5-wal-and-recovery/checkpoint机制浅析.md': ['Checkpoint'],
        'source-tracks/postgresql/L1-getting-started/pg_complie_and_run.md': ['源码编译'],
        'source-tracks/postgresql/L5-wal-and-recovery/PostgreSQL 时间线解析.md': ['PITR'],
        'source-tracks/postgresql/L1-getting-started/pgsql_main_structure.md': [],
        'source-tracks/postgresql/L1-getting-started/postgresql基操.md': [],
        'source-tracks/postgresql/L8-extensions-perf/sql_test.md': [],
        'source-tracks/postgresql/L3-index-and-query/insert_data.md': [],  # not really executor content without reading it

        # replication/
        'source-tracks/postgresql/L6-replication-ha/postgresql流复制同异步分析.md': ['异步复制', '流复制', '复制'],
        'source-tracks/postgresql/L6-replication-ha/PostgreSQL 同步流复制原理和代码浅析-阿里云开发者社区.md': ['同步流复制', '流复制', '复制'],
        'source-tracks/postgresql/L6-replication-ha/pg_slot.md': ['复制槽'],
        'source-tracks/postgresql/L6-replication-ha/PostgreSQL复制槽实操.md': ['复制槽'],
        'source-tracks/postgresql/L6-replication-ha/pg_walreceiver.md': ['WalReceiver'],
        'source-tracks/postgresql/L6-replication-ha/PostgreSQL数据库复制——后台一等公民进程WalReceiver&startup交互_postgressql walreceive线程_肥叔菌的博客-CSDN博客.md': ['WalReceiver'],
        'source-tracks/postgresql/L6-replication-ha/pg_walsender.md': ['WalSender'],
        'source-tracks/postgresql/L6-replication-ha/PostgreSQL的后台进程walsender分析 - 关系型数据库 - 亿速云.md': ['WalSender'],
        'source-tracks/postgresql/L6-replication-ha/pg_replication_keepalive.md': ['keepalive', '流复制'],
        'source-tracks/postgresql/L6-replication-ha/pg_logic_decode.md': ['逻辑解码', '逻辑复制'],
        'source-tracks/postgresql/L6-replication-ha/详解完整恢复及基于时间点的恢复.md': ['PITR'],
        'source-tracks/postgresql/L6-replication-ha/docker搭建Postgresql主备集群.md': ['复制'],
        'source-tracks/postgresql/L6-replication-ha/postgresql startup处理 - postgresql内核分析 - SegmentFault 思否.md': ['源码'],
        'source-tracks/postgresql/L6-replication-ha/Postgresql存储、索引及系统优化、主备切换.md': ['MVCC', '性能调优'],

        # storage/
        'source-tracks/postgresql/L2-storage-engine/pgsql_storage.md': ['存储'],
        'source-tracks/postgresql/L5-wal-and-recovery/full_page_writes.md': ['full_page_writes'],
        'source-tracks/postgresql/L5-wal-and-recovery/pg_checksum.md': ['pg_checksum'],
        'source-tracks/postgresql/L2-storage-engine/pg共享内存.md': ['共享内存'],
        'source-tracks/postgresql/L2-storage-engine/PosgreSQL FSM文件解析 – 蛋挞.md': ['FSM', '存储'],
        'source-tracks/postgresql/L5-wal-and-recovery/xlog.md': ['WAL'],
        'source-tracks/postgresql/L2-storage-engine/干货  PostgreSQL数据表文件底层结构布局分析 - 知乎.md': ['存储'],
        'source-tracks/postgresql/L2-storage-engine/file/pgsql_page.md': ['存储'],
        'source-tracks/postgresql/L2-storage-engine/mm/pg_page.md': ['共享内存'],
        'source-tracks/postgresql/L2-storage-engine/mm/pgsql内存管理.md': ['共享内存'],

        # process/
        'source-tracks/postgresql/L5-wal-and-recovery/BgWriter.md': ['BgWriter'],
        'source-tracks/postgresql/L5-wal-and-recovery/Checkpoint.md': ['Checkpoint'],
        'source-tracks/postgresql/L5-wal-and-recovery/WalWriter.md': ['WalWriter'],

        # executor/
        'source-tracks/postgresql/L3-index-and-query/PostgreSQL的insert语句执行过程分析 - 墨天轮.md': ['executor'],

        # debug/
        'source-tracks/postgresql/L1-getting-started/code-server调试postgresql.md': ['debug'],

        # ha/
        'source-tracks/postgresql/L6-replication-ha/repmgr实现原理.md': ['repmgr'],

        # extension/
        'source-tracks/postgresql/L8-extensions-perf/pgsql扩展.md': ['扩展'],

        # kernel/
        'source-tracks/postgresql/L3-index-and-query/Postgresql触发器详解.md': ['触发器'],

        # repmgr/
        'source-tracks/postgresql/L6-replication-ha/pgsql_repmgr.md': ['repmgr'],
        'source-tracks/postgresql/L6-replication-ha/repmgr_cluster.md': ['repmgr'],

        # stats/
        'source-tracks/postgresql/L3-index-and-query/stats.md': ['统计信息'],

        # pg_command/ - no new tags
        'source-tracks/postgresql/L1-getting-started/pg_ctl.md': [],
        'source-tracks/postgresql/L1-getting-started/initdb.md': [],
    }

    # --- db/ (44 files) ---
    db_tags = {
        # logical_decode/
        'source-tracks/postgresql/L7-logical-replication/逻辑复制源码分析.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/postgresql逻辑复制-DML.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/逻辑复制解惑.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/逻辑复制支持ddl问题.md': ['逻辑复制', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/逻辑复制支持DDL需求分析.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/支持ddl评审相关问题.md': ['逻辑复制', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/指定列同步对逻辑复制支持DDL的影响.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/polardb逻辑解码源码解读.md': ['polardb', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/ai逻辑解码.md': ['逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/LogLogicalMessage详解.md': ['LogLogicalMessage', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/逻辑解码.md': ['逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/逻辑解码支持DDL.md': ['逻辑解码', '逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/pg15逻辑复制支持DDL.md': ['逻辑复制', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/pglogical详解.md': ['pglogical', '逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/pglogical支持DDL搭建教程.md': ['pglogical', '逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/pglogical.so.md': ['pglogical'],
        'source-tracks/postgresql/L7-logical-replication/逻辑解码DDL-Replay框架设计.md': ['DDL-Replay', '逻辑解码', '双向同步'],
        'source-tracks/postgresql/L7-logical-replication/逻辑解码ddl replay支持sqlserver模式.md': ['DDL-Replay', '逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/DDL.md': ['逻辑解码'],
        'source-tracks/postgresql/L7-logical-replication/logical_use.md': ['逻辑复制'],
        # ai_coding/
        'source-tracks/postgresql/L7-logical-replication/ai_coding/ddl_design_improve.md': ['DDL-Replay', '逻辑复制', '双向同步'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/逻辑复制支持DDLAI提示词.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/ddl存储生命周期.md': ['逻辑解码', '逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/ddl写入wal日志的影响.md': ['逻辑解码', 'WAL'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/逻辑复制支持ddl ai配置流程.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/逻辑复制支持DDL概要设计.md': ['逻辑复制', 'DDL-Replay'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/逻辑复制支持同步系统表概要设计.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/ai_coding/新增逻辑复制同步系统表.md': ['逻辑复制'],

        # sqlserver/ (also add SQLServer category)
        'source-tracks/postgresql/L7-logical-replication/sqlserver/sqlserver模式逻辑复制支持ddl.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/逻辑复制同步ddl适配bbf面临的挑战.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/支持逻辑复制同步ddl适配sqlserver方案.md': ['逻辑复制'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/babelfish ddl已知限制.md': [],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/bbf创建分区表.md': [],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/内核执行babelfish上下文需要考虑的问题.md': [],

        # postgresql/
        'source-tracks/postgresql/L1-getting-started/使用meson编译pg.md': ['源码编译'],
        'source-tracks/postgresql/L1-getting-started/part1.md': ['源码'],
        'source-tracks/postgresql/L3-index-and-query/pg常用函数.md': [],

        # mysql/ (also add MySQL category)
        'source-tracks/postgresql/L8-extensions-perf/macos安装mysql.md': [],

        # taos/ (also add TDengine category)
        'source-tracks/postgresql/L8-extensions-perf/taos基本使用.md': [],

        # root
        'source-tracks/postgresql/L7-logical-replication/ddl同步架构.md': ['双向同步', '逻辑复制', 'DDL-Replay'],
        'source-tracks/postgresql/L1-getting-started/命名空间.md': ['命名空间'],
        'source-tracks/postgresql/L1-getting-started/多数据库模式命名空间问题.md': ['命名空间'],
    }

    # --- openguass/ (4 files) ---
    openguass_tags = {
        'source-tracks/distributed/L2-consensus/openguass dcf启动详解.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/opengauss dcf搭建 - 墨天轮.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/openguass架构详解.md': [],
        'source-tracks/distributed/L2-consensus/openguass升级机制.md': [],
    }

    # --- cluster/ (relevant files only) ---
    cluster_tags = {
        'source-tracks/distributed/L2-consensus/一文读懂openguass dcf网络模块.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/dcf投票系统详解.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/dcf写入机制.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/dcf运行机制.md': ['DCF'],
        'source-tracks/distributed/L2-consensus/openguass dcf源码阅读.md': ['DCF', '源码'],
        'source-tracks/distributed/L2-consensus/常用压缩算法编程.md': ['压缩'],
        'source-tracks/distributed/L2-consensus/raft重要概念.md': ['Raft'],
        'source-tracks/distributed/L2-consensus/raft协议动态调整quorum.md': ['Raft'],
        'source-tracks/distributed/L2-consensus/c-raft分布式存储方案.md': ['C-Raft', 'Raft'],
        'source-tracks/distributed/L2-consensus/c-rart.md': ['Raft', 'C-Raft'],
        'source-tracks/distributed/L3-ha-and-dr/ha元信息常见存储方式.md': ['HA'],
        'source-tracks/distributed/L3-ha-and-dr/调整corosync网络波动时间操作文档.md': ['HA'],
        'source-tracks/distributed/L3-ha-and-dr/业界高可用解决方案.md': ['HA'],
        'source-tracks/distributed/L3-ha-and-dr/中移动数据库停库问题分析.md': ['HA'],
        'source-tracks/distributed/L3-ha-and-dr/postgresql伪双写.md': ['伪双写'],
        'source-tracks/distributed/L3-ha-and-dr/haproxy支持postgresql伪双写.md': ['HAProxy', '伪双写'],
        'source-tracks/distributed/L3-ha-and-dr/haproxy使用extern-check支持伪双写配置验证.md': ['HAProxy', '伪双写'],
        'source-tracks/distributed/L3-ha-and-dr/事务管理.md': ['事务管理', '并发控制', '锁'],
        'source-tracks/distributed/L4-field-notes/多地多中心方案调研.md': ['多中心'],
        'source-tracks/distributed/L4-field-notes/repmgr网络割裂问题.md': ['repmgr'],
    }

    # --- database/ (1 file) ---
    database_tags = {
        'source-tracks/postgresql/L8-extensions-perf/polardb竞争力分析.md': ['polardb'],
    }

    # --- Category additions (for MySQL, SQLServer, TDengine pages) ---
    category_additions = {
        'source-tracks/postgresql/L7-logical-replication/sqlserver/sqlserver模式逻辑复制支持ddl.md': ['SQLServer'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/逻辑复制同步ddl适配bbf面临的挑战.md': ['SQLServer'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/支持逻辑复制同步ddl适配sqlserver方案.md': ['SQLServer'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/babelfish ddl已知限制.md': ['SQLServer'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/bbf创建分区表.md': ['SQLServer'],
        'source-tracks/postgresql/L7-logical-replication/sqlserver/内核执行babelfish上下文需要考虑的问题.md': ['SQLServer'],
        'source-tracks/postgresql/L8-extensions-perf/macos安装mysql.md': ['MySQL'],
        'source-tracks/postgresql/L8-extensions-perf/taos基本使用.md': ['TDengine'],
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

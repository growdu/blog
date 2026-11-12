"""集成测试：真的跑一遍 tools/sync-hexo.py，产物里真的带上 platforms / publish_on。

契约层说「母稿说了什么就透传什么」——这句话要由**真的跑一遍发布脚本**来验，
不是靠读代码。本文件用一份最小母稿语料跑完整的 sync-hexo.py，再检查
source/_posts/ 下生成出来的 front matter。

语料是合成的（跑全量 docs/ 要三分钟，不适合放进单元测试），
但跑的是**仓库里那一份真的** tools/sync-hexo.py。
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from publishkit.contract import (
    ContractFieldError,
    contract_from_fields,
    parse_front_matter,
    validate_fields,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "tools" / "sync-hexo.py"


def build_corpus(root: Path, drafts) -> None:
    """Write a minimal docs/ tree plus the config sync-hexo.py reads."""
    for rel, text in drafts.items():
        path = root / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    # sync-hexo.py 用 _config.matery.yml 生成关于页；缺了它脚本会中断。
    shutil.copy(REPO_ROOT / "_config.matery.yml", root / "_config.matery.yml")


def run_sync(root: Path) -> None:
    """Run the repository's sync-hexo.py over the corpus in ``root``."""
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "sync-hexo.py 失败：\n{}\n{}".format(
        result.stdout, result.stderr
    )


def read_post(root: Path, rel: str) -> str:
    path = root / "source" / "_posts" / rel
    assert path.is_file(), "sync-hexo.py 没有生成 {}".format(path)
    return path.read_text(encoding="utf-8")


PLAIN_DRAFT = """\
---
title: "普通一篇"
---

# 普通一篇

正文第一段。
"""

SCHEDULED_DRAFT = """\
---
title: "带发布计划的一篇"
platforms:
  - wechat
  - toutiao
publish_on: 2026-11-13
---

# 带发布计划的一篇

正文第一段。
"""


# --- 透传 ---------------------------------------------------------------


def test_sync_carries_platforms_and_publish_on(tmp_path):
    build_corpus(tmp_path, {"blog/scheduled.md": SCHEDULED_DRAFT})
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/scheduled.md"))

    assert fields["platforms"] == ["wechat", "toutiao"]
    assert fields["publish_on"] == "2026-11-13"


def test_passthrough_values_are_byte_identical_to_the_source(tmp_path):
    """含引号、含中文的值要**逐字**搬过去，不能被重新加引号或转义。"""
    draft = (
        "---\n"
        'title: "带引号的中文标题"\n'
        "platforms:\n"
        "  - wechat\n"
        '  - "toutiao"\n'
        'publish_on: "2026-11-13"\n'
        "---\n\n"
        "# 正文\n"
    )
    build_corpus(tmp_path, {"blog/quoted.md": draft})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/quoted.md")

    assert "  - wechat\n" in out
    assert '  - "toutiao"\n' in out
    assert 'publish_on: "2026-11-13"\n' in out


def test_platforms_without_publish_on(tmp_path):
    build_corpus(
        tmp_path,
        {"blog/only-platforms.md": '---\ntitle: x\nplatforms:\n  - wechat\n---\n\n正文\n'},
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/only-platforms.md")
    fields, _ = parse_front_matter(out)

    assert fields["platforms"] == ["wechat"]
    assert "publish_on" not in fields


def test_publish_on_without_platforms(tmp_path):
    build_corpus(
        tmp_path,
        {"blog/only-date.md": "---\ntitle: x\npublish_on: 2026-11-13\n---\n\n正文\n"},
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/only-date.md")
    fields, _ = parse_front_matter(out)

    assert fields["publish_on"] == "2026-11-13"
    assert "platforms" not in fields


def test_an_inline_platforms_list_is_carried_through_for_the_contract_to_reject(tmp_path):
    """内联列表不在格式规则里（§4.2）——但不能悄悄丢掉，要让契约层报错。"""
    build_corpus(
        tmp_path,
        {"blog/inline.md": "---\ntitle: x\nplatforms: [wechat, toutiao]\n---\n\n正文\n"},
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/inline.md")
    fields, _ = parse_front_matter(out)

    assert fields["platforms"] == "[wechat, toutiao]"


def test_an_indented_scalar_platforms_is_carried_through_for_the_contract_to_reject(tmp_path):
    """作者把 platforms 写成**缩进标量**时，不能静默丢掉。

    ``platforms:`` 下面缩进的 ``wechat`` 是 YAML 合法、也是作者最自然的写法
    （§4.2 规定的形态是 ``platforms:`` + ``  - wechat``）。丢掉它等于
    「这篇不发」，而作者以为自己写了——所以要**原样保留**，
    让契约层去报「platforms 必须是列表」，与内联列表走同一条路。
    """
    build_corpus(
        tmp_path,
        {"blog/indented.md": "---\ntitle: x\nplatforms:\n  wechat\n---\n\n正文\n"},
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/indented.md")
    fields, _ = parse_front_matter(out)

    # 保留下来了（不是丢掉）
    assert fields["platforms"] == "wechat"

    # 而且契约层看得见它、报得出错
    with pytest.raises(ContractFieldError) as excinfo:
        contract_from_fields(fields)
    assert "platforms 必须是列表" in str(excinfo.value)


def test_an_indented_scalar_publish_on_is_carried_through(tmp_path):
    """缩进标量的 publish_on 同样不能丢——它的值本身是合法的日期。"""
    build_corpus(
        tmp_path,
        {
            "blog/indented-date.md": "---\ntitle: x\npublish_on:\n"
            "  2026-11-13\n---\n\n正文\n"
        },
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/indented-date.md")
    fields, _ = parse_front_matter(out)

    assert fields["publish_on"] == "2026-11-13"


def test_an_indented_scalar_is_not_picked_up_from_another_key(tmp_path):
    """缩进标量只能来自**它自己那个 key** 下面——不能越界去捞别人的值。"""
    build_corpus(
        tmp_path,
        {
            "blog/neighbour.md": "---\ntitle: x\nplatforms:\n"
            "publish_on: 2026-11-13\n---\n\n正文\n"
        },
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/neighbour.md")
    fields, _ = parse_front_matter(out)

    assert "platforms" not in fields
    assert fields["publish_on"] == "2026-11-13"


def test_empty_values_are_dropped(tmp_path):
    """空值等于「没写」。

    ``platforms:`` 后面没有条目就是空列表（不是候选），``publish_on:`` 后面
    没有值就是没写。两种都不该在产物里留下一行空壳——留着会让下游以为
    「写了但值是空的」，那是两回事。
    """
    build_corpus(
        tmp_path,
        {"blog/empty.md": "---\ntitle: x\nplatforms:\npublish_on:\n---\n\n正文\n"},
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/empty.md")
    fields, _ = parse_front_matter(out)

    assert "platforms" not in out
    assert "publish_on" not in out
    assert "platforms" not in fields
    assert "publish_on" not in fields


def test_fields_outside_the_passthrough_list_are_not_carried(tmp_path):
    """白名单透传，不做全文转储——作者写别的字段不会被顺手搬走。

    §4.1 白名单里的字段**全部**要搬（平台 id 与发布日期早就通了，展示元数据
    这一轮接上），白名单外的字段一个都不许搬。
    """
    build_corpus(
        tmp_path,
        {
            "blog/extra.md": "---\n"
            'title: x\n'
            "tldr: 要被搬走的摘要\n"
            "description: 要被搬走的描述\n"
            "secret: 不该被搬走\n"
            "platforms:\n"
            "  - wechat\n"
            "---\n\n正文\n"
        },
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/extra.md")
    fields, _ = parse_front_matter(out)

    assert fields["tldr"] == "要被搬走的摘要"
    assert fields["description"] == "要被搬走的描述"
    assert "secret" not in fields
    assert "不该被搬走" not in out
    assert fields["platforms"] == ["wechat"]


# --- §4.1 的展示元数据通道 ------------------------------------------------


SHOWCASE_DRAFT = """\
---
title: "带展示元数据的一篇"
short_title: "短标题"
tldr: "一句话说清这篇在讲什么。"
description: "给 OG / Twitter 卡片用的摘要。"
difficulty: 3
cover: images/cover.jpg
reprintPolicy: cc_by_nd
kind: post
platforms:
  - wechat
publish_on: 2026-11-13
---

# 带展示元数据的一篇

正文第一段。
"""


def test_every_passthrough_field_of_4_1_reaches_the_product(tmp_path):
    """§4.1 的透传字段表有 10 个字段，全部要到达产物。

    §12 第 2 行的验收标准写的就是「真文章 → front matter 含
    tldr/description/difficulty」。
    """
    build_corpus(tmp_path, {"blog/showcase.md": SHOWCASE_DRAFT})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/showcase.md")
    fields, _ = parse_front_matter(out)

    assert fields["title"] == "带展示元数据的一篇"
    assert fields["short_title"] == "短标题"
    assert fields["tldr"] == "一句话说清这篇在讲什么。"
    assert fields["description"] == "给 OG / Twitter 卡片用的摘要。"
    assert fields["difficulty"] == "3"
    assert fields["cover"] == "images/cover.jpg"
    assert fields["reprintPolicy"] == "cc_by_nd"
    assert fields["kind"] == "post"
    assert fields["platforms"] == ["wechat"]
    assert fields["publish_on"] == "2026-11-13"


def test_the_carried_showcase_fields_satisfy_the_content_contract(tmp_path):
    """搬过去的字段要能被契约层读懂——这不是巧合，是接缝的定义。"""
    build_corpus(tmp_path, {"blog/showcase.md": SHOWCASE_DRAFT})
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/showcase.md"))
    contract = contract_from_fields(fields)

    assert contract.short_title == "短标题"
    assert contract.tldr == "一句话说清这篇在讲什么。"
    assert contract.description == "给 OG / Twitter 卡片用的摘要。"
    assert contract.difficulty == 3
    assert contract.cover == "images/cover.jpg"
    assert contract.reprint_policy == "cc_by_nd"


def test_values_outside_their_domain_are_carried_for_the_contract_to_reject(tmp_path):
    """值不在域内时（difficulty / reprintPolicy）要**原样搬过去**让契约层报错。

    悄悄丢掉更糟——丢了等于「这篇不发」，而作者以为自己写了。
    """
    build_corpus(
        tmp_path,
        {
            "blog/bad-values.md": "---\n"
            'title: x\n'
            "difficulty: 高\n"
            "reprintPolicy: 瞎写\n"
            "---\n\n正文\n"
        },
    )
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/bad-values.md")
    fields, _ = parse_front_matter(out)

    # 原样带过去了（不是丢掉）
    assert fields["difficulty"] == "高"
    assert fields["reprintPolicy"] == "瞎写"

    # 契约层看得见，并报得出错
    violations = validate_fields(fields)

    assert any("difficulty" in v for v in violations)
    assert any("reprintPolicy" in v for v in violations)


def test_a_draft_without_front_matter_gets_the_standard_front_matter(tmp_path):
    build_corpus(tmp_path, {"blog/bare.md": "# 没有 front matter\n\n正文。\n"})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/bare.md")
    fields, _ = parse_front_matter(out)

    assert set(fields) == {"title", "date", "author", "categories", "tags"}
    assert "platforms" not in out
    assert "publish_on" not in out


# --- 没有弄坏别的东西 ----------------------------------------------------


def test_posts_without_the_fields_keep_their_front_matter_unchanged(tmp_path):
    """没写这两个字段的母稿，front matter 必须与改动前逐字段一致。"""
    build_corpus(tmp_path, {"blog/plain.md": PLAIN_DRAFT})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/plain.md")
    fields, _ = parse_front_matter(out)

    assert set(fields) == {"title", "date", "author", "categories", "tags"}
    assert fields["title"] == "普通一篇"
    assert fields["author"] == "growdu"
    assert fields["categories"] == ["blog"]
    assert fields["tags"] == ["blog"]
    assert "platforms" not in out
    assert "publish_on" not in out


def test_the_existing_front_matter_shape_is_unchanged(tmp_path):
    """front matter 的骨架一行都不能动——多一行少一行都会改掉站点渲染。"""
    build_corpus(tmp_path, {"blog/plain.md": PLAIN_DRAFT})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/plain.md")

    assert re.match(
        r'^---\ntitle: "普通一篇"\ndate: \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\n'
        r'author: growdu\ncategories:\n  - blog\ntags:\n  - blog\n---\n',
        out,
    )


def test_the_passthrough_does_not_disturb_the_title_override(tmp_path):
    """作者在 front matter 里写的 title 仍然优先于正文里的 H1。"""
    build_corpus(
        tmp_path,
        {"blog/titled.md": '---\ntitle: "front matter 的标题"\n---\n\n# 正文里的 H1\n'},
    )
    run_sync(tmp_path)

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/titled.md"))

    assert fields["title"] == "front matter 的标题"


def test_the_body_is_unchanged_by_the_passthrough(tmp_path):
    build_corpus(tmp_path, {"blog/scheduled.md": SCHEDULED_DRAFT})
    run_sync(tmp_path)

    out = read_post(tmp_path, "blog/scheduled.md")

    assert "正文第一段。" in out
    assert out.rstrip().endswith("正文第一段。")


def test_the_generated_post_satisfies_the_content_contract(tmp_path):
    """产物本身要能被内容契约读懂——这不是巧合，是接缝的定义。"""
    build_corpus(tmp_path, {"blog/scheduled.md": SCHEDULED_DRAFT})
    run_sync(tmp_path)

    from publishkit.contract import contract_from_fields

    fields, _ = parse_front_matter(read_post(tmp_path, "blog/scheduled.md"))
    contract = contract_from_fields(fields)

    assert contract.platforms == ("wechat", "toutiao")
    assert contract.publish_on == "2026-11-13"
    assert contract.is_publish_candidate is True


def test_sync_script_does_not_import_the_contract_layer():
    """站点构建脚本不许 import 契约层——两边互不依赖，契约层不是构建期依赖。"""
    source = SYNC_SCRIPT.read_text(encoding="utf-8")

    assert SYNC_SCRIPT.is_file()
    assert not re.search(r"^\s*(import|from)\s+publishkit", source, re.MULTILINE), (
        "sync-hexo.py 不许 import 契约层"
    )


@pytest.mark.parametrize("draft_name", ["scheduled.md", "plain.md"])
def test_every_post_is_written(tmp_path, draft_name):
    drafts = {
        "blog/scheduled.md": SCHEDULED_DRAFT,
        "blog/plain.md": PLAIN_DRAFT,
    }
    build_corpus(tmp_path, drafts)
    run_sync(tmp_path)

    assert (tmp_path / "source" / "_posts" / "blog" / draft_name).is_file()

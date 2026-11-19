"""精简索引 ``search-lite.json`` 还得有人守着。

**背景**：全站搜索有两个消费者，索引不是一个：

* **顶部导航的搜索弹窗**（``_partial/search.ejs``）用 ``search.json``
  —— 全文索引，实测 13,490,267 字节，gzip 后 4.2MB。首次击键才下载，
  所以那个弹窗是「按需加载」。
* **404 页的搜索框**（由 ``tools/sync-hexo.py`` 生成）用
  ``search-lite.json`` —— 约 80KB，每条只有 title / url / cat。

**2026-11-19**：首屏那个只搜标题的搜索框删掉了（顶部导航本来就有全文
搜索，首屏再来一个是同一个去处的第二个入口）。它曾经是精简索引的第二
个消费者 —— 现在只剩 404 页这一个。

于是这份索引还得留着、还得是那个形状：404 页的 JS 是按
``title / url / cat`` 三个字段读它的，少一个字段它就静默地搜不出东西
（页面上显示「没有匹配的文章」，看起来像没有结果，其实是坏的）。

原来守着这块的 ``tests/test_home_search_box.py`` 跟着首屏搜索框一起
退休了（它有一半的用例是在 node 里跑首屏那段 JS，那段 JS 已经不在了）；
索引本身的守卫搬到这个文件里。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC_SCRIPT = REPO / "tools" / "sync-hexo.py"

DRAFT = "---\ntitle: {title}\n---\n\n{body}\n"

CORPUS = {
    "db/postgresql.md": DRAFT.format(title="PostgreSQL 数据库", body="数据库正文。"),
    "cluster/paxos.md": DRAFT.format(title="Paxos 共识", body="共识协议正文。"),
    "life/intro.md": DRAFT.format(title="编程之路", body="随笔。"),
}


def test_the_lite_index_has_the_fields_the_search_needs(tmp_path):
    """精简索引每条都要有 title / url / cat。

    索引是 sync 生成的（``source/`` 是 gitignore 的，CI 里没有现成文件），
    所以这里造一个临时语料跑一遍 sync，看它真的写出这三个字段。
    """
    for rel, text in CORPUS.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    shutil.copy(REPO / "_config.matery.yml", tmp_path / "_config.matery.yml")

    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "sync-hexo.py 失败：\n{}\n{}".format(
        result.stdout, result.stderr
    )

    index = json.loads(
        (tmp_path / "source" / "search-lite.json").read_text(encoding="utf-8")
    )

    assert index, "精简索引是空的"
    for entry in index:
        assert set(entry) == {"title", "url", "cat"}, entry
        assert entry["title"], entry
        assert entry["url"].startswith("/"), entry


def test_the_404_page_still_uses_the_lite_index():
    """404 页的搜索还在抓精简索引 —— 不是全文索引，也不是没有。

    404 页原来抓的是 ``/search.xml``，站点里根本没有那个文件，于是这个
    fetch 永远失败、永远跳 Google（国内不可用）：等于 404 页没有搜索。
    """
    sync = SYNC_SCRIPT.read_text(encoding="utf-8")

    assert "fetch('/search-lite.json')" in sync, (
        "sync-hexo.py 里 404 页不再抓精简索引了 —— 那页的搜索是坏的"
    )
    assert "fetch('/search.json')" not in sync, (
        "404 页不该去下 13.5MB 的全文索引 —— 搜一个词要等 4.2MB"
    )

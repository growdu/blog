"""GoatCounter 的真实 PV 快照：抓取、归一化、落到站点里。

**背景**：阶段 1 的 Task 6。

线上侧栏「最热文章」那一栏的🔥数字，是 ``patch-theme.py`` 里的一句
``Math.max(5, Math.floor(字数 / 50))``——**它是文章的字数除以 50**。
一篇十万字的文章显示「🔥 2000」，读者以为有两千人读过它。

真实的两套统计是有的：GoatCounter（页面在收）和不蒜子（页面在显示），
但它们的数字都是**页面运行时**由脚本填的，构建期拿不到——于是模板
只好自己编一个。

**这个任务把假数字删掉**：阅读量改读 ``data/view-counts.json``
（GoatCounter 的真实 PV 快照），快照里没有的页面**不显示**这一格，
不显示一个假的🔥。

快照由 ``tools/fetch-view-counts.py`` 生成。选 GoatCounter 而不是不蒜子：
它的 API 是**只读**的，不会像不蒜子那样每查一次就给那个路径 +1。

**2026-11-18**：侧栏与首页的「近期热门」tab 都已经删掉了（站点做减法），
这两个读者随之消失。**快照本身照旧抓、照旧存、照旧校验**——
它是一份独立的数据资产，不是页面的一部分；哪天要再做一个「最热」入口，
直接读它就行，不必重新造一遍抓取器。

这里断言的是**行为**：抓取器怎么解析、怎么归一化路径、快照怎么进到
``source/_data/``、刷新工作流怎么保证不把好数据抹掉。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FETCHER = REPO_ROOT / "tools" / "fetch-view-counts.py"
SNAPSHOT = REPO_ROOT / "data" / "view-counts.json"


# --- 1. 抓取器 --------------------------------------------------------------


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("fetch_view_counts", FETCHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_fetcher_parses_a_goatcounter_response():
    """喂一个假的 GoatCounter 响应，断言解析出的 path→PV 映射。

    GoatCounter 的 ``/api/v0/stats/hits`` 返回 ``{"hits": [{"path": ..., "count": ...}]}``。
    """
    fetcher = _load_fetcher()
    payload = {
        "hits": [
            {
                "path": "/2026/08/18/source-tracks/postgresql/index-and-query/learning-path/03-query-pipeline/",
                "count": 42,
                "event": False,
                "path_id": 7,
            },
            {"path": "/archives/", "count": 3, "event": False, "path_id": 9},
        ],
        "more": False,
        "total": 2,
    }

    counts = fetcher.parse_counts(payload)

    assert counts["2026/08/18/source-tracks/postgresql/index-and-query/learning-path/03-query-pipeline"] == 42
    assert counts["archives"] == 3


def test_the_fetcher_normalizes_the_path_the_same_way_the_template_does():
    """快照里的键要和模板算出来的键**一模一样**，否则永远匹配不上。

    hexo 的 ``post.path`` 是 ``2026/08/18/db/aaa/index.html``，
    GoatCounter 记的是 ``/2026/08/18/db/aaa/``——两边都要归一到
    ``2026/08/18/db/aaa``。
    """
    fetcher = _load_fetcher()

    assert fetcher.normalize_path("/2026/08/18/db/aaa/") == "2026/08/18/db/aaa"
    assert fetcher.normalize_path("2026/08/18/db/aaa/index.html") == "2026/08/18/db/aaa"
    assert fetcher.normalize_path("/2026/08/18/db/aaa") == "2026/08/18/db/aaa"


# --- 2. 快照怎么进到站点里 -------------------------------------------------


def test_the_snapshot_file_is_a_valid_counts_object():
    """快照文件必须存在，且长成 ``{"counts": {...}}`` 的样子。"""
    assert SNAPSHOT.is_file(), "缺少 data/view-counts.json"

    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert isinstance(data.get("counts"), dict), data


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_hexo_view_counts", REPO_ROOT / "tools" / "sync-hexo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_snapshot_reaches_the_hexo_data_dir(tmp_path):
    """快照必须被复制到 ``source/_data/``——hexo 才会把它挂到 site.data 上。

    复制不到 ``_data/`` 的话，模板里的 ``site.data['view-counts']``
    永远是 undefined，页面会一直显示不出阅读量。
    """
    sync = _load_sync()

    dest = sync.copy_view_counts_snapshot(src_dir=str(tmp_path))

    assert dest is not None, "快照没有被复制到 source/_data/"
    copied = json.loads(Path(dest).read_text(encoding="utf-8"))
    assert copied == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


# --- 3. 中文路径：GoatCounter 返回百分号编码，hexo 的 post.path 是原始 Unicode ---


def test_the_snapshot_key_matches_the_template_for_a_chinese_path():
    """GoatCounter 的 API 返回的是**百分号编码**的路径，hexo 的 ``post.path``
    是**原始 Unicode**。

    614 篇文章里有 358 篇（58.5%）的路径带中文。不解码的话，一多半的文章
    永远匹配不上——而且是**安静地**不匹配：「近期热门」只排那 42% 的 ASCII
    路径文章，看起来一切正常。
    """
    fetcher = _load_fetcher()

    assert fetcher.normalize_path(
        "/2022/04/13/source-tracks/postgresql/extensions-perf/pgsql%E6%89%A9%E5%B1%95/"
    ) == "2022/04/13/source-tracks/postgresql/extensions-perf/pgsql扩展"

    # 已经是原始 Unicode 的（有的 GoatCounter 实例存的是解码后的）也不能被改坏
    assert fetcher.normalize_path(
        "/2022/04/13/source-tracks/postgresql/extensions-perf/pgsql扩展/"
    ) == "2022/04/13/source-tracks/postgresql/extensions-perf/pgsql扩展"


def test_the_snapshot_key_matches_a_template_path_with_a_space():
    """带空格的路径同理（空格在 URL 里编码成 %20）。"""
    fetcher = _load_fetcher()

    assert fetcher.normalize_path("/2026/01/01/db/a%20b/") == "2026/01/01/db/a b"


def test_a_broken_escape_sequence_does_not_explode():
    """路径里出现落单的 % 时，解码要**原样保留**，不能抛异常也不能变成乱码。"""
    fetcher = _load_fetcher()

    assert fetcher.normalize_path("/2026/01/01/100%/") == "2026/01/01/100%"


# --- 4. HTTP 契约：URL、请求头、翻页 ----------------------------------------


class _FakeGoatCounter:
    """一个假的 GoatCounter：记下每次请求长什么样，按剧本回数据。

    真接口没有 key 跑不了，但**请求长什么样**是可以钉死的——URL 里有哪些
    参数、认证头是什么、翻页怎么翻。这些东西错了，刷新就是静悄悄地失败。
    """

    def __init__(self, pages):
        # pages: [{"hits": [...], "more": bool}, ...]
        self.pages = pages
        self.requests = []

    def __enter__(self):
        import http.server
        import threading

        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                import urllib.parse

                parsed = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(parsed.query)
                outer.requests.append(
                    {
                        "path": parsed.path,
                        "query": query,
                        "full": self.path,
                        "authorization": self.headers.get("Authorization"),
                    }
                )
                index = min(len(outer.requests) - 1, len(outer.pages) - 1)
                page = outer.pages[index]
                body = json.dumps(page).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        return False

    @property
    def api_base(self):
        return "http://127.0.0.1:{}/api/v0".format(self.port)


def _hit(path, count):
    return {"path": path, "count": count, "event": False, "path_id": 1}


def test_the_fetcher_asks_the_api_the_documented_way():
    """请求的 URL、参数、认证头要跟官方 API 文档对得上。"""
    fetcher = _load_fetcher()
    with _FakeGoatCounter([{"hits": [_hit("/a/", 1)], "more": False}]) as fake:
        fetcher.API_BASE = fake.api_base
        counts = fetcher.fetch_counts("SECRET", "growdu")

    assert counts == {"a": 1}, counts
    request = fake.requests[0]
    assert request["path"] == "/api/v0/stats/hits", request
    assert request["authorization"] == "Bearer SECRET", request
    assert request["query"]["path_by_name"] == ["true"], request
    assert request["query"]["limit"] == ["100"], request
    assert request["query"]["start"] and request["query"]["end"], request


def test_the_fetcher_pages_with_offset_instead_of_a_growing_url():
    """翻页用 ``offset``，**不是** ``exclude_paths``。

    exclude_paths 的办法是把已经拿到的路径全塞回下一次请求：600 条路径
    之后 URL 有 8 万多字符，多数服务器和代理在 8–32KB 就掐了——刷新会
    硬失败，而这件事在真接口上跑一次之前谁也发现不了。
    """
    fetcher = _load_fetcher()
    pages = [
        {"hits": [_hit("/p%d/" % i, i) for i in range(100)], "more": True},
        {"hits": [_hit("/p100/", 100)], "more": False},
    ]
    with _FakeGoatCounter(pages) as fake:
        fetcher.API_BASE = fake.api_base
        counts = fetcher.fetch_counts("SECRET", "growdu")

    assert len(counts) == 101, len(counts)
    assert [r["query"].get("offset", ["0"])[0] for r in fake.requests] == ["0", "100"]
    # URL 长度不随页数增长
    assert len(fake.requests[1]["full"]) < len(fake.requests[0]["full"]) + 50


def test_the_fetcher_refuses_to_count_the_same_path_twice():
    """翻页出错（同一页被返回两次）要**报错**，不能悄悄把阅读量翻倍。

    offset 没被服务端认的时候就会这样：每页都是前 100 条。悄悄翻倍比直接
    失败更糟——数字看着合理，其实全错。
    """
    fetcher = _load_fetcher()
    page = {"hits": [_hit("/a/", 5), _hit("/b/", 6)], "more": True}
    with _FakeGoatCounter([page, page]) as fake:
        fetcher.API_BASE = fake.api_base
        with pytest.raises(RuntimeError):
            fetcher.fetch_counts("SECRET", "growdu")


def test_the_fetcher_stops_after_too_many_pages():
    """服务端一直说 more，也不能无限翻下去。"""
    fetcher = _load_fetcher()
    pages = [{"hits": [_hit("/p%d/" % i, i)], "more": True} for i in range(3)]
    with _FakeGoatCounter(pages) as fake:
        fetcher.API_BASE = fake.api_base
        counts = fetcher.fetch_counts("SECRET", "growdu", max_pages=3)

    assert len(fake.requests) == 3, len(fake.requests)
    assert counts == {"p0": 0, "p1": 1, "p2": 2}, counts


# --- 5. 刷新工作流不能把好数据悄悄抹掉 ---------------------------------------

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "fetch-view-counts.yml"


def test_the_fetcher_refuses_to_wipe_a_good_snapshot(tmp_path, monkeypatch):
    """抓不到东西时**不能**把快照写成空的。

    空快照 = 真实 PV 一个都没有 —— 数据被悄悄清空，而 CI 是绿的。
    API 形状变了、key 过期、站点改名，都会让抓取结果变成空。
    """
    out = tmp_path / "view-counts.json"
    out.write_text(json.dumps({"counts": {"a": 1}}), encoding="utf-8")

    fetcher = _load_fetcher()
    monkeypatch.setenv("GOATCOUNTER_API_KEY", "SECRET")
    monkeypatch.setattr(fetcher, "fetch_counts", lambda *a, **k: {})

    rc = fetcher.main(["--out", str(out)])

    assert rc != 0, "空快照被写进去了"
    assert json.loads(out.read_text(encoding="utf-8"))["counts"] == {"a": 1}, (
        "原来好的数据被覆盖了"
    )


def test_the_fetcher_refuses_a_snapshot_that_lost_most_of_its_paths(tmp_path, monkeypatch):
    """路径数**骤减**也是坏信号：形状变了的话，会安静地少掉一大半。"""
    out = tmp_path / "view-counts.json"
    old = {"p%d" % i: i for i in range(100)}
    out.write_text(json.dumps({"counts": old}), encoding="utf-8")

    fetcher = _load_fetcher()
    monkeypatch.setenv("GOATCOUNTER_API_KEY", "SECRET")
    monkeypatch.setattr(fetcher, "fetch_counts", lambda *a, **k: {"p0": 1})

    rc = fetcher.main(["--out", str(out)])

    assert rc != 0, "只剩 1 条的快照被写进去了"
    assert json.loads(out.read_text(encoding="utf-8"))["counts"] == old


def test_the_refresh_workflow_is_pinned_to_master_and_runs_the_tests():
    """工作流直接推 master，所以要钉死在 master 上，推之前先跑测试。

    不钉的话，从别的分支手动触发这个工作流，那个分支上的提交会被
    rebase 到 master 再推上去。
    """
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "ref: master" in text, "checkout 没有钉在 master 上"
    assert "pytest" in text, "推 master 之前没有跑测试"
    assert "workflow_dispatch" in text, "只剩自动触发就不是「手动刷新」了"

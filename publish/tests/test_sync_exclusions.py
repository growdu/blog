"""内部工程目录不再被发布为文章（规格 §4.3 的路径排除规则）。

这条规则是**防回归守卫**，不是修复手段：真正的解法是「想清楚哪些内容该发布，
然后让发布路径与工程路径物理分离」（AIV 把工程目录迁出 ``docs/`` 就是那么
做的）。它防的是「将来有人在 ``docs/`` 下建了 ``tests/``、``pipeline/`` 这类
工程目录，构建期把它们当成文章发布」。

守卫有两条，都在这儿：

1. **集成**：真的跑一遍 ``tools/sync-hexo.py``——``docs/`` 下工程目录里的文件
   **不**进产物，而同名文件（``README.md``）照旧进；
2. **防回归**：仓库里今天 ``docs/`` 下命中排除名单的**必须是空集**——空集才
   说明这条规则没有改变任何现有产物的去留（§4.3「当前状态：规则命中 0 个
   文件」）。

断言的写法刻意**不**硬编码内容单元数（规格 §12 第 0 行写的「当前 564」
早就过期了——树在长，硬编码每加一篇新文章就红一次）：改成「命中集为空集」+
「内容单元数 ≥ 下界」，这才是 §13 风险表里「规则命中集必须为空」的本意。
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "tools" / "sync-hexo.py"
DOCS = REPO_ROOT / "docs"

#: §4.3 的排除名单（原文）：路径中任意一级目录名命中即排除，大小写不敏感。
SPEC_EXCLUDED_DIR_NAMES = {
    "tests",
    "test",
    "fixtures",
    "plans",
    "pipeline",
    "build",
    "out",
    "_staging",
    "frames",
}

#: 内容单元数的下界。规格 §12 第 0 行记的是「当前 564」，那个数字已经过期
#: （今天是 619 个 md + 3 个 html），硬编码每加一篇新文章就红一次——所以只
#: 断言下界：低于 500 说明有人误删了一大片文章，那是要立刻知道的事。
CONTENT_UNIT_FLOOR = 500


def load_sync_module():
    """Load ``tools/sync-hexo.py`` as a module (it is a script, not a package).

    只读常量与纯函数，不跑 ``main()``——脚本的入口有 ``__main__`` 守卫。
    """
    spec = importlib.util.spec_from_file_location("sync_hexo_exclusions", SYNC_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: 会被发布成内容单元的扩展名。排除规则只对它们有意义——``.c`` / ``Makefile``
#: 这类文件本来就不会进产物，落在排除目录里也不改变任何事。
PUBLISHABLE_SUFFIXES = (".md", ".html", ".htm")


def excluded_hits(docs_dir, module):
    """Every **publishable** file that sits in an excluded directory.

    按**目录名**匹配，不按文件名——所以 ``aiv/voice/README.md`` 不会被算进来。

    只算会被发布的文件（md / html）：``docs/src/test/`` 底下确实有几个
    ``.c`` 与 ``Makefile``，但它们从来不会变成文章，落在排除目录里也不改变
    任何产物。规格 §4.3 记的「规则命中 0 个文件」说的就是这个意思。
    """
    hits = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in PUBLISHABLE_SUFFIXES:
            continue
        parts = path.relative_to(docs_dir).parts
        if any(module.is_excluded_dir(part) for part in parts[:-1]):
            hits.append(str(path.relative_to(docs_dir)))
    return hits


def content_units(docs_dir, module):
    """The md / html files that count as published content units."""
    units = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in PUBLISHABLE_SUFFIXES:
            continue
        parts = path.relative_to(docs_dir).parts
        if any(module.is_excluded_dir(part) for part in parts[:-1]):
            continue
        units.append(path)
    return units


# --- 规则本身 -------------------------------------------------------------


def test_the_exclusion_list_is_exactly_the_one_in_the_spec():
    """§4.3 的排除名单一个字都不能差，也不能多也不能少。"""
    module = load_sync_module()

    assert set(module.EXCLUDED_DIR_NAMES) == SPEC_EXCLUDED_DIR_NAMES


def test_the_exclusion_matching_is_case_insensitive_and_exact():
    """大小写不敏感；但不是前缀匹配——``testing`` 不等于 ``test``。"""
    module = load_sync_module()

    assert module.is_excluded_dir("TESTS")
    assert module.is_excluded_dir("Tests")
    assert module.is_excluded_dir("Pipeline")
    assert module.is_excluded_dir("_STAGING")

    assert not module.is_excluded_dir("testing")
    assert not module.is_excluded_dir("my_test_dir")
    assert not module.is_excluded_dir("blog")
    assert not module.is_excluded_dir("README.md")


# --- 防回归守卫 -----------------------------------------------------------


def test_the_exclusion_rule_matches_nothing_in_the_real_docs_tree():
    """仓库里 ``docs/`` 下命中排除名单的**可发布文件**必须是空集。

    §4.3 记的是「当前状态：规则命中 0 个文件」。命中集非空就意味着这条规则
    正在悄悄改变某些现有产物的去留——那是要有人拍板的事，不该默默发生。

    注意 ``docs/src/test/`` 目录**已经存在**（底下是几个 ``.c`` 与
    ``Makefile``，没有可发布文件）：守卫要防的位置已经选好了，只是今天还没
    往里放文章。
    """
    module = load_sync_module()

    hits = excluded_hits(DOCS, module)

    assert hits == [], "docs/ 下命中排除名单的可发布文件：{}".format(hits)


def test_the_content_unit_count_stays_above_the_floor():
    """内容单元数不得低于下界。

    不写死具体数字（§12 第 0 行的「当前 564」早就过期）：只断言下界——正常
    加文章不会红，误删一大片会红。
    """
    module = load_sync_module()

    units = content_units(DOCS, module)

    assert len(units) >= CONTENT_UNIT_FLOOR, "内容单元数掉到了 {}（下界 {}）".format(
        len(units), CONTENT_UNIT_FLOOR
    )


# --- 集成：真的跑一遍 sync-hexo.py ---------------------------------------


def build_corpus(root: Path, drafts) -> None:
    for rel, text in drafts.items():
        path = root / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    shutil.copy(REPO_ROOT / "_config.matery.yml", root / "_config.matery.yml")


def run_sync(root: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "sync-hexo.py 失败：\n{}\n{}".format(
        result.stdout, result.stderr
    )


DRAFT = "---\ntitle: {title}\n---\n\n{body}\n"

CORPUS = {
    "blog/ok.md": DRAFT.format(title="该发布的一篇", body="正文。"),
    # 命中排除名单：tests / test / pipeline（大小写不敏感）
    "src/test/test_module/notes.md": DRAFT.format(title="工程笔记", body="不该发布。"),
    "blog/tests/plan.md": DRAFT.format(title="测试计划", body="不该发布。"),
    "blog/PIPELINE/draft.md": DRAFT.format(title="流水线草稿", body="不该发布。"),
    # 隐藏目录：现有的守卫，与新规则并列
    ".hidden/secret.md": DRAFT.format(title="隐藏目录", body="不该发布。"),
    # **文件名**叫 README.md 但所在目录不命中——按目录名排除，不按文件名
    "blog/aiv/voice/README.md": DRAFT.format(title="音色规范", body="该发布。"),
}


def test_engineering_directories_are_not_published(tmp_path):
    build_corpus(tmp_path, CORPUS)
    run_sync(tmp_path)

    posts = tmp_path / "source" / "_posts"

    # 该发的照发
    assert (posts / "blog" / "ok.md").is_file()
    # 同名文件按目录名判定——README.md 不因为名字被排除
    assert (posts / "blog" / "aiv" / "voice" / "README.md").is_file()

    # 工程目录里的文件不进产物
    assert not (posts / "src" / "test" / "test_module" / "notes.md").exists()
    assert not (posts / "blog" / "tests" / "plan.md").exists()
    assert not (posts / "blog" / "PIPELINE" / "draft.md").exists()

    # 隐藏目录守卫还在（与新规则并列，不是被替换）
    assert not (posts / ".hidden" / "secret.md").exists()


def test_the_excluded_directories_leave_no_trace_in_the_product(tmp_path):
    """被排除的目录整棵不进产物——文章、图都不进。"""
    build_corpus(
        tmp_path,
        dict(
            CORPUS,
            **{"blog/pipeline/logo.png": "not really a png"},
        ),
    )
    run_sync(tmp_path)

    source = tmp_path / "source"

    assert not (source / "_posts" / "blog" / "pipeline").exists()
    assert not (source / "images" / "blog" / "pipeline").exists()

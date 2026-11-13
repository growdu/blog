"""编辑器里那些「怎么用代码碰到平台」的口径，必须留在试点记录里。

§R2 记的是**平台规则**（上限多少、封面什么比例）。这一节记的是另一件事：
**选择器**——标题框在哪、正文区是什么类、图片按钮怎么认、勾选项的标记在哪儿。

为什么值得单独立一条守卫：

* 工具脚本**不入库**（放仓库外的临时目录），所以定位口径只有文档这一份副本；
* 这些口径是**摸出来**的，不是文档里抄的——重新摸一遍要花掉一整轮观测的时间；
* 摸错了**不会立刻出事**。比如把勾选标记当成在 wrapper 的子孙里，
  读出来全是「未勾选」，而页面其实勾着——读数骗人，内容却是对的。

所以这里钉的不是「某个类名」，而是**那些必须留着的关键定位与两条反直觉的坑**
（遮罩淡出期间会拦截点击、勾选标记在 label 自己身上）。
"""

from pathlib import Path

PILOT_RELATIVE_PATH = ("toutiao", "docs", "02-试点记录.md")

R3_HEADING = "### R3 · 2026-11-13"

#: 必须留在文档里的定位口径。每一条都是「重填一遍要重新摸」的东西。
REQUIRED_LOCATORS = (
    "textarea[placeholder=",
    "div.ProseMirror",
    "12.5l7.921",
    ".footer-back-content",
    ".article-cover-radio-group",
    ".article-cover-img-wrap",
    ".article-cover-img-replace",
    ".byte-drawer-wrapper",
    ".byte-drawer-mask",
    "byte-checkbox-checked",
    "/mp/agw/article/publish",
)

#: 两条反直觉的坑：不知道就会踩，踩了还会读出错的结论。
REQUIRED_WARNINGS = (
    "淡出期间仍会拦截点击",
    "的子孙里",
)


def _text(repo_root: Path) -> str:
    return repo_root.joinpath(*PILOT_RELATIVE_PATH).read_text(encoding="utf-8")


def test_the_locator_section_is_recorded(repo_root):
    """§R3 必须在。

    没有它，下一次要重填就得从头摸一遍选择器——那是一整轮观测的时间。
    """
    text = _text(repo_root)

    assert R3_HEADING in text, "试点记录里没有 {} 这一节".format(R3_HEADING)


def test_every_required_locator_is_documented(repo_root):
    """每一个「重新摸要花时间」的选择器都得在。

    少一个，下次重填就有一处会踩空——而踩空的症状往往是「看起来成功了」。
    """
    text = _text(repo_root)

    missing = [locator for locator in REQUIRED_LOCATORS if locator not in text]
    assert not missing, "试点记录里没有这些定位口径：{}".format("、".join(missing))


def test_the_two_counter_intuitive_traps_are_written_down(repo_root):
    """两条坑必须在，而且要写清楚**坑在哪**，不是只写「注意」。

    * 遮罩淡出期间仍会拦截点击 → 表现是「点了没反应」，容易被当成页面卡了；
    * 勾选标记在 label 自己身上 → 表现是「读出来全是未勾选」，
      页面其实勾着——**读数骗人，内容是对的**，不去对照 class 就会误判。
    """
    text = _text(repo_root)

    for warning in REQUIRED_WARNINGS:
        assert warning in text, "试点记录里没有这条坑：{}".format(warning)


def test_the_refill_procedure_is_ordered(repo_root):
    """重填的顺序必须在，而且得是「标题 → 正文 → 图 → 封面 → 勾选项」。

    顺序错一步就会白跑：比如封面要等正文里的首图存在（首图会自动成为封面），
    图片插入要等正文粘好（要在 `【图N】` 占位符上定位光标）。
    """
    text = _text(repo_root)

    start = text.find("**重填一篇的顺序**")
    assert start != -1, "试点记录里没有「重填一篇的顺序」"

    order = ["标题框填标题", "真剪贴板", "正文图", "封面", "勾选项回到默认"]
    positions = []
    for step in order:
        index = text.find(step, start)
        assert index != -1, "重填顺序里没有「{}」这一步".format(step)
        positions.append(index)

    assert positions == sorted(positions), "重填的步骤顺序变了：{}".format(order)


def test_no_local_paths_leaked_into_the_repository(repo_root):
    """跟踪文件里不该出现本机路径。

    定位口径进文档，**脚本不进仓库**——脚本里有本机临时目录、浏览器 profile 路径、
    调试产物。哪天顺手把脚本或它的输出塞进仓库，这些路径就会跟着进来，
    而且没人会去清理它们。

    这里只扫**被 git 跟踪**的文件：``toutiao/out/`` 里的产物不入库，
    扫它们只会制造假警报。
    """
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "--", "toutiao", "publish"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return  # git 问不到，不当成「泄漏」

    forbidden = ("/tmp/tt-browser", "toutiao-publisher", "Library/Application Support")
    this_file = Path(__file__).resolve()
    for relative in result.stdout.split():
        if not relative.endswith((".py", ".md", ".toml", ".json", ".txt")):
            continue
        path = repo_root / relative
        if not path.is_file():
            continue
        # 这个文件自己就写着这些标记——扫自己等于自己绊自己。
        if path.resolve() == this_file:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in forbidden:
            assert marker not in text, (
                "{} 里出现了本机路径「{}」——工具脚本与产物不入库，"
                "定位口径留在试点记录里就够了".format(relative, marker)
            )


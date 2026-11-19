"""左右两块侧栏（分类导航 / 最多阅读）已经整个删掉了。

**背景**：这两块侧栏在 2026-11-18 之前一直挂在 ``layout.ejs`` 里——
左边一个分类导航，右边一个「最多阅读」排行榜。窄屏下它们被 CSS 藏起来，
宽屏下占掉左右各 270px，把正文挤成中间一条窄带；首页首屏因此还多出一堆
读者不点的东西。

现在它们不在了：页面按整幅宽度排版，分类从顶部导航的「分类」进，
文章从「归档」页看。

这里守的是**「别又长回来」**：

1. ``layout.ejs`` 里不许再有 ``cat-sidebar`` / ``hot-sidebar``；
2. 不许再有 ``toggleSidebar``（折叠开关连着这两块侧栏，一起没）；
3. ``patch-theme.py`` 里不许再注入侧栏的 CSS —— 模板没了、样式还在，
   那一堆选择器就是纯死代码，下次有人读到会以为侧栏还在；
4. 跑一遍 patcher 之后，侧栏**不会**被塞回来。

第 4 条是关键：``patch-theme.py`` 里曾经存过一份侧栏模板的**抄本**，
跟主题里真正生效的那份早就对不上了（抄本少了折叠开关
``onclick="toggleSidebar('cat')"``）。哪天它真的注入进去，侧栏就再也
折叠不了，而构建不会报错、测试也不会红。一份抄本 = 两处真相 = 迟早漂。
"""

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
THEME = REPO_ROOT / "themes" / "matery"
PATCH_THEME = REPO_ROOT / "tools" / "patch-theme.py"
LAYOUT_EJS = THEME / "layout" / "layout.ejs"


def test_the_layout_has_no_sidebar_markup():
    """主题里不许再有侧栏的 DOM。"""
    layout = LAYOUT_EJS.read_text(encoding="utf-8")

    assert "cat-sidebar" not in layout, "左侧「分类导航」侧栏又回来了"
    assert "hot-sidebar" not in layout, "右侧「最多阅读」侧栏又回来了"
    assert "toggleSidebar" not in layout, "侧栏的折叠开关（toggleSidebar）还留着"


def test_the_patcher_injects_no_sidebar_css():
    """patcher 里不许再注入侧栏的样式。

    侧栏没了还留着那几百行 CSS，是纯粹的噪声：下次有人读到
    ``.cat-sidebar`` 会以为侧栏还在。
    """
    text = PATCH_THEME.read_text(encoding="utf-8")

    assert "cat-sidebar" not in text, "patch-theme.py 里还有侧栏的 CSS"
    assert "hot-sidebar" not in text, "patch-theme.py 里还有侧栏的 CSS"
    assert "sidebar_ejs" not in text, "patch-theme.py 里还存着侧栏模板的抄本"


def test_running_the_patcher_does_not_bring_the_sidebar_back(tmp_path):
    """跑一遍 patcher，主题里仍然没有侧栏。

    patcher 是在主题目录上跑的（``themes/matery``），所以在临时目录里放一份
    主题的拷贝再跑它——跑完侧栏不该出现，折叠开关也不该出现。
    """
    theme_copy = tmp_path / "themes" / "matery"
    theme_copy.parent.mkdir(parents=True)
    shutil.copytree(str(THEME), str(theme_copy))

    result = subprocess.run(
        [sys.executable, str(PATCH_THEME)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, "patch-theme.py 跑挂了：\n{}\n{}".format(
        result.stdout, result.stderr
    )

    layout = (theme_copy / "layout" / "layout.ejs").read_text(encoding="utf-8")
    assert "cat-sidebar" not in layout, "跑完 patcher，分类导航侧栏被塞回来了"
    assert "hot-sidebar" not in layout, "跑完 patcher，最多阅读侧栏被塞回来了"
    assert "toggleSidebar" not in layout, "跑完 patcher，折叠开关被塞回来了"


def test_the_theme_css_has_no_sidebar_rules():
    """``my.css`` 里也不许再有侧栏的规则。

    这里必须查**文件本身**，而不是查 patcher：patcher 是幂等的，marker 还在
    就整段跳过——只改 patcher 而不动 my.css，仓库里的样式会一直留着。
    """
    css = (THEME / "source" / "css" / "my.css").read_text(encoding="utf-8")

    assert "cat-sidebar" not in css, "my.css 里还有分类导航侧栏的样式"
    assert "hot-sidebar" not in css, "my.css 里还有最多阅读侧栏的样式"
    assert "cat-collapsed" not in css, "my.css 里还有侧栏折叠态的样式"

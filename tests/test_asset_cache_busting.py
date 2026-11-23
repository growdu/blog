"""静态资源的 URL 必须带内容哈希 —— 否则改了样式，老访客根本看不到。

**背景（2026-11-23）**：nginx 对 .css/.js 一律

    expires 30d;
    add_header Cache-Control "public, immutable";

而这些资源的 URL 是稳的（``/css/my.css``）。CSS 一改，**同一个 URL 的
新内容浏览器不会去取** —— ``immutable`` 明确告诉浏览器「30 天内别来问」。

2026-11-20 首页统计条从「五张白卡片」重做成「一整条五格」之后，服务器上
明明已经是新样式，老访客看到的却还是旧版：≤992px 时旧 CSS 是
``repeat(3, 1fr)``，五张卡排成「3 + 2」**两行**，数字还是 30px 的黑体。
新样式一次都没送到他们眼前。

这里守三件事：

1. 主题的 CSS/JS 链接带上了内容哈希（``?v=``）—— 内容变 → URL 变 →
   浏览器必须重新取；
2. service worker 的缓存名**每次构建都不一样**（``__SW_CACHE_NAME__``
   占位符由 CI 换成 SHA + 时间戳）—— 否则旧缓存永远不清；
3. ``/sw.js`` 在 nginx 里**不缓存** —— service worker 必须在稳定的 URL
   上被重新取到，新缓存名才轮换得起来。

放在根级 ``tests/``，随 ``site-guard.yml`` 进 CI。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
THEME = REPO / "themes" / "matery"
ASSET_VERSION_JS = THEME / "scripts" / "asset-version.js"
SYNC_HEXO = REPO / "tools" / "sync-hexo.py"
SOURCE_SW = REPO / "source" / "sw.js"
NGINX_SCRIPT = REPO / "tools" / "update-nginx-cache.sh"
HEXO_WORKFLOW = REPO / ".github" / "workflows" / "hexo.yml"

NODE = shutil.which("node")


def _read(path: Path) -> str:
    assert path.is_file(), "找不到 {}".format(path)
    return path.read_text(encoding="utf-8")


# --- 1. 主题脚本存在，且真的给 URL 加版本号 --------------------------------


def test_asset_version_script_exists():
    """主题里得有这个脚本，否则 URL 上的 ``?v=`` 根本没人加。"""
    assert ASSET_VERSION_JS.is_file(), "缺少 {}".format(ASSET_VERSION_JS)


def test_asset_version_script_registers_html_filter():
    """它挂在 ``after_render:html`` 上 —— 渲染完的 HTML 才改。"""
    text = _read(ASSET_VERSION_JS)
    assert "after_render:html" in text
    assert "hexo.extend.filter.register" in text


@pytest.mark.skipif(NODE is None, reason="没装 node，跑不了过滤器")
def test_asset_version_filter_adds_hash(tmp_path):
    """真跑一遍过滤器：本地 CSS 加上 ``?v=``，别的 URL 一律不动。"""
    script = tmp_path / "run.js"
    script.write_text(
        """
const path = require('path');
const REPO = {repo};
let filterFn = null;
global.hexo = {{
  config: {{ root: '/' }},
  theme_dir: path.join(REPO, 'themes', 'matery'),
  extend: {{ filter: {{ register: (type, fn) => {{ filterFn = fn; }} }} }}
}};
require(path.join(REPO, 'themes', 'matery', 'scripts', 'asset-version.js'));

const html = [
  '<link rel="stylesheet" href="/css/my.css">',
  '<link rel="stylesheet" href="/css/tech.css">',
  '<script src="/js/matery.js"></script>',
  '<script src="/sw.js"></script>',
  '<script src="https://cdn.example.com/x.js"></script>',
  '<a href="/archives/">归档</a>'
].join('\\n');

const out = filterFn(html);
console.log(JSON.stringify(out));
""".format(repo=json.dumps(str(REPO))),
        encoding="utf-8",
    )

    result = subprocess.run(
        [NODE, str(script)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)

    # 本地 CSS/JS：带上了版本号
    assert re.search(r'href="/css/my\.css\?v=[0-9a-f]+"', out), out
    assert re.search(r'href="/css/tech\.css\?v=[0-9a-f]+"', out), out
    assert re.search(r'src="/js/matery\.js\?v=[0-9a-f]+"', out), out

    # service worker 必须留在稳定 URL 上 —— 否则它自己更新不了
    assert 'src="/sw.js"' in out, out
    assert not re.search(r'src="/sw\.js\?v=', out), out

    # 外链与站内链接不动
    assert 'src="https://cdn.example.com/x.js"' in out, out
    assert 'href="/archives/"' in out, out


# --- 2. service worker 的缓存名每次构建都不一样 -----------------------------


def test_generated_sw_uses_build_placeholder():
    """``sync-hexo.py`` 生成的 sw.js 得留占位符给 CI 换。"""
    text = _read(SYNC_HEXO)
    assert "__SW_CACHE_NAME__" in text, "sw.js 的缓存名还是写死的"


def test_committed_sw_matches_generator():
    """仓库里那份 sw.js 得跟生成器产出的一致（生成器会覆盖它）。"""
    text = _read(SYNC_HEXO)
    i = text.index('"""const CACHE=')
    j = text.index('"""', i + 3)
    generated = text[i + 3 : j]
    assert _read(SOURCE_SW) == generated, "source/sw.js 与 sync-hexo.py 生成的不一致"


def test_ci_stamps_the_cache_name():
    """CI 得真的把占位符换成带 SHA 的名字。"""
    text = _read(HEXO_WORKFLOW)
    assert "__SW_CACHE_NAME__" in text
    assert re.search(r"sed -i .*__SW_CACHE_NAME__", text)


def test_sw_cache_name_is_not_hardcoded():
    """别再写死 'blog-v3' —— 那等于缓存名永远不变。"""
    text = _read(SOURCE_SW)
    assert "blog-v3" not in text


# --- 3. nginx：/sw.js 不缓存，浏览器才拿得到新的 service worker -------------


def test_nginx_script_keeps_sw_uncached():
    """``/sw.js`` 必须 no-cache。

    nginx 对 .js 一律 ``expires 30d; immutable`` —— 浏览器连新的
    service worker 都拿不到，缓存名就永远轮换不起来。
    """
    text = _read(NGINX_SCRIPT)
    assert re.search(r"location = /sw\.js\s*\{\s*add_header Cache-Control \"no-cache\"", text)

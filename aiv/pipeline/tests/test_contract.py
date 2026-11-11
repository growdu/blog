"""视觉分镜契约的守卫。

**分工原则**：本期内容进契约，版式常量留代码。

这一期（以及以后每一期）的文案、数字、标签都写在 `aiv/contracts/*.json` 里，
场景渲染器不许再写死它们。这组测试盯着三件事：

1. 契约本身是完整的——句子恰好被覆盖一次，每段参数齐全，渲染器都存在；
2. 文案没有回流到代码——场景源码里不再出现契约中的文案；
3. 契约化之后画面没变——逐像素指纹与改造前一致。

第 3 条是关键：把文案搬进契约最容易出的事故是「顺手把画面也改了」，
而画面变了不会有任何报错，只有逐像素比对能发现。
"""
import ast
import hashlib
import importlib
import json
from pathlib import Path

import cairo
import pytest

from pyv import contract as contract_mod
from pyv.params import MissingParam, Params

FIXTURES = Path(__file__).parent / "fixtures"
BASELINE = FIXTURES / "scene_baseline.json"

# 短于 3 个字符的文案不判：两个汉字的词（"输出"、"并行"）到处都是，
# 拿它当判据只会天天误报。3 个字起才算「一句具体的文案」。
MIN_COPY_LENGTH = 3


@pytest.fixture(scope="module")
def contract():
    return contract_mod.load_contract()


# ---------------------------------------------------------------- 契约完整性


def test_contract_loads_and_has_segments(contract):
    assert contract.version == 1
    assert contract.episode
    assert contract.title
    assert len(contract.segments) == 6


def test_contract_covers_every_sentence_exactly_once(contract):
    seen: list[int] = []
    for segment in contract.segments:
        seen.extend(segment.sentences)
    assert sorted(seen) == list(range(contract.sentence_count))
    assert contract.sentence_count == 10


def test_every_segment_renderer_exists(contract):
    for segment in contract.segments:
        module = importlib.import_module(segment.renderer)
        assert callable(module.render), segment.renderer


def test_every_segment_has_all_required_params(contract):
    """场景声明了必填参数，契约必须一个不缺地给出来。"""
    for segment in contract.segments:
        module = importlib.import_module(segment.renderer)
        required = getattr(module, "REQUIRED", ())
        assert required, f"{segment.renderer} 没有声明 REQUIRED"
        missing = [k for k in required if k not in segment.params]
        assert not missing, f"{segment.id} 缺参数：{missing}"


def test_contract_params_are_not_empty_strings(contract):
    """画面上不能出现空文案——那通常是漏填。"""
    for segment in contract.segments:
        for key, value in segment.params.items():
            if isinstance(value, str):
                assert value.strip(), f"{segment.id} 的 {key} 是空串"


# ------------------------------------------------------- 文案不许回流到代码


def _scene_literals(module_name: str) -> list[str]:
    """场景源码里的字符串字面量。

    只取字面量，是因为**字面量才是真正会画到画面上的文本**。
    标识符（`worker_h`）和注释是代码，不是内容——按整份源码做子串匹配，
    值 `worker` 会被 `worker_h` 这种版式变量名误伤。
    """
    module = importlib.import_module(module_name)
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _param_keys(contract) -> set[str]:
    """所有场景声明的参数键。

    参数键是代码里的标识（`decoder_label`），不是文案，判定时要排除掉——
    否则值 `decoder` 会被参数名误伤。
    """
    keys: set[str] = set()
    for segment in contract.segments:
        module = importlib.import_module(segment.renderer)
        keys.update(getattr(module, "REQUIRED", ()))
    return keys


def _copy_leaks(literals: list[str], params: dict, keys: set[str]) -> list[tuple]:
    """找出字面量里藏着契约文案的地方，返回 (key, value, literal)。"""
    leaks: list[tuple] = []
    values = {v for v in params.values() if isinstance(v, str)}
    for key, value in params.items():
        if not isinstance(value, str) or len(value) < MIN_COPY_LENGTH:
            continue
        for literal in literals:
            # 参数键本身跳过；但万一某个参数值就长成参数键的样子，仍然要查。
            if literal in keys and literal not in values:
                continue
            if value in literal:
                leaks.append((key, value, literal))
    return leaks


def test_scene_source_contains_no_episode_copy(contract):
    """契约里的文案不得出现在场景源码里。

    文案写在代码里，就等于又回到了「改一句话要改代码」的老路。

    判定规则：把场景源码解析成 AST，取出所有字符串字面量，
    凡是**包含**契约里那句文案的字面量都算回流——除了参数键本身。
    """
    keys = _param_keys(contract)
    for segment in contract.segments:
        literals = _scene_literals(segment.renderer)
        leaks = _copy_leaks(literals, segment.params, keys)
        assert not leaks, (
            f"{segment.renderer} 里写死了契约文案："
            + "；".join(f"{k}={v!r}（命中 {lit!r}）" for k, v, lit in leaks)
            + "，它们应该只存在于契约里"
        )


def test_copy_guard_actually_catches_a_leak(contract):
    """守卫自己也要验：塞一句硬编码文案进去，必须被抓出来。

    没有这条，守卫一旦写坏（比如规则太松到什么都不匹配）就会一直绿着，
    而它恰恰是最该被信任的那条测试。
    """
    segment = contract.segments[0]
    keys = _param_keys(contract)
    value = segment.params["title"]
    leaks = _copy_leaks([f"text(ctx, {value!r})"], segment.params, keys)
    assert leaks, "守卫没抓到硬编码文案，它已经失效了"


# ------------------------------------------------------------ 缺参数要报错


def test_missing_param_raises_with_scene_name(contract):
    segment = contract.segments[0]
    broken = dict(segment.params)
    broken.pop(next(iter(broken)))
    with pytest.raises(MissingParam) as exc:
        Params(broken, segment.id)["__missing__"]
    assert "__missing__" in str(exc.value)


def test_scene_render_rejects_incomplete_params(contract):
    """参数不全时必须当场报错，不能悄悄退回硬编码的旧文案。"""
    segment = contract.segments[0]
    module = importlib.import_module(segment.renderer)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    with pytest.raises(MissingParam):
        module.render(ctx, 0.5, 320, 180, {})


def test_render_scene_validates_params_before_rendering(tmp_path, contract):
    """渲染入口也要查参数——不能等渲染到一半才炸。"""
    from pyv import render
    from pyv.timeline import Scene

    scene = Scene(id="s01", start=0.0, end=1.0, type="code", subtitle="测试",
                  renderer="pyv.scenes.s01_intro", params={})
    with pytest.raises(MissingParam):
        render.render_scene(scene, tmp_path / "x.mp4", width=320, height=180)


# ------------------------------------------------------------ 逐像素回归


def _without_mascot(monkeypatch) -> None:
    """让形象一律不画。

    3D 形象是**媒体产物，不入库**（见 `character/README.md`）。基准指纹若带着
    素材抓，换台机器、换个干净检出就必然对不上——测试会退化成「看本机有没有图」，
    而不是「看这次改造有没有改到画面」。强制不画，基准才在任何检出里都成立。

    落版头像 `avatar.jpg` 是入库的，两边都会画，不受这个开关影响。
    """
    from pyv import character

    def _no_mascot(self) -> None:
        self._mode = "none"

    monkeypatch.setattr(character.Mascot, "_load", _no_mascot)


def _scene_frame_hash(module_name: str, params: dict, t: float) -> str:
    from pyv.palette import COLORS, hex_to_rgb

    module = importlib.import_module(module_name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(*hex_to_rgb(COLORS["bg"]))
    ctx.paint()
    module.render(ctx, t, 1920, 1080, params)
    return hashlib.sha256(bytes(surface.get_data())).hexdigest()


def test_contract_driven_rendering_is_pixel_identical(contract, monkeypatch):
    """契约化之后，画面必须与改造前一模一样。

    基准指纹是「文案还写死在场景代码里」时抓的。把文案搬进契约最容易出的
    事故就是顺手把画面也改了——而画面变了不会有任何报错，只有逐像素比对能发现。
    """
    _without_mascot(monkeypatch)
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["frames"]
    for segment in contract.segments:
        for t in (0.0, 0.45, 0.9):
            key = f"{segment.renderer}@{t}"
            assert key in baseline, f"基准里没有 {key}"
            actual = _scene_frame_hash(segment.renderer, segment.params, t)
            assert actual == baseline[key], (
                f"{key} 的画面变了：文案搬进契约不该动到画面"
            )


def test_pixel_baseline_excludes_local_mascot_asset(contract, monkeypatch):
    """基准指纹里不含本机的形象素材。

    形象 PNG 不入库，干净检出里根本没有它。基准若是带着素材抓的，
    就会在主工作区绿、在干净检出里必然红——那等于把测试绑死在一台机器的状态上，
    而它本该盯的是「代码有没有改画面」。这条测试盯住「基准与素材无关」这个前提本身。
    """
    from pyv import character

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["capture"]["mascot"] == "none", "基准必须是在不画形象时抓的"
    assert baseline["capture"]["times"] == [0.0, 0.45, 0.9]
    assert len(baseline["frames"]) == 18, "6 个场景 × 3 个时间点"

    # 主工作区里形象素材是在的：有它也必须对得上「不画形象」的基准，
    # 说明素材确实没进比较。
    if not character.STATIC_IMAGE.is_file():
        pytest.skip("本机没有形象素材，这条前提无从验证")
    _without_mascot(monkeypatch)
    params = next(s.params for s in contract.segments
                  if s.renderer == "pyv.scenes.s01_intro")
    key = "pyv.scenes.s01_intro@0.45"
    assert _scene_frame_hash("pyv.scenes.s01_intro", params, 0.45) \
        == baseline["frames"][key]

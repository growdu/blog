import importlib

import cairo
import pytest

SCENE_MODULES = [
    "pyv.scenes.s01_intro",
    "pyv.scenes.s02_serial",
    "pyv.scenes.s03_cores",
    "pyv.scenes.s04_parallel",
    "pyv.scenes.s05_bench",
    "pyv.scenes.s06_outro",
    # EP02（CSN 全序）新增的四个场景
    "pyv.scenes.s02_mixed",
    "pyv.scenes.s03_counter",
    "pyv.scenes.s04_propagate",
    "pyv.scenes.s05_layers",
]


def _all_contracts():
    """仓库里每一期的契约，默认那一期排在最前面。"""
    from pyv import contract as contract_mod

    paths = [contract_mod.DEFAULT_CONTRACT]
    paths.extend(
        p for p in sorted(contract_mod.CONTRACTS_DIR.glob("*.json"))
        if p != contract_mod.DEFAULT_CONTRACT
    )
    return [contract_mod.load_contract(p) for p in paths]


def _params_for(module_name: str) -> dict:
    """这一期的画面内容来自视觉分镜契约，不是场景代码。

    一个场景可能被多期复用（片头片尾就是），取第一个用到它的契约即可。
    """
    for contract in _all_contracts():
        for segment in contract.segments:
            if segment.renderer == module_name:
                return segment.params
    raise AssertionError(f"契约里没有 {module_name}")


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_module_exposes_render(name):
    module = importlib.import_module(name)
    assert callable(module.render)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_draws_something(name):
    module = importlib.import_module(name)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    module.render(ctx, 0.5, 320, 180, _params_for(name))
    data = surface.get_data()
    assert any(byte != 0 for byte in data)


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_render_handles_endpoints(name):
    module = importlib.import_module(name)
    for t in (0.0, 1.0):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
        ctx = cairo.Context(surface)
        module.render(ctx, t, 320, 180, _params_for(name))


def test_s03_highlights_exactly_one_core():
    import pyv.scenes.s03_cores as s03
    highlighted = s03.highlighted_cores(_params_for("pyv.scenes.s03_cores"))
    assert len(highlighted) == 1
    assert 0 <= highlighted[0] < 32


def test_s04_exposes_four_workers():
    import pyv.scenes.s04_parallel as s04
    assert s04.worker_count(_params_for("pyv.scenes.s04_parallel")) == 4


def test_s05_bench_draws_a_range_not_a_single_precise_value():
    """压测那组数字是区间（2 到 5 倍），画面不能画成一个精确的单值。

    串行条占 1 倍，实测区间从 2 倍起到 5 倍止——条的长度必须与
    画面上写的那个倍数对得上，否则图和字各说各的。
    """
    import pyv.scenes.s05_bench as s05

    params = _params_for("pyv.scenes.s05_bench")
    marks = s05.scale(1000.0)
    unit = marks["unit"]
    assert marks["serial_end"] - marks["x0"] == pytest.approx(unit)
    assert marks["range_x"] - marks["x0"] == pytest.approx(unit * 2)
    assert marks["range_end"] - marks["x0"] == pytest.approx(unit * 5)
    assert marks["range_x"] > marks["serial_end"], "区间必须整体落在串行基线之外"
    assert params["callout"] == "2–5 倍", "画面上的倍数必须与口播一致"


def test_s04_separates_reader_from_walsender():
    """openGauss 的 reader 是独立线程，walsender 单独收口，不能画成一个。

    上一版把来源方标成 `Reader (WALSender)`，与源码拓扑不符。
    """
    params = _params_for("pyv.scenes.s04_parallel")
    assert params["source_label"] == "reader"
    assert params["target_label"] == "walsender"
    assert "WALSender" not in params["source_sub"], \
        "来源方不是 WALSender——reader 与 walsender 是两个线程"


def test_s06_uses_personal_avatar_and_no_banned_words():
    import pyv.scenes.s06_outro as s06
    from pyv import character
    from pyv.timeline import BANNED_SUBSTRINGS
    source = open(s06.__file__, encoding="utf-8").read()
    assert "avatar_path" in source, "落版头像必须走统一入口"
    assert character.avatar_path() is not None, "个人头像素材缺失"
    for word in BANNED_SUBSTRINGS:
        assert word.lower() not in source.lower(), word


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_scene_source_has_no_banned_words(name):
    from pyv.timeline import BANNED_SUBSTRINGS
    module = importlib.import_module(name)
    source = open(module.__file__, encoding="utf-8").read()
    for word in BANNED_SUBSTRINGS:
        assert word.lower() not in source.lower(), (name, word)


def _glyph_pixels(ch: str, size: int = 40) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size * 2, size * 2)
    ctx = cairo.Context(surface)
    ctx.select_font_face("PingFang SC", cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)
    ctx.set_source_rgb(0, 0, 0)
    ctx.move_to(4, size)
    ctx.show_text(ch)
    surface.flush()
    return bytes(surface.get_data())


def _is_missing_glyph(ch: str) -> bool:
    """字体没有该字形时会画成同一个豆腐块，可据此比对。"""
    return _glyph_pixels(ch) == _glyph_pixels("\ue000")


@pytest.mark.parametrize("name", SCENE_MODULES)
def test_every_character_in_scene_source_is_renderable(name, monkeypatch):
    """PingFang SC 缺字形时会静默画成豆腐块，必须提前拦住。"""
    module = importlib.import_module(name)
    original = module.text
    drawn: list[str] = []

    def spy(ctx, s, *args, **kwargs):
        drawn.append(s)
        return original(ctx, s, *args, **kwargs)

    monkeypatch.setattr(module, "text", spy)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 180)
    ctx = cairo.Context(surface)
    module.render(ctx, 0.5, 320, 180, _params_for(name))

    assert drawn, "场景应当至少画出一行文字"
    for s in drawn:
        for ch in s:
            if ch.isspace():
                continue
            assert not _is_missing_glyph(ch), (
                f"{name} 画的字符 {ch!r} 不在 PingFang SC 里，会渲染成豆腐块"
            )


# ------------------------------------------------------ EP02 · CSN 全序的场景


def _ep02_params(renderer: str) -> dict:
    """EP02 契约里某个场景的画面内容。"""
    from pyv import contract as contract_mod

    path = contract_mod.CONTRACTS_DIR / "csn-total-ordering.json"
    for segment in contract_mod.load_contract(path).segments:
        if segment.renderer == renderer:
            return segment.params
    raise AssertionError(f"EP02 契约里没有 {renderer}")


def test_s02_mixed_ranks_follow_the_commit_order():
    """时间轴上的名次由契约里的提交顺序决定，不由编号决定。"""
    import pyv.scenes.s02_mixed as s02

    params = _ep02_params("pyv.scenes.s02_mixed")
    ranks = s02.commit_ranks(params)
    ids = [str(x) for x in params["txn_ids"]]
    order = [str(x) for x in params["commit_order"]]
    assert sorted(ranks) == list(range(len(ids)))
    for index, txn_id in enumerate(ids):
        assert ranks[index] == order.index(txn_id)


def test_s02_mixed_commit_order_is_not_the_id_order():
    """这期讲的就是「先后是乱的」——提交顺序必须真的和编号顺序不同。"""
    params = _ep02_params("pyv.scenes.s02_mixed")
    assert [str(x) for x in params["commit_order"]] != [
        str(x) for x in params["txn_ids"]
    ]


def test_s03_counter_numbers_strictly_increase():
    import pyv.scenes.s03_counter as s03

    params = _ep02_params("pyv.scenes.s03_counter")
    values = [int(v) for v in s03.csn_sequence(params)]
    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_s03_counter_reading_starts_before_the_first_number():
    """计数器先显示起始值，发一个号才跳一次。"""
    import pyv.scenes.s03_counter as s03

    params = _ep02_params("pyv.scenes.s03_counter")
    readings = s03.counter_reading(params)
    assert readings[0] == str(params["counter_value"])
    assert readings[1:] == [str(v) for v in params["csn_values"]]


def test_s05_layers_has_six_layers():
    import pyv.scenes.s05_layers as s05

    params = _ep02_params("pyv.scenes.s05_layers")
    assert s05.layer_count(params) == 6
    assert len(params["layer_ids"]) == len(params["layer_names"]) \
        == len(params["layer_roles"]) == 6


def test_s02_and_s03_tell_the_same_story():
    """s02 说「谁先 commit 是乱的」，s03 必须按同一个领取顺序发号。

    两段画面用的是同一组事务：如果 s03 的发号顺序跟 s02 的提交顺序对不上，
    观众会看到「最后 commit 的事务拿到了最小的号」这种自相矛盾的画面。
    """
    mixed = _ep02_params("pyv.scenes.s02_mixed")
    counter = _ep02_params("pyv.scenes.s03_counter")
    assert [str(x) for x in counter["txn_ids"]] == [
        str(x) for x in mixed["commit_order"]
    ]

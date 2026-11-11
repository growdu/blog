"""测试用场景：画一块可见色块。

渲染管线的集成测试用它，不依赖 pyv/scenes 下的正式场景，
这样渲染引擎的提交可以独立通过测试。
"""
from __future__ import annotations


def render(ctx, t: float, w: int, h: int, params=None) -> None:
    """画一个随进度变宽的深蓝色块。"""
    ctx.set_source_rgb(0.17, 0.30, 0.49)
    ctx.rectangle(w * 0.2, h * 0.3, w * 0.6 * max(0.1, t), h * 0.4)
    ctx.fill()

"""场景参数：本期内容从契约里取，缺了就当场报错。

分工原则（2026-11-11 定）：

- **本期内容进契约**——文案、数字、标签、枚举。改一句文案只改契约，不动代码。
- **版式常量留代码**——位置、尺寸、配色、动效曲线。

场景渲染器不再写死任何一期的文案。参数缺失必须报错，
不能悄悄退回硬编码的旧文案——那会让契约与画面的不一致变得无声无息。
"""
from __future__ import annotations

from typing import Any, Iterable


class MissingParam(KeyError):
    """契约缺少场景需要的参数。"""


def check_required(params: dict, keys: Iterable[str], scene: str = "") -> None:
    """渲染前先查一遍：缺的全都报出来，而不是只报第一个。"""
    missing = [k for k in keys if k not in params]
    if missing:
        where = f"（场景 {scene}）" if scene else ""
        raise MissingParam(
            f"场景参数缺少 {', '.join(repr(k) for k in missing)}{where}"
        )


class Params:
    """契约参数的只读视图。

    缺键直接抛 `MissingParam`，错误信息里带上场景号——
    契约写错时要在渲染之前就看见，而不是渲染到一半才炸。
    """

    __slots__ = ("_data", "_scene")

    def __init__(self, data: dict | None, scene: str = "") -> None:
        self._data = data or {}
        self._scene = scene

    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            where = f"（场景 {self._scene}）" if self._scene else ""
            raise MissingParam(f"场景参数缺少 {key!r}{where}")
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """可选参数：有就用，没有用默认值。"""
        return self._data.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def as_dict(self) -> dict:
        return dict(self._data)

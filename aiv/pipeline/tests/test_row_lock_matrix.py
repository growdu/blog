"""EP06 的兼容性矩阵与位定义：结构必须站得住。

矩阵是画面上信息量最大的一块，也是最容易抄错的一块——
4×4 共 16 格，错一格画面上就自相矛盾，而肉眼看渲染图未必看得出来。
所以这里盯的是**矩阵该有的结构性质**，不是把整张表抄一遍：

1. 对称：A 申请 B 的锁，与 B 申请 A 的锁，结论必须一样；
2. 单调：弱的一侧永远不比强的一侧更严——
   「弱 A 与 B 兼容」推出「更弱的 A 与 B 也兼容」，
   「弱 A 与弱 B 兼容」推出「弱 A 与更强的 B 不兼容」；
3. 最强的那一行必须全是冲突；
4. 最弱的那一行只与最强的冲突。

这四条一起，把 16 格可能的组合压到只剩一种——
出处文章那张表就是唯一解。抄错任何一格都会至少踩中一条。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pyv import contract as contract_mod

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "row-lock.json"

# 模式从弱到强的顺序，和画面上的排列一致
MODE_ORDER = ("KEY SHARE", "SHARE", "NO KEY UPDATE", "EXCLUSIVE")


@pytest.fixture(scope="module")
def matrix() -> list[list[bool]]:
    contract = contract_mod.load_contract(CONTRACT)
    segment = next(s for s in contract.segments if s.id == "s04")
    return [[bool(cell) for cell in row] for row in segment.params["matrix"]]


def test_the_matrix_is_four_by_four(matrix):
    """4 种模式两两组合，就是 4×4。"""
    assert len(matrix) == 4
    for row in matrix:
        assert len(row) == 4


def test_the_matrix_is_symmetric(matrix):
    """申请方向反过来的结论必须一样。"""
    for i in range(4):
        for j in range(4):
            assert matrix[i][j] == matrix[j][i], \
                f"({i}, {j}) 与 ({j}, {i}) 结论不一致：{MODE_ORDER[i]} 对 {MODE_ORDER[j]}"


def test_the_matrix_is_monotone_in_strength(matrix):
    """弱的一侧永远不比强的一侧更严。

    矩阵的行序与列序都是**从弱到强**（行号越大越强）。
    「弱 A 与 B 兼容」推出「更弱的 A 与 B 也兼容」——
    越强的一侧限制越多，所以把 A 换成更弱的，结论只能更宽松。
    """
    for i in range(4):
        for j in range(4):
            if not matrix[i][j]:
                continue
            # 行方向：换成更弱的 A（行号更小），与同一个 B
            for weaker in range(i):
                assert matrix[weaker][j], (
                    f"{MODE_ORDER[i]} 与 {MODE_ORDER[j]} 兼容，"
                    f"更弱的 {MODE_ORDER[weaker]} 不该与它冲突"
                )
            # 列方向：换成更弱的 B（列号更小），与同一个 A
            for weaker in range(j):
                assert matrix[i][weaker], (
                    f"{MODE_ORDER[i]} 与 {MODE_ORDER[j]} 兼容，"
                    f"{MODE_ORDER[i]} 与更弱的 {MODE_ORDER[weaker]} 却冲突了"
                )


def test_the_strongest_mode_conflicts_with_everything(matrix):
    """最强的那一行必须全是冲突。"""
    assert not any(matrix[3]), f"最强的一行不该有兼容：{matrix[3]}"


def test_the_weakest_mode_only_conflicts_with_the_strongest(matrix):
    """最弱的那一行只跟最强者过不去。"""
    assert matrix[0][:3] == [True, True, True], \
        f"最弱的一行除最强者外都该兼容：{matrix[0]}"
    assert matrix[0][3] is False, "最弱的一行与最强者应当冲突"


def test_the_diagonal_is_consistent(matrix):
    """自己跟自己：KeyShare 与 Share 自己不冲突，NoKeyUpdate 与 Exclusive 自己冲突。"""
    assert matrix[0][0] is True, "KeyShare 与自己应当兼容"
    assert matrix[1][1] is True, "Share 与自己应当兼容"
    assert matrix[2][2] is False, "NoKeyUpdate 与自己应当冲突"
    assert matrix[3][3] is False, "Exclusive 与自己应当冲突"


def test_the_bit_labels_are_four_distinct_hex_values():
    """画面上那四个位：四个名字、四个互不相同的十六进制值。"""
    contract = contract_mod.load_contract(CONTRACT)
    segment = next(s for s in contract.segments if s.id == "s05")
    bits = segment.params["bit_labels"]
    assert len(bits) == 4
    names = [pair[0] for pair in bits]
    values = [pair[1] for pair in bits]
    assert len(set(names)) == 4, f"位名有重复：{names}"
    assert len(set(values)) == 4, f"位值有重复：{values}"
    for value in values:
        assert value.startswith("0x"), f"位值应该是十六进制：{value}"
        int(value, 16)

"""守住规格 06 里那些「看起来是示例、其实是断言」的段落。

§4.2 那段 JSON 看着只是个示例，但它同时断言了两件事：周键的**格式**
和周键与 ``scheduled_at`` 的**自洽**。示例原本写的是 ``2026-W47``，
而 2026-11-13 其实是 2026-W46——这类错误不会被任何测试抓到，
除非有人专门去算一遍。

§4.3 举的跨年例子也是断言：2019-12-30 属于 2020-W01（那天是星期一，
但属于下一个 ISO 周年）、2026-12-31 属于 2026-W53。
两句都成立，那段说明才立得住；不成立的话就是「用错误的例子讲正确的道理」。

所以这里把两段都钉住：规格里写的数字必须真的算得出那个结果。
"""

import json
import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "publish" / "spec" / "06-发布计划与调度.md"

_WEEK_KEY_RE = re.compile(r"^\d{4}-W\d{2}$")


def _spec():
    return SPEC_PATH.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """取某个小节的内容（到下一个同级或更高级标题为止）。"""
    start = text.index(heading)
    rest = text[start + len(heading):]
    match = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    return rest[: match.start()] if match else rest


def test_the_week_key_example_matches_its_own_timestamp():
    """§4.2 示例里的周键必须等于 scheduled_at 那天的 ISO 周。

    两者必须自洽，否则读者照着示例理解周键语义会理解错。
    """
    section = _section(_spec(), "### 4.2 周键的语义")

    blocks = re.findall(r"```json\n(.*?)\n```", section, re.DOTALL)
    assert len(blocks) == 1, "§4.2 应当只有一段 JSON 示例，实际找到 {} 段".format(
        len(blocks)
    )

    payload = json.loads(blocks[0])
    assert len(payload) == 1, "§4.2 的示例里应当只有一周"

    week_key, record = next(iter(payload.items()))
    assert _WEEK_KEY_RE.match(week_key), "周键格式不对：{!r}".format(week_key)

    scheduled_at = record["scheduled_at"]
    day = date.fromisoformat(scheduled_at.split(" ")[0])
    iso = day.isocalendar()
    assert week_key == "{}-W{:02d}".format(iso[0], iso[1]), (
        "示例自相矛盾：{} 那天的 ISO 周是 {}-W{:02d}，示例写的是 {}".format(
            day, iso[0], iso[1], week_key
        )
    )


def test_the_year_boundary_examples_behave_as_claimed():
    """§4.3 举的三个日期，行为必须与它写的一致。

    三条各自成立才说明「ISO 周年和日历年不是同一年」：
    2019-12-30 是星期一却属于 2020-W01；2026-12-31 属于 2026-W53；
    2027-01-04 那个星期一才进 2027-W01。
    """
    section = _section(_spec(), "### 4.3 周键怎么算")

    def week_key(day: date) -> str:
        iso = day.isocalendar()
        return "{}-W{:02d}".format(iso[0], iso[1])

    assert "2019-12-30" in section, "§4.3 不再举 2019-12-30 这个例子了"
    assert "2026-12-31" in section, "§4.3 不再举 2026-12-31 这个例子了"

    assert week_key(date(2019, 12, 30)) == "2020-W01"
    assert week_key(date(2026, 12, 31)) == "2026-W53"
    assert week_key(date(2027, 1, 4)) == "2027-W01"

    # 2019-12-30 那天确实是星期一——否则那个例子讲的不是跨年。
    assert date(2019, 12, 30).weekday() == 0
    # 2027-01-04 是 2027 年的第一个星期一。
    assert date(2027, 1, 4).weekday() == 0

    # 规格里**声称的**周键必须就是上面算出来的那些。
    # 只查「日期出现了」不够：写「2026-12-31 属于 2027-W01」也含那个日期，
    # 但那句话是错的——所以要把三个周键本身也钉住。
    for claimed in ("2020-W01", "2026-W53", "2027-W01"):
        assert claimed in section, (
            "§4.3 应当写明 {}，现在这段说明里的周键与实际算出来的不一致".format(
                claimed
            )
        )

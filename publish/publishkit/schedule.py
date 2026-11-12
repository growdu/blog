"""调度层：候选集、选题规则、周键。

这一层是**平台无关**的触发器：它只回答「什么时候发、发什么」，把「怎么发」
交给平台 adapter（``publish/spec/06-发布计划与调度.md`` §一）。

**它不 import 任何平台 adapter 的模块**（§11.1 的接缝原则）：平台怎么发，
由 ``publish/capabilities/<platform>.toml`` 的 ``[adapter].command`` 决定。

三块东西：

1. **配置解析**（§5.4）：仓库路径 / 凭据路径 / 状态目录都要能配。
   环境变量给默认值，命令行选项覆盖环境变量（launchd 的
   ``EnvironmentVariables`` 只能给环境变量，所以这两条腿都得有）。
2. **周键**（§4.3）：ISO-8601 周编号。
3. **候选集与选题规则**（§3.2、§3.3）：这篇该发不发、该发到哪、什么时候发。

**这一期只驱动文档类平台**（能力模型里 ``kind == "document"``）。
视频平台（``channels`` / ``bilibili``）吃的是视频期号而不是内容单元，
生命周期也不同（出包 → 人工发 → 回填链接），走它们自己那套 CLI。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import PublishKitError
from .capability import list_capabilities
from .contract import ContractError, parse_content_date, read_contract

__all__ = [
    "PUBLISHED_STATUSES",
    "ContentUnit",
    "OutboxIndex",
    "OutboxRecord",
    "ScheduleConfig",
    "ScheduleConfigError",
    "ScheduleError",
    "ScheduleIneligibleError",
    "SchedulePublishError",
    "content_id_for",
    "discover_units",
    "flatten_content_id",
    "load_outbox_index",
    "resolve_config",
    "select_for_platform",
    "snapshot_name",
    "target_platforms",
    "week_key",
    "week_window",
]


class ScheduleError(PublishKitError):
    """调度层读不了配置、算不出选题，或状态文件写不了。"""


class ScheduleConfigError(ScheduleError):
    """配置不对：路径不存在、平台没有能力声明、参数不合法。"""


class ScheduleIneligibleError(ScheduleError):
    """这一篇不合格：内容契约不满足，或它不适合这个平台。"""


class SchedulePublishError(ScheduleError):
    """发布过程出了岔子：接口报错、写盘失败、结果未知。"""


#: 「已经发过」的状态。
#:
#: ``packaged`` 也在里面——它是「出包待人工上传」，不是「已发布」，但它
#: 意味着**这一篇已经走完流水线**。不把它算进去，它就会因为「最久未发」
#: 而每周被选上一次，轮转队列卡死在一篇上。
PUBLISHED_STATUSES = ("published", "reviewing", "drafted", "packaged")


# --- 配置（§5.4） --------------------------------------------------------


@dataclass(frozen=True)
class ScheduleConfig:
    """调度层能写盘的每一个位置。

    每一个都能被命令行选项与环境变量指到别处——测试绝不许写进仓库。
    """

    repo_root: Path
    posts_dir: Path
    outbox_dir: Path
    state_dir: Path
    schedule_file: Path
    capabilities_dir: Path
    secrets_file: Path


def resolve_config(
    *,
    repo_root=None,
    state_dir=None,
    posts_dir=None,
    outbox_dir=None,
    capabilities_dir=None,
    schedule_file=None,
    secrets=None,
    environ=None,
) -> ScheduleConfig:
    """把三个可配项解析成一份配置（§5.4）。

    优先级：**命令行选项 > 环境变量 > 默认值**。

    ==================== ========================== ==========================
    环境变量               含义                        默认
    ==================== ========================== ==========================
    ``PUBLISH_REPO``      仓库根路径                  从当前目录往上找
    ``PUBLISH_SECRETS``   凭据文件                    ``$REPO/weixin/secrets.json``
    ``PUBLISH_STATE_DIR`` 状态目录                    ``$REPO/publish``
    ==================== ========================== ==========================

    状态目录一改，``schedule.json`` 与 ``outbox/`` **都跟着走**——
    outbox 不是钉死在 ``$PUBLISH_REPO/publish/outbox`` 的。
    """
    env = os.environ if environ is None else environ

    if repo_root is not None:
        root = Path(repo_root)
    elif env.get("PUBLISH_REPO"):
        root = Path(env["PUBLISH_REPO"])
    else:
        root = discover_repo_root(Path.cwd())

    if state_dir is not None:
        state = Path(state_dir)
    elif env.get("PUBLISH_STATE_DIR"):
        state = Path(env["PUBLISH_STATE_DIR"])
    else:
        state = root / "publish"

    if secrets is not None:
        secret_path = Path(secrets)
    elif env.get("PUBLISH_SECRETS"):
        secret_path = Path(env["PUBLISH_SECRETS"])
    else:
        secret_path = root / "weixin" / "secrets.json"

    return ScheduleConfig(
        repo_root=root,
        posts_dir=Path(posts_dir) if posts_dir is not None else root / "source" / "_posts",
        outbox_dir=Path(outbox_dir) if outbox_dir is not None else state / "outbox",
        state_dir=state,
        schedule_file=(
            Path(schedule_file) if schedule_file is not None else state / "schedule.json"
        ),
        capabilities_dir=(
            Path(capabilities_dir)
            if capabilities_dir is not None
            else root / "publish" / "capabilities"
        ),
        secrets_file=secret_path,
    )


def discover_repo_root(start: Path) -> Path:
    """从 ``start`` 往上找含有 ``publish/capabilities`` 的那一层。

    找不到就用 ``start`` 本身——调用方马上会因为「能力声明目录不存在」
    而报配置错误，那比在这里猜一个路径好。
    """
    current = Path(start).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / "publish" / "capabilities").is_dir():
            return candidate
    return current


# --- 周键（§4.3） --------------------------------------------------------


def week_key(day: date) -> str:
    """ISO-8601 周编号：``2026-W47``。

    用 ``datetime.date.isocalendar()`` 算，**不自己写周数算法**——
    跨年那周自己写必错：2026-12-31 属于 2027-W01（§4.3）。
    """
    iso = day.isocalendar()
    return "{}-W{:02d}".format(iso[0], iso[1])


def week_window(day: date) -> tuple:
    """那一周的周一到周日（含两端）。

    周一是周一——``isocalendar()`` 也是这么定的，两边不能各定一套。
    """
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


# --- 内容单元（§3.2） ----------------------------------------------------


@dataclass(frozen=True)
class ContentUnit:
    """一个内容单元：内容契约 + 调度层要用的日期。

    ``content_id`` 是**站内路径**（相对 ``source/_posts/``，去后缀），
    不是文件名——``db/postgresql/demo`` 就是一个内容单元的 id。
    """

    content_id: str
    contract: object
    publish_on: date | None
    date: date | None

    @property
    def platforms(self) -> tuple:
        return tuple(self.contract.platforms)

    @property
    def title(self) -> str:
        return self.contract.title

    @property
    def sort_date(self) -> date:
        """排序用的日期：``publish_on`` 优先，缺省用 ``date``（§3.3）。

        两个都没有时排最后——排序键必须**总是**存在，否则「最久未发」
        这条规则会在缺日期的那几篇上抛异常。
        """
        return self.publish_on or self.date or date.max


def content_id_for(path, posts_dir) -> str:
    """内容单元 id：相对 ``source/_posts/`` 的路径去掉 ``.md``。

    例：``db/logical_decode/postgresql逻辑复制-DML.md`` →
    ``db/logical_decode/postgresql逻辑复制-DML``。
    """
    root = Path(posts_dir).resolve()
    relative = Path(path).resolve().relative_to(root)
    return relative.with_suffix("").as_posix()


def discover_units(posts_dir) -> tuple:
    """读出全部内容单元。

    返回 ``(内容单元, 错误信息)``：**坏文件不静默跳过**——错误信息一条条
    报出来（哪个文件、为什么）。但它也不该让整轮调度停摆：仓库里几百篇，
    一篇坏了不是其余的都不发。
    """
    root = Path(posts_dir)
    if not root.is_dir():
        raise ScheduleConfigError("找不到内容单元目录：{}".format(root))

    units = []
    errors = []
    for path in sorted(root.rglob("*.md")):
        try:
            contract = read_contract(path)
        except ContractError as exc:
            errors.append("{}：{}".format(content_id_for(path, root), exc))
            continue

        publish_on = date.fromisoformat(contract.publish_on) if contract.publish_on else None
        published = parse_content_date(contract.date) if contract.date else None
        units.append(
            ContentUnit(
                content_id=content_id_for(path, root),
                contract=contract,
                publish_on=publish_on,
                date=published,
            )
        )
    return units, errors


# --- outbox 索引（§3.3 的「已发过」） -------------------------------------


@dataclass(frozen=True)
class OutboxRecord:
    """outbox 里的一个状态快照。"""

    content_id: str
    platform: str
    status: str
    path: Path
    data: dict
    mtime_ns: int


@dataclass(frozen=True)
class OutboxIndex:
    """``publish/outbox/*.json`` 的索引。

    **靠扫目录建索引，不靠算文件名去找**：快照是自描述的（文件里写着
    ``content_id`` 与 ``platform``），文件名只是约定。
    """

    records: dict = field(default_factory=dict)
    errors: tuple = ()

    def get(self, content_id: str, platform: str):
        """某篇在某平台上的那条快照；没有就是 ``None``。"""
        return self.records.get((content_id, platform))

    def is_published(self, content_id: str, platform: str) -> bool:
        """这篇在这个平台上是不是已经走完流水线了。"""
        record = self.get(content_id, platform)
        return record is not None and record.status in PUBLISHED_STATUSES

    def for_platform(self, platform: str) -> list:
        """某个平台的全部快照，按 content_id 排序。"""
        return sorted(
            (record for record in self.records.values() if record.platform == platform),
            key=lambda record: record.content_id,
        )


def load_outbox_index(outbox_dir) -> OutboxIndex:
    """扫描 outbox 目录建索引。

    坏 JSON 不静默忽略：记进 ``errors``，让调用方报出来——一个读不动的
    快照文件，意味着一篇可能已经发过了却查不到。
    """
    root = Path(outbox_dir)
    records = {}
    errors = []
    if not root.is_dir():
        return OutboxIndex(records={}, errors=())

    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append("{}：读不出来（{}）".format(path.name, exc))
            continue
        if not isinstance(data, dict):
            errors.append("{}：不是一份映射".format(path.name))
            continue
        content_id = data.get("content_id")
        platform = data.get("platform")
        if not isinstance(content_id, str) or not isinstance(platform, str):
            errors.append("{}：缺 content_id 或 platform".format(path.name))
            continue
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        records[(content_id, platform)] = OutboxRecord(
            content_id=content_id,
            platform=platform,
            status=str(data.get("status") or ""),
            path=path,
            data=data,
            mtime_ns=mtime_ns,
        )
    return OutboxIndex(records=records, errors=tuple(errors))


# --- outbox 文件名约定（§6.5） -------------------------------------------


def flatten_content_id(content_id: str) -> str:
    """把内容 id 压成一个能进文件名的串。

    ``db/postgresql/demo`` → ``db-postgresql-demo``。

    **顺带校验**：``.`` / ``..`` 这类路径段一律拒绝——写错地方只是不整洁，
    删错地方是破坏（与 ``toutiao/toutiao/publish.py`` 的 ``flatten_id()``
    同一套理由；这里独立实现，契约层不 import adapter 的模块）。
    """
    if not isinstance(content_id, str) or not content_id.strip():
        raise ScheduleError(
            "content_id 必须是非空字符串，实际是 {!r}".format(content_id)
        )
    for segment in content_id.split("/"):
        if segment in (".", ".."):
            raise ScheduleError(
                "content_id 的路径段 {!r} 会跑出目录：content_id={!r}".format(
                    segment, content_id
                )
            )
    flat = content_id.replace("/", "-")
    if flat in (".", ".."):
        raise ScheduleError("content_id 不能是 {!r}：它就是目录名本身".format(flat))
    return flat


def snapshot_name(content_id: str, platform: str) -> str:
    """outbox 快照的文件名：``<压平后的 content_id>__<platform>.json``。"""
    return "{}__{}.json".format(flatten_content_id(content_id), platform)


# --- 平台（这一期只驱动文档类） -------------------------------------------


def target_platforms(config: ScheduleConfig, platform_filter=None) -> list:
    """这一期调度器驱动的平台：能力声明里 ``kind == "document"`` 的那些。

    视频平台（``channels`` / ``bilibili``）吃的是视频期号而不是内容单元，
    生命周期也不同，进不了这一期的候选集。

    ``platform_filter`` 给定时只留那一个平台（CLI 的 ``--platform``）；
    给了一个视频平台就**报错**——不许静默跳过，更不许假装发过了。
    """
    capabilities = list_capabilities(capabilities_dir=config.capabilities_dir)
    documents = [cap for cap in capabilities if cap.kind == "document"]
    if platform_filter:
        chosen = [cap for cap in documents if cap.id == platform_filter]
        if not chosen:
            known = {cap.id for cap in capabilities}
            if platform_filter in known:
                raise ScheduleConfigError(
                    "{} 是视频平台，这一期调度器只驱动文档类平台".format(platform_filter)
                )
            raise ScheduleConfigError(
                "找不到平台 {!r} 的能力声明：{}".format(
                    platform_filter, config.capabilities_dir / "{}.toml".format(platform_filter)
                )
            )
        return chosen
    return sorted(documents, key=lambda cap: cap.id)


# --- 选题规则（§3.3） ----------------------------------------------------


def select_for_platform(units, platform, *, window, outbox=None, exclude=()):
    """在某个平台的候选集里选出本周要发的那一篇。

    规则（§3.3）：

    1. 候选集 = ``platforms`` 里含这个平台的内容单元；
    2. 其中有 ``publish_on`` 落在本周的 → 选它（``publish_on`` 最早的；
       再并列按 ``content_id`` 字典序，保证确定性）；
    3. 没有 → 剔除**已发过的**（outbox 里有同 ``(content_id, platform)``
       且状态是成功态的）；
    4. 剩下的按「``publish_on``，缺省用 ``date``」升序，取第一篇 =
       最久未发的；
    5. 一个都不剩 → 明确说「本周没有可发的」。

    返回 ``(选中的内容单元, 选它的理由)``。选不出来时内容单元是 ``None``，
    理由是一句人话——「本周没有可发的」不是错误，是一个事实。
    """
    index = outbox if outbox is not None else OutboxIndex()
    candidates = [unit for unit in units if platform in unit.platforms]
    if not candidates:
        return None, "候选集是空的：没有内容单元声明 platform 包含 {!r}".format(platform)

    # 规则 2：publish_on 落在本周的优先（作者有最终控制权）。
    monday, sunday = window
    this_week = [
        unit
        for unit in candidates
        if unit.publish_on is not None and monday <= unit.publish_on <= sunday
    ]
    if this_week:
        chosen = min(this_week, key=lambda unit: (unit.publish_on, unit.content_id))
        return chosen, "publish_on {} 落在本周".format(chosen.publish_on)

    # 规则 3：剔除已发过的。
    rest = [
        unit
        for unit in candidates
        if unit.content_id not in exclude
        and not index.is_published(unit.content_id, platform)
    ]
    if not rest:
        return None, "本周没有可发的：候选集里的内容都已经发到过 {}".format(platform)

    # 规则 4：最久未发。
    chosen = min(rest, key=lambda unit: (unit.sort_date, unit.content_id))
    return chosen, "最久未发（{}）".format(chosen.sort_date)

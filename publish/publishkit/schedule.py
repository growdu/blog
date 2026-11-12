"""调度层：候选集、选题规则、周键、调度状态文件。

这一层是**平台无关**的触发器：它只回答「什么时候发、发什么」，把「怎么发」
交给平台 adapter（``publish/spec/06-发布计划与调度.md`` §一）。

**它不 import 任何平台 adapter 的模块**（§11.1 的接缝原则）：平台怎么发，
由 ``publish/capabilities/<platform>.toml`` 的 ``[adapter].command`` 决定。

四块东西：

1. **配置解析**（§5.4）：仓库路径 / 凭据路径 / 状态目录都要能配。
   环境变量给默认值，命令行选项覆盖环境变量（launchd 的
   ``EnvironmentVariables`` 只能给环境变量，所以这两条腿都得有）。
2. **周键**（§4.3）：ISO-8601 周编号。
3. **候选集与选题规则**（§3.2、§3.3）：这篇该发不发、该发到哪、什么时候发。
4. **调度状态文件**（§4.1、§4.2）：``publish/schedule.json``，周键幂等。

**这一期只驱动文档类平台**（能力模型里 ``kind == "document"``）。
视频平台（``channels`` / ``bilibili``）吃的是视频期号而不是内容单元，
生命周期也不同（出包 → 人工发 → 回填链接），走它们自己那套 CLI。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
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
    "ScheduleState",
    "WeeklyResult",
    "WeekRecord",
    "content_id_for",
    "discover_units",
    "flatten_content_id",
    "load_outbox_index",
    "resolve_config",
    "run_weekly",
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

#: 自动重试的次数上限（§7.2「超过上限（比如 3 次）转人工」）。
MAX_RETRY_ATTEMPTS = 3


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

    def is_blocked(self, content_id: str, platform: str) -> bool:
        """这篇在这个平台上是不是**不该再被自动选中**。

        四种情况：

        - 已经发过的（成功态）→ 不再发；
        - 结果未知（超时，§7.1 第三条）→ **不能自动重发**，可能已经发出去了；
        - 失败且不自动重试的（这一篇不合格 / 平台审核不通过）→ 转人工，
          而且它不该继续霸占「最久未发」的位置（§7.4）；
        - 失败但可重试的 → 不在这里挡（它由重试那一路处理）。
        """
        record = self.get(content_id, platform)
        if record is None:
            return False
        if record.status in PUBLISHED_STATUSES:
            return True
        if record.status == "unknown":
            return True
        if record.status == "failed" and record.data.get("retryable") is False:
            return True
        return False

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
        return None, "候选集是空的：没有内容单元的 platforms 里包含 {!r}".format(platform)

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

    # 规则 3：剔除已发过的（也剔除结果未知的、转人工的）。
    rest = [
        unit
        for unit in candidates
        if unit.content_id not in exclude
        and not index.is_blocked(unit.content_id, platform)
    ]
    if not rest:
        return None, "本周没有可发的：候选集里的内容都已经发到过 {}".format(platform)

    # 规则 4：最久未发。
    chosen = min(rest, key=lambda unit: (unit.sort_date, unit.content_id))
    return chosen, "最久未发（{}）".format(chosen.sort_date)


# --- 调度状态文件（§4.1、§4.2） -------------------------------------------


@dataclass(frozen=True)
class WeekRecord:
    """一周一条调度记录（§4.2）。

    字段是固定的五个：``content_id`` / ``platforms`` / ``scheduled_at`` /
    ``trigger`` / ``done``。这个文件是入库的，形状定下来就是对外契约。
    """

    content_id: str
    platforms: tuple
    scheduled_at: str
    trigger: str
    done: bool

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "platforms": list(self.platforms),
            "scheduled_at": self.scheduled_at,
            "trigger": self.trigger,
            "done": self.done,
        }

    @classmethod
    def from_dict(cls, data: object, week: str = "") -> "WeekRecord":
        """读一条记录，字段不对就报错。

        状态文件是**手也要能改**的东西（人也会去改它），所以字段不对时
        必须指名道姓地说哪个字段不对，而不是默默跳过那一周——默默跳过
        意味着「这一周当没发过」，于是同一周发两遍。
        """
        where = "{} ".format(week) if week else ""
        if not isinstance(data, dict):
            raise ScheduleError(
                "{}调度记录的顶层必须是映射，实际是 {}".format(
                    where, type(data).__name__
                )
            )

        allowed = ("content_id", "platforms", "scheduled_at", "trigger", "done")
        for key in data:
            if key not in allowed:
                raise ScheduleError("{}调度记录出现未知字段 {}".format(where, key))

        content_id = data.get("content_id")
        if not isinstance(content_id, str) or not content_id.strip():
            raise ScheduleError("{}调度记录的 content_id 必须是非空字符串".format(where))

        platforms = data.get("platforms")
        if not isinstance(platforms, list) or not all(
            isinstance(item, str) and item.strip() for item in platforms
        ):
            raise ScheduleError("{}调度记录的 platforms 必须是字符串数组".format(where))

        scheduled_at = data.get("scheduled_at")
        if not isinstance(scheduled_at, str):
            raise ScheduleError("{}调度记录的 scheduled_at 必须是字符串".format(where))

        trigger = data.get("trigger")
        if not isinstance(trigger, str):
            raise ScheduleError("{}调度记录的 trigger 必须是字符串".format(where))

        done = data.get("done")
        if not isinstance(done, bool):
            raise ScheduleError("{}调度记录的 done 必须是布尔值".format(where))

        return cls(
            content_id=content_id,
            platforms=tuple(platforms),
            scheduled_at=scheduled_at,
            trigger=trigger,
            done=done,
        )


class ScheduleState:
    """``publish/schedule.json``——调度层自己的那层幂等键（§4.1）。

    **写入是原子的**：先写临时文件，再 ``os.replace`` 换名。中途崩了不会
    留下半个 JSON——半个 JSON 比没有更坏：读不出来的那份会被当成「没发过」，
    于是同一周发两遍。
    """

    def __init__(self, path, records=None):
        self.path = Path(path)
        self.records = dict(records or {})

    @classmethod
    def load(cls, path) -> "ScheduleState":
        """读调度状态。文件不存在 = 还没跑过（不是错误）。"""
        path = Path(path)
        if not path.exists():
            return cls(path, {})

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ScheduleError("调度状态文件读不了：{}（{}）".format(path, exc)) from exc

        try:
            data = json.loads(text)
        except ValueError as exc:
            raise ScheduleError(
                "调度状态文件不是合法 JSON：{}（{}）".format(path, exc)
            ) from exc

        if not isinstance(data, dict):
            raise ScheduleError("调度状态文件的顶层必须是映射：{}".format(path))

        records = {}
        for week, raw in data.items():
            records[week] = WeekRecord.from_dict(raw, week=week)
        return cls(path, records)

    def to_dict(self) -> dict:
        return {week: record.to_dict() for week, record in self.records.items()}

    def get(self, week: str):
        """某一周的记录；没有就是 ``None``。"""
        return self.records.get(week)

    def put(self, week: str, record: WeekRecord) -> None:
        self.records[week] = record

    def unfinished_weeks(self) -> list:
        """没跑完的周，按周键升序。

        周键是 ``YYYY-Www``，两位周号，所以字典序 = 时间序。
        """
        return sorted(
            week for week, record in self.records.items() if not record.done
        )

    def save(self) -> None:
        """原子写盘。"""
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

        handle, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            # 换名失败：临时文件不能留在状态目录里（它不是合法状态文件，
            # 下次读的时候只会多一个看不懂的东西）。
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


# --- 定时调度（§3.3 + §4.2 + §7.3） ---------------------------------------


@dataclass(frozen=True)
class WeeklyResult:
    """跑完一次定时调度之后的结果。"""

    week: str
    action: str
    content_id: str | None = None
    platforms: tuple = ()
    messages: tuple = ()
    ok: bool = True


def retry_failed(
    config: ScheduleConfig,
    publisher,
    *,
    dry_run: bool = False,
    skip=(),
    max_attempts: int = MAX_RETRY_ATTEMPTS,
):
    """把 outbox 里「失败且可重试」的记录重试一次（§7.2）。

    - ``status = "failed"`` 且 ``retryable`` 不是 False 的记录：重试一次；
    - ``retryable = False`` 的（这一篇不合格 / 平台审核不通过）：
      **永不自动重试**；
    - 已经试够 ``max_attempts`` 次的：转人工，不再自动重试。

    返回 ``(消息列表, 本次处理过的 (content_id, platform))``。
    """
    index = load_outbox_index(config.outbox_dir)
    messages = []
    handled = set()
    for record in sorted(index.records.values(), key=lambda r: (r.content_id, r.platform)):
        if record.status != "failed":
            continue
        if record.data.get("retryable") is False:
            continue
        attempts = record.data.get("attempts")
        if isinstance(attempts, int) and attempts >= max_attempts:
            continue
        key = (record.content_id, record.platform)
        if key in skip:
            continue
        handled.add(key)
        if dry_run:
            messages.append(
                "（演练）会重试 {} → {}".format(record.content_id, record.platform)
            )
            continue
        if publisher(record.content_id, record.platform):
            messages.append("重试 {} → {}：成功。".format(record.content_id, record.platform))
        else:
            messages.append("重试 {} → {}：还是失败。".format(record.content_id, record.platform))
    return messages, handled


def run_weekly(
    config: ScheduleConfig,
    *,
    publisher,
    platform_filter=None,
    now=None,
    dry_run: bool = False,
) -> WeeklyResult:
    """跑一次定时调度。

    ``publisher`` 是「把一篇发到某个平台」这个动作，签名
    ``publisher(content_id, platform) -> bool``（True = 这一篇在这个平台上
    成功了）。它由 CLI 提供（真的去调 adapter）；这一层只管**策略**：
    选哪一篇、写不写周键、失败了怎么办。

    几条规则在这里生效：

    - §4.2 规则 1：本周的周键已经存在且 ``done = true`` → **跳过**；
    - §4.2 规则 2：存在但 ``done = false`` → 继续跑并覆盖该周的记录；
    - §7.3：有**别的**周没跑完 → **优先重试它**，而不是直接选新的一篇；
    - §3.4：某个平台失败不阻塞其他平台。

    ``dry_run`` 时**什么都不写**：不写 outbox、不调 adapter、不写周键。
    """
    now = now or datetime.now()
    state = ScheduleState.load(config.schedule_file)
    week = week_key(now.date())
    messages = []
    handled = set()

    # §7.3：优先重试未完成的周，而不是直接选新的一篇。
    unfinished = state.unfinished_weeks()
    if unfinished:
        outcomes = []
        for key in unfinished:
            record = state.get(key)
            ok, said = _publish_to_platforms(
                config,
                record.content_id,
                record.platforms,
                publisher,
                dry_run,
                skip=handled,
            )
            handled |= {(record.content_id, pid) for pid in record.platforms}
            messages.extend(said)
            outcomes.append((key, record, ok))
            if not dry_run:
                state.put(
                    key,
                    replace(record, done=ok),
                )
                state.save()
        said, retried = retry_failed(
            config, publisher, dry_run=dry_run, skip=handled
        )
        messages.extend(said)
        _key, first, _ok = outcomes[0]
        return WeeklyResult(
            week=week,
            action="retry",
            content_id=first.content_id,
            platforms=first.platforms,
            messages=tuple(messages),
            ok=all(ok for _key, _record, ok in outcomes),
        )

    # §7.2：定时任务跑的时候，把「失败且可重试」的记录重试一次。
    said, retried = retry_failed(config, publisher, dry_run=dry_run, skip=handled)
    messages.extend(said)
    handled |= retried

    # §4.2 规则 1：本周已经跑完 → 跳过。
    existing = state.get(week)
    if existing is not None and existing.done:
        return WeeklyResult(
            week=week,
            action="skipped",
            content_id=existing.content_id,
            platforms=existing.platforms,
            messages=(
                "{} 已经跑完（{}），本次跳过。".format(week, existing.content_id),
            ),
            ok=True,
        )

    units, errors = discover_units(config.posts_dir)
    for error in errors:
        messages.append("语料有问题，这一篇没进候选集：" + error)

    index = load_outbox_index(config.outbox_dir)
    for error in index.errors:
        messages.append("outbox 有读不动的快照：" + error)

    window = week_window(now.date())
    capabilities = target_platforms(config, platform_filter)
    target_ids = [cap.id for cap in capabilities]

    picks = []
    for capability in capabilities:
        unit, reason = select_for_platform(
            units,
            capability.id,
            window=window,
            outbox=index,
            exclude={content_id for content_id, _pid in handled},
        )
        if unit is None:
            messages.append("{}：{}".format(capability.id, reason))
            continue
        picks.append((capability.id, unit, reason))

    if not picks:
        # §3.3 规则 5：一个都不剩 → 明确说「本周没有可发的」，不静默成功。
        return WeeklyResult(
            week=week,
            action="nothing",
            messages=tuple(messages),
            ok=True,
        )

    # 一周发一篇（§4.1「同一周被调度两次 → 发两篇」）：取最早的那一篇。
    _platform_id, unit, reason = min(
        picks, key=lambda item: (item[1].sort_date, item[1].content_id)
    )
    platforms = tuple(pid for pid in target_ids if pid in unit.platforms)
    messages.append(
        "{}：选中 {}（{}，{}）".format(week, unit.content_id, reason, unit.title)
    )

    record = WeekRecord(
        content_id=unit.content_id,
        platforms=platforms,
        scheduled_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        trigger="weekly",
        done=False,
    )
    if not dry_run:
        # 先落一条 done = false：中途崩了，下一次跑就知道这周没跑完（§7.3）。
        state.put(week, record)
        state.save()

    ok, said = _publish_to_platforms(
        config, unit.content_id, platforms, publisher, dry_run, skip=handled
    )
    messages.extend(said)

    if not dry_run:
        state.put(week, replace(record, done=ok))
        state.save()

    return WeeklyResult(
        week=week,
        action="published",
        content_id=unit.content_id,
        platforms=platforms,
        messages=tuple(messages),
        ok=ok,
    )


def _publish_to_platforms(config, content_id, platforms, publisher, dry_run, skip=()):
    """把一篇发到几个平台上。返回 ``(是否全部成功, 消息列表)``。

    已经发到过的平台**跳过**——发布层的幂等键（§4.1）：重跑不会重发已成功
    的部分。某个平台失败**不阻塞**其他平台（§3.4）。
    ``skip`` 里是本次运行已经处理过的 ``(content_id, platform)``——同一轮里
    不重复动手。
    """
    ok = True
    messages = []
    for platform in platforms:
        if (content_id, platform) in skip:
            messages.append(
                "{} → {}：本次已经处理过，跳过。".format(content_id, platform)
            )
            continue
        index = load_outbox_index(config.outbox_dir)
        record = index.get(content_id, platform)
        if record is not None and record.status == "unknown":
            # 结果未知（超时）：不能自动重发——可能已经发出去了（§7.1 第三条）。
            messages.append(
                "{} → {}：结果未知，不自动重发，跳过。".format(content_id, platform)
            )
            continue
        if (
            record is not None
            and record.status == "failed"
            and record.data.get("retryable") is False
        ):
            # 不合格 / 审核不通过：转人工，不自动重试（§7.1）。
            messages.append(
                "{} → {}：转人工（不自动重试），跳过。".format(content_id, platform)
            )
            continue
        if index.is_published(content_id, platform):
            messages.append("{} 已经发到过 {}，跳过。".format(content_id, platform))
            continue
        if dry_run:
            messages.append("（演练）会把 {} 发到 {}".format(content_id, platform))
            continue

        published = publisher(content_id, platform)
        if published:
            messages.append("{} → {}：成功。".format(content_id, platform))
        else:
            ok = False
            messages.append("{} → {}：失败。".format(content_id, platform))
    return ok, messages

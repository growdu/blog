"""守住触发器模板：跑的命令、注入的路径、触发的时间。

模板是这一层里**唯一一件自己会跑**的东西——没有调用方检查它，
装错了就是每周五早上九点悄悄跑错一次，跑错的那次往往没人发现
（因为它本来就不该有可见输出）。

所以把它的关键参数钉住：命令拼错、周几跑、仓库路径没注入，
这三种改法各自要有一个用例变红。
"""

import plistlib
from pathlib import Path

PUBLISH_DIR = Path(__file__).resolve().parents[1]
DEPLOY_DIR = PUBLISH_DIR / "deploy"

LAUNCHD = DEPLOY_DIR / "launchd.plist.template"
CRONTAB = DEPLOY_DIR / "crontab.template"
GITHUB_ACTION = DEPLOY_DIR / "github-action.yml.template"


def _load_launchd() -> dict:
    """把模板里的占位符换成假路径，然后当 plist 解析。"""
    text = LAUNCHD.read_text(encoding="utf-8")
    text = (
        text.replace("__PYTHON__", "/usr/bin/python3")
        .replace("__REPO__", "/repo")
        .replace("__HOME__", "/home/me")
    )
    return plistlib.loads(text.encode("utf-8"))


def _crontab_lines() -> list:
    """crontab 模板里的有效命令行（不含注释与空行）。"""
    lines = []
    for raw in CRONTAB.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


# --- 文件在 ------------------------------------------------------------


def test_the_three_templates_are_committed():
    """模板不在仓库里就没法安装——它们是这一层唯一的入口。"""
    for path in (LAUNCHD, CRONTAB, GITHUB_ACTION):
        assert path.is_file(), "缺少模板：{}".format(path)


# --- launchd -----------------------------------------------------------


def test_the_template_is_valid_plist():
    assert _load_launchd()["Label"] == "com.growdu.publish.schedule"


def test_the_job_runs_the_weekly_schedule():
    """命令必须是 ``publishkit.cli schedule weekly``。

    写错子命令的后果不是报错，而是**每周五什么都不发**——
    调度器自己不会说「我该跑但没跑」。
    """
    args = _load_launchd()["ProgramArguments"]
    assert args[-3:] == ["publishkit.cli", "schedule", "weekly"]


def test_the_job_runs_inside_the_publish_package():
    """``publishkit`` 挂在 ``publish/`` 下面（publish 本身不是包）。

    cwd 必须是 publish 目录，PYTHONPATH 也要指向它，
    否则 ``python3 -m publishkit.cli`` 根本找不到模块。
    """
    config = _load_launchd()
    assert config["WorkingDirectory"].endswith("/publish")
    assert config["EnvironmentVariables"]["PYTHONPATH"].endswith("/publish")


def test_the_job_gets_the_repo_and_the_secrets_from_the_environment():
    """规格 5.4：仓库路径与凭据路径由环境变量给，不写死在代码里。"""
    env = _load_launchd()["EnvironmentVariables"]
    assert env["PUBLISH_REPO"] == "/repo"
    assert env["PUBLISH_SECRETS"].endswith("/weixin/secrets.json")


def test_the_schedule_is_friday_nine():
    """每周五 09:00（launchd 的 Weekday 里 0 和 7 是周日，5 是周五）。"""
    slots = _load_launchd()["StartCalendarInterval"]
    assert len(slots) == 1, "只该有一个触发点，多了就是每周发好几次"
    slot = slots[0]
    assert slot["Weekday"] == 5
    assert slot["Hour"] == 9
    assert slot["Minute"] == 0


def test_the_job_does_not_run_at_load_time():
    """装上 launchd 的那一刻就发一次不是我们要的行为。"""
    assert _load_launchd()["RunAtLoad"] is False


def test_the_log_goes_to_the_library_logs_folder():
    config = _load_launchd()
    assert config["StandardOutPath"].endswith("/Library/Logs/publish-schedule.log")
    assert config["StandardErrorPath"] == config["StandardOutPath"]


# --- cron --------------------------------------------------------------


def test_the_crontab_runs_friday_nine():
    """服务器版：每周五 09:00。"""
    lines = _crontab_lines()
    assert len(lines) == 1, "crontab 模板里应当只有一条有效命令行"
    assert lines[0].startswith("0 9 * * 5 ")


def test_the_crontab_runs_the_same_command():
    """本机与服务器跑的是同一个入口（规格 5.1：触发方式与调度器解耦）。"""
    line = _crontab_lines()[0]
    assert "-m publishkit.cli schedule weekly" in line


def test_the_crontab_injects_the_repo_path():
    """cron 的环境变量极少，路径必须自己给。"""
    line = _crontab_lines()[0]
    assert "PUBLISH_REPO=__REPO__" in line
    assert "PYTHONPATH=__REPO__/publish" in line


# --- GitHub Actions ----------------------------------------------------


def test_the_github_action_template_carries_the_warning():
    """规格 5.2：CI schedule 不可行（出口 IP 动态，接口全被挡）。

    这个模板存在的意义是当对照物，所以「不要用」这句话必须在文件里，
    不能只写在规格里——有人只会看到模板。
    """
    text = GITHUB_ACTION.read_text(encoding="utf-8")
    assert "不推荐" in text
    assert "40164" in text or "出口 IP" in text


def test_the_github_action_template_still_points_at_the_same_entry():
    """它是参照物，所以命令要跟另外两个模板一致。"""
    text = GITHUB_ACTION.read_text(encoding="utf-8")
    assert "publishkit.cli schedule weekly" in text

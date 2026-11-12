"""通知：措辞必须区分状态。

含糊地说「已发布」是发布场景里最贵的一种 bug——
用户以为发出去了，实际没有。
"""
from __future__ import annotations

import json
import urllib.request

# 状态 → 该怎么说
PHRASES = {
    "packaged": "发布包已生成，待你上传",
    "submitted": "已投稿，审核中",
    "published": "已发布",
    "failed": "投稿失败",
}

WEBHOOK_ENV = "BILIBILI_WEBHOOK"


def phrase(status: str) -> str:
    return PHRASES.get(status, f"状态 {status}")


def notify(episode: str, status: str, title: str, package_dir: str,
           webhook: str | None = None) -> str:
    """写一条日志；配了 webhook 就再推一条。返回那句措辞。"""
    text = f"[B站] {episode} {phrase(status)}：{title}（{package_dir}）"
    print(text)
    if webhook:
        try:
            # Request 本身也会抛（webhook 写错成不是一个 URL 时），
            # 所以构造与发送要一起裹住。
            body = json.dumps({"msgtype": "text",
                               "text": {"content": text}}).encode("utf-8")
            request = urllib.request.Request(
                webhook, data=body,
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
        except Exception as error:   # noqa: BLE001
            # 通知失败不影响发布本身，但要让人看见。
            print(f"WARNING 通知推送失败：{error}")
    return text

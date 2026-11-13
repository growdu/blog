"""探测：把一个页面的结构 dump 出来。

**为什么需要它。** 视频号助手的投稿页长什么样，本仓库没见过；
靠猜选择器写流程，写出来的代码看着像那么回事，一跑就超时——
而且是「超时」这种最没信息量的失败。

所以先探测再写：跑一次 `probe`，把页面上所有能填、能点、能传文件的元素
连同**建议的 CSS 选择器**一起打出来，照着写选择器表。

探测只读页面，不点任何东西。
"""

from __future__ import annotations

import json
from pathlib import Path

# 一次把 DOM 里跟「填」「点」「传文件」有关的元素全捞出来。
# 故意把 a[href] 也带上：很多平台的提交按钮其实是 <a> 或 <span>。
_JS = r"""
() => {
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  };
  const attr = (el, name) => (el.getAttribute(name) || '').trim();
  const cssEscape = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : s;
  const suggest = (el) => {
    if (el.id) return '#' + cssEscape(el.id);
    const tag = el.tagName.toLowerCase();
    const ph = attr(el, 'placeholder');
    if (ph) return `${tag}[placeholder="${ph}"]`;
    const aria = attr(el, 'aria-label');
    if (aria) return `${tag}[aria-label="${aria}"]`;
    const name = attr(el, 'name');
    if (name) return `${tag}[name="${name}"]`;
    const type = attr(el, 'type');
    if (type) return `${tag}[type="${type}"]`;
    return tag;
  };
  const pick = (el) => ({
    tag: el.tagName.toLowerCase(),
    type: attr(el, 'type'),
    name: attr(el, 'name'),
    id: el.id || '',
    cls: (typeof el.className === 'string' ? el.className : '').trim(),
    placeholder: attr(el, 'placeholder'),
    aria: attr(el, 'aria-label'),
    title: attr(el, 'title'),
    role: attr(el, 'role'),
    accept: attr(el, 'accept'),
    href: attr(el, 'href'),
    contenteditable: attr(el, 'contenteditable'),
    text: ((el.innerText || '') + ' ' + (el.value || '')).trim().slice(0, 100),
    value: (el.value || '').slice(0, 100),
    visible: visible(el),
    suggested: suggest(el),
  });
  const selector = 'input, textarea, select, button, [contenteditable="true"], '
                + '[role="button"], [role="textbox"], a[href], label';
  return {
    url: location.href,
    title: document.title,
    frames: Array.from(document.querySelectorAll('iframe')).map((f) => ({
      src: f.src || '',
      id: f.id || '',
      cls: (typeof f.className === 'string' ? f.className : '').trim(),
    })),
    nodes: Array.from(document.querySelectorAll(selector)).map(pick),
  };
}
"""


def dump_structure(page) -> dict:
    """在 page 上执行探测脚本，返回结构化结果。

    **子 frame 也要探。** 视频号助手把登录二维码放在
    `open.weixin.qq.com` 的 iframe 里；投稿页的编辑器同样可能不在主文档里。
    只探主文档会漏掉真正要操作的那些元素。
    """
    dump = page.evaluate(_JS)
    frames = []
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            inner = frame.evaluate(_JS)
        except Exception:
            continue  # frame 正在导航／跨域，下一轮再试
        frames.append({
            "url": frame.url,
            "name": frame.name,
            "nodes": inner.get("nodes") or [],
        })
    dump["frame_nodes"] = frames
    return dump


def render_text(dump: dict, *, only_visible: bool = False) -> str:
    """把探测结果渲染成人能读的文本。"""
    lines: list[str] = []
    lines.append(f"URL   {dump.get('url')}")
    lines.append(f"标题  {dump.get('title')}")
    frames = dump.get("frames") or []
    if frames:
        lines.append("")
        lines.append("== iframe ==")
        for frame in frames:
            lines.append(f"  {frame.get('id') or '(无 id)'}  {frame.get('cls')}  {frame.get('src')}")
    lines.append("")
    lines.append("== 元素 ==")
    for node in dump.get("nodes") or []:
        lines.extend(_render_node(node, only_visible))
    for frame in dump.get("frame_nodes") or []:
        lines.append("")
        lines.append(f"== frame {frame.get('url')} ==")
        for node in frame.get("nodes") or []:
            lines.extend(_render_node(node, only_visible))
    return "\n".join(lines)


def _render_node(node: dict, only_visible: bool) -> list[str]:
    if only_visible and not node.get("visible"):
        return []
    bits = [node.get("tag") or "?"]
    for key in ("type", "name", "id", "cls", "placeholder", "aria", "role", "accept", "href"):
        value = node.get(key)
        if value:
            bits.append(f"{key}={value}")
    if node.get("contenteditable"):
        bits.append(f"contenteditable={node['contenteditable']}")
    if node.get("text"):
        bits.append(f"text={node['text']!r}")
    if not node.get("visible"):
        bits.append("(不可见)")
    return ["  " + "  ".join(bits), f"      → {node.get('suggested')}"]


def save(dump: dict, path: Path) -> Path:
    """把原始探测结果存成 JSON（给写选择器的人留证据）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# 判断「是不是已经进了后台」用的一组关键词。
# **这是启发式，不是判据。** 它的唯一用途是让人（和看日志的人）
# 知道该等还是该扫——真正的判据是页面结构本身。
LOGGED_IN_HINTS = ("发表视频", "发布视频", "内容管理", "发表动态", "首页")


def looks_logged_in(dump: dict) -> bool:
    """页面上有没有「已经登录进后台」的迹象。

    只用于**提示**，不用来放行任何写操作——判断错了顶多让人多等一会儿。
    """
    texts = [node.get("text") or "" for node in (dump.get("nodes") or [])]
    blob = " ".join(texts)
    return any(hint in blob for hint in LOGGED_IN_HINTS)


def summarize(dump: dict) -> str:
    """一行字的页面概览，给轮询时打印用。"""
    nodes = dump.get("nodes") or []
    visible = [n for n in nodes if n.get("visible")]
    files = [n for n in visible if n.get("type") == "file"]
    # 「输入框」不含文件框——文件框是另一个东西，混在一起数会让人以为少了一个
    boxes = [n for n in visible
             if n.get("tag") in ("input", "textarea") and n.get("type") != "file"]
    buttons = [n for n in visible if n.get("tag") == "button" or n.get("role") == "button"]
    state = "像是已进后台" if looks_logged_in(dump) else "像是还在登录页"
    return (f"{state}  url={dump.get('url')}  可见元素={len(visible)} "
            f"输入框={len(boxes)} 文件框={len(files)} 按钮={len(buttons)}")


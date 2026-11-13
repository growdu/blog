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
    """在 page 上执行探测脚本，返回结构化结果。"""
    return page.evaluate(_JS)


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
        if only_visible and not node.get("visible"):
            continue
        bits = [node.get("tag") or "?"]
        for key in ("type", "name", "id", "cls", "placeholder", "aria", "role", "accept"):
            value = node.get(key)
            if value:
                bits.append(f"{key}={value}")
        if node.get("contenteditable"):
            bits.append(f"contenteditable={node['contenteditable']}")
        if node.get("text"):
            bits.append(f"text={node['text']!r}")
        if not node.get("visible"):
            bits.append("(不可见)")
        lines.append("  " + "  ".join(bits))
        lines.append(f"      → {node.get('suggested')}")
    return "\n".join(lines)


def save(dump: dict, path: Path) -> Path:
    """把原始探测结果存成 JSON（给写选择器的人留证据）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

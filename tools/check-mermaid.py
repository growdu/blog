#!/usr/bin/env python3
"""量出站点里**渲染不出来**的 mermaid 图，并给出原因。

**为什么要有这个工具**：mermaid 解析失败的图在页面上不是报错，而是被
``layout.ejs`` 换成一行「⚠ 此图语法错误，未能渲染」——从页面截图上看，
那只是一块空白的提示框，不点开源码根本不知道原来画的是什么。
于是「图坏了」这件事在站点上一直是隐形的。

**怎么量的**：把构建产物 ``public/**/*.html`` 里所有
``<div class="mermaid">`` 的源码收集起来（去重），在一个 headless Chrome
里逐张调用 **站点自己用的那个** ``mermaid.render()``（不是 parse——
render 才是真正画出 SVG 的那条路径；parse 只查语法，查不出布局期的错误，
比如 gantt 的 ``Invalid date``）。渲不出来的就是坏图。

**怎么用**：

    npx hexo generate          # 先构建产物
    python3 tools/check-mermaid.py                # 报告（退出码 1 = 有坏图）
    python3 tools/check-mermaid.py --list         # 逐条列出（含所在页面）
    python3 tools/check-mermaid.py --json out.json

**依赖**：本机有 ``google-chrome``（或 ``chromium``）和 ``websocket-client``
（``pip install websocket-client``）。

CI 里暂时不跑它：GitHub 的 runner 自带 Chrome，但 1300 多张图要渲十分钟，
而部署那条 job 的超时预算是 20 分钟——hexo generate 自己就占了 9 分钟。
把检查放进 CI 之前，先把坏图清零（见 review/plans/2026-11-16-展示审计与优化方向.md 第七节）。
"""

from __future__ import annotations

import argparse
import functools
import html as htmllib
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.request
from collections import OrderedDict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.join(REPO, "public")

MERMAID_DIV = re.compile(r'<div class="mermaid"[^>]*>([\s\S]*?)</div>')


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def collect_sources(public_dir: str) -> OrderedDict:
    """收集产物里所有 mermaid 源码 -> 出现过的页面列表。"""
    sources: OrderedDict = OrderedDict()
    for root, _dirs, files in os.walk(public_dir):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(root, f)
            try:
                text = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in MERMAID_DIV.finditer(text):
                src = htmllib.unescape(m.group(1)).strip()
                sources.setdefault(src, []).append(os.path.relpath(path, public_dir))
    return sources


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def serve(directory: str):
    """把目录起在一个随机端口上，返回 (base_url, shutdown)。"""
    handler = functools.partial(QuietHandler, directory=directory)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return "http://127.0.0.1:%d" % port, httpd.shutdown


class Chrome:
    """一个 headless Chrome + 一条 CDP 连接。"""

    def __init__(self, port: int):
        self.port = port
        self.proc = None
        self.ws = None
        self._id = 0

    def __enter__(self):
        binary = find_chrome()
        if not binary:
            raise SystemExit(
                "找不到 Chrome（本机需要 google-chrome 或 chromium）。"
                "这个工具用 headless Chrome 跑站点自己的 mermaid。"
            )
        self.proc = subprocess.Popen(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--remote-debugging-port=%d" % self.port,
             "--user-data-dir=/tmp/check-mermaid-profile",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(4)
        import websocket  # 局部导入：没装就到这里才报错

        tabs = json.load(urllib.request.urlopen(
            "http://127.0.0.1:%d/json/list" % self.port))
        pages = [t for t in tabs if t.get("type") == "page"]
        if not pages:
            raise SystemExit("Chrome 起来了，但没有可用的标签页")
        # suppress_origin=True 是必须的：Chrome 会拒绝带 Origin 头的 websocket。
        self.ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=180, suppress_origin=True)
        self.cmd("Page.enable")
        self.cmd("Runtime.enable")
        return self

    def __exit__(self, *_exc):
        try:
            if self.ws:
                self.ws.close()
        finally:
            if self.proc:
                self.proc.terminate()

    def cmd(self, method, params=None):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method,
                                 "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                return msg.get("result")

    def eval(self, expr):
        res = self.cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        return (res or {}).get("result", {}).get("value")


def render_all(chrome: Chrome, sources: list[str], boot_url: str, timeout_s: int):
    """在页面里逐张 mermaid.render()。返回 (成功数, 失败列表)。"""
    chrome.cmd("Page.navigate", {"url": boot_url})
    # 「mermaid 到位了」必须验到 render 这个函数本身。
    #
    # 曾经的写法是 `if chrome.eval("typeof window.mermaid"):`——但 eval 回的
    # 是**字符串**，"undefined" 也是非空串，在 Python 里是真值，于是等待逻辑
    # 第一轮就「通过」了。mermaid 其实压根没加载（产物里缺 mermaid.min.js），
    # 工具照样往下跑，render 抛异常、循环卡死，最后报「渲染成功 0　渲染失败 0」——
    # 一份**假的全清**。缺图和坏图，长得一模一样。
    #
    # 所以这里要的是布尔，而且必须问到 render：
    # mermaid 没加载 / 加载了但没有 render / 版本不对，三种都算没到位。
    for _ in range(60):
        time.sleep(1)
        if chrome.eval(
            "(typeof window.mermaid === 'object' && window.mermaid !== null "
            "&& typeof window.mermaid.render === 'function')"
        ):
            break
    else:
        raise SystemExit(
            "mermaid 没加载起来——%s 打开后页面里应当有 .mermaid 容器，"
            "且 /lib/mermaid/mermaid.min.js 能下载到"
            "（产物里没有它？先跑 tools/copy-vendor.py 再 npx hexo generate）"
            % boot_url)

    boot = """(function(){
  window.__r = {done:false, ok:0, bad:[], settled:0};
  var list = %s;
  var i = 0;
  function one(){
    if (i >= list.length) { window.__r.done = true; return; }
    var src = list[i]; var idx = i; i++;
    /* 渲染本身可能同步抛异常（mermaid 内部对某些源码直接 throw 而不是
       reject）。不接住的话整个循环就断在这里，后面几千张图一张都不测，
       最后报「成功 0 失败 0」——又是一份假的全清。
       所以每张图的异常也算它自己的失败。 */
    try {
      window.mermaid.render('scan-' + idx, src).then(
        function(){ window.__r.ok++; window.__r.settled++; one(); },
        function(e){
          window.__r.bad.push({
            i: idx,
            msg: String((e && (e.message || e.str)) || e),
            head: src.slice(0, 240)
          });
          window.__r.settled++; one();
        });
    } catch (err) {
      window.__r.bad.push({
        i: idx,
        msg: '同步抛异常：' + String((err && (err.message || err.str)) || err),
        head: src.slice(0, 240)
      });
      window.__r.settled++; one();
    }
  }
  one();
  return 'started';
})()""" % json.dumps(sources)
    chrome.eval(boot)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(3)
        if chrome.eval("window.__r && window.__r.done"):
            break
    result = json.loads(chrome.eval("JSON.stringify(window.__r)"))
    # 没跑完就是没跑完：ok + bad 少于总数，说明剩下的图卡住了。
    # 这时候不能把已测的那部分当成结论——「测了一半」和「全测了」必须能分开。
    if not result.get("done") or result.get("settled", 0) < len(sources):
        raise SystemExit(
            "渲染没跑完：%d 张里只跑完 %d 张（超时 %d 秒）。"
            "这次的数字不作数——先查 mermaid 是不是真的加载上了。"
            % (len(sources), result.get("settled", 0), timeout_s))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="找出渲染不出来的 mermaid 图")
    ap.add_argument("--public", default=PUBLIC, help="产物目录（默认 public/）")
    ap.add_argument("--list", action="store_true", help="逐条列出坏图（含所在页面）")
    ap.add_argument("--filter", metavar="PREFIX", default="",
                    help="只列出页面路径以 PREFIX 开头的坏图")
    ap.add_argument("--json", metavar="FILE", help="把结果写成 JSON")
    ap.add_argument("--timeout", type=int, default=2400, help="渲染超时秒数（默认 2400）")
    args = ap.parse_args()

    if not os.path.isdir(args.public):
        raise SystemExit("没有产物目录 %s —— 先跑 npx hexo generate" % args.public)

    sources = collect_sources(args.public)
    if not sources:
        raise SystemExit("%s 里没找到任何 mermaid 图" % args.public)
    print("唯一 mermaid 源码数：%d" % len(sources), flush=True)

    # boot 页面必须走 http：mermaid 的 loader 写的是 /lib/mermaid/mermaid.min.js
    # （绝对路径），file:// 下会被解析到文件系统根目录，下载不到。
    base_url, shutdown = serve(args.public)
    try:
        first_page = next(iter(sources.values()))[0]
        boot = base_url + "/" + first_page.replace(os.sep, "/")
        with Chrome(9400) as chrome:
            result = render_all(chrome, list(sources.keys()), boot, args.timeout)
    finally:
        shutdown()

    bad = result["bad"]
    ok = result["ok"]
    print("渲染成功：%d　渲染失败：%d" % (ok, len(bad)))

    keys = list(sources.keys())
    records = []
    for item in bad:
        src = keys[item["i"]]
        records.append({
            "message": item["msg"],
            "source": src,
            "pages": sources[src],
        })

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"total": len(sources), "ok": ok, "bad": records},
                      fh, ensure_ascii=False, indent=2)
        print("结果已写到 %s" % args.json)

    if args.list:
        shown = 0
        for rec in records:
            pages = rec["pages"]
            if args.filter:
                pages = [p for p in pages if p.startswith(args.filter)]
                if not pages:
                    continue
            shown += 1
            print("--- %s" % rec["message"].split("\n")[0])
            print("    页面：%s" % ", ".join(pages[:3]))
            for line in rec["source"].split("\n")[:4]:
                print("    | %s" % line)
        print("共 %d 张坏图" % shown)

    return 1 if records else 0


if __name__ == "__main__":
    sys.exit(main())

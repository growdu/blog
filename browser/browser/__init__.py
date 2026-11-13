"""发布执行器：用 Playwright 驱动真实 Chromium 完成平台投稿。

这个包**不是 adapter**，是第三层：

    aiv/publish/<EP>.json ──┐
                             ├─→ browser/ ─→ 真实浏览器 ─→ 平台页面
    channels/out/<EP>/    ──┘

为什么单独一层。adapter 负责「这个平台的限额怎么裁、包怎么出」，
是平台知识；视频号与 B站各不相同，所以两个 adapter 互不引用
（见 publish/spec/07-视频发布契约.md §3.3）。而「点哪个按钮、往哪个框里填字」
也是平台知识，但它是**另一种**平台知识——浏览器交互知识——而且它不产生包，
只消费包。把它塞进 adapter 会让「出包」这件事必须装浏览器才能跑。

所以这里的分工是：

    adapter（channels/、bilibili/）  产出发布包，校验限额
    browser/                         打开真实浏览器，把包里的东西填进去
    状态快照（publish/outbox/）        两边共用的对外事实

**browser/ 不 import 任何 adapter。** 回填快照靠调用外部命令
（默认 `python -m channels.cli mark published`），不靠 import，
这样浏览器执行器可以给任意平台用，而不会把平台焊死在代码里。
"""

__all__ = ["__version__"]

__version__ = "0.1.0"

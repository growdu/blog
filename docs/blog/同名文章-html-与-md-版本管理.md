# 同名文章：HTML 与 MD 版本管理

仓库偶尔会出现 `xxx.md` 和 `xxx.html` 两个同主题、不同表达形式的源文件（一个 markdown 版、一个带丰富排版的 HTML 版）。本文说明 `sync-hexo.py` 处理这种情况的约定，**为什么必须**遵守，以及怎么做。

## TL;DR

> **同主题的 .html 文件名必须以 `-html` 后缀结尾**。
> 例：`foo.md` 的 HTML 版叫 `foo-html.html`（不是 `foo.html`）。
> `tools/sync-hexo.py` 会检测并强约束这个约定；不符合的提交会让 CI 构建失败。

## 现状

仓库里目前有 2 对同主题双版本（已统一改过名）：

| markdown 版 | HTML 版 |
|---|---|
| `docs/db/ddl同步架构.md` | `docs/db/ddl同步架构-html.html` |
| `docs/hometown/家中对联.md` | `docs/hometown/家中对联-html.html` |

另外有 1 个**独立** .html（无对应 .md），不受本约定约束：`docs/db/sqlserver/sqlserver逻辑复制ddl.html`。

## 为什么需要这个约定

### 1. 视觉区分

`docs/db/` 里 `ddl同步架构.md` 和 `ddl同步架构.html` 并排躺着，文件管理器一眼看上去是"两个不同文件"还是"同主题的两种格式"很模糊。改成 `ddl同步架构-html.html` 后，前缀和后缀都标明了"这是 HTML 版"，扫一眼目录就懂。

### 2. 避免 permalink 冲突

hexo 7 的 post 处理器会**强制用文件名作为 permalink 的 slug**（`node_modules/hexo/dist/plugins/processor/post.js` 第 49 行 `data.slug = info.title;`），无视 front matter 里的 `slug:` 字段。所以：

- `xxx.md` → `/blog/<日期>/xxx/`
- `xxx.html` → `/blog/<日期>/xxx/`

两个文件会**生成同一条 URL**，后写入的会覆盖前者，CI 不报错但内容莫名其妙。改名为 `xxx-html.html` 后：

- `xxx.md` → `/blog/<日期>/xxx/`
- `xxx-html.html` → `/blog/<日期>/xxx-html/`

URL 不再冲突，两个版本都可以正常访问。

### 3. 自动化检测

`sync-hexo.py` 在 CI 跑的时候，会扫描 `docs/` 下所有 `.html` 文件，**如果发现有 `.html` 缺 `-html` 后缀且存在同名 `.md`**，立刻打 ERROR 并以 exit code 2 退出，CI 构建失败：

```
ERROR docs/db/ddl同步架构.html: shares basename with docs/db/ddl同步架构.md
but is not suffixed with -html. Rename the .html file to
docs/db/ddl同步架构-html.html (see docs/blog/同名文章-html-与-md-版本管理.md).
```

宁可构建失败、让维护者收到 GitHub Actions 红色 ❌，也不要静默生成两条相同 URL 的文章。

## 新增一篇文章的两种写法

### 写法 A：纯 markdown（最常见）

```bash
# docs/<分类>/<文章名>.md
docs/db/ddl同步架构.md
```

文章正文用 markdown 写，front matter 可选（`sync-hexo.py` 会自动补 title/date/categories/tags）。

### 写法 B：纯 HTML（需要保留富排版）

当一篇文章里有大量 `<table>` / `<div class="mermaid">` / 自定义 CSS 样式时，markdown 写起来很别扭，直接写 HTML 更顺手：

```bash
# docs/<分类>/<文章名>.html
docs/db/sqlserver/sqlserver逻辑复制ddl.html
```

要求：
- 文件首行有 `<title>标题</title>` 标签（`sync-hexo.py` 会提取做 front matter 的 `title`，并从正文里删除这个标签避免重复渲染）
- 形如 `/blog/images/xxx.png` 的图片用绝对路径引用；或者把图片放在 HTML 同目录下用相对路径

### 写法 C：同主题两个版本（本文重点）

同一个主题，markdown 版简洁、HTML 版带丰富排版/图表。**两文件都存在**的场景：

```bash
docs/db/
├── ddl同步架构.md              # markdown 简版
└── ddl同步架构-html.html       # HTML 富版（必须带 -html 后缀）
```

**不要**这样：

```bash
docs/db/
├── ddl同步架构.md
└── ddl同步架构.html       # ❌ 缺 -html 后缀，CI 失败
```

**也不要**这样（试图用 `slug:` 字段解决 URL 冲突）：

```yaml
# ddl同步架构.html
---
title: 同步架构
slug: ddl-html     # ❌ hexo 7 忽略 slug，仍然用文件名
---
```

`slug:` 字段在 hexo 7 被强制覆盖为文件名，**别浪费时间**。

## 修复违规

如果收到 CI 的 ERROR 提示，按以下步骤修复：

```bash
# 把 xxx.html 改名为 xxx-html.html（保留 git 历史）
git mv docs/<分类>/xxx.html docs/<分类>/xxx-html.html

git add docs/<分类>/xxx-html.html
git commit -m "rename: xxx.html -> xxx-html.html per naming convention"
git push origin master
```

不需要再改 .md，也不需要改 front matter。`sync-hexo.py` 检测到 `-html` 后缀会**保留原文件名**直接输出到 `source/_posts/<分类>/xxx-html.html`，hexo 渲染后 permalink 形如 `/blog/2024/01/01/xxx-html/`。

## 边界情况

### 1. `index.html` / `index.htm`

`index.html` 是 page bundle（页面捆绑）约定，`sync-hexo.py` 会跳过（不当作普通文章处理）。如果你在 `docs/<分类>/<文章名>/index.html` 写了 HTML 版，**不需要加 `-html` 后缀**——目录本身就是 disambiguator。

### 2. `_index.html`

`docs/<分类>/_index.html` 是分类页/项目页入口，由 `sync-hexo.py` 显式跳过（`process_html` 第 222-224 行）。本约定不适用。

### 3. 独立 HTML（无对应 .md）

像 `docs/db/sqlserver/sqlserver逻辑复制ddl.html` 这种没有同名 .md 的 .html，**不强制**加 `-html` 后缀（加了也无害，但没意义）。本约定只约束"一对双版本"的场景。

### 4. 内容冲突 / 哪一个优先

hexo 不会合并两份内容，它们各有自己的 permalink。文章列表里会按 `date` 排序（markdown 版的 date 来自 git log，HTML 版也来自 git log），不会出现"覆盖"的情况。

## FAQ

### Q: 我能不能给 .html 加别的后缀，比如 `xxx-formatted.html` 或 `xxx-rich.html`？

不能。`sync-hexo.py` 只检测 `-html` 后缀，其它后缀会被视为违规。统一后缀让脚本逻辑简单、命名一致。

### Q: 我能不能把 .html 放进 `xxx-html/index.html` 子目录？

技术上可以（page bundle），但这会变成"独立 HTML"场景，不再有配对的 .md。子目录结构和"双版本并列"在语义上不同，不要混用。

### Q: 已经 commit 的违规 .html 怎么补救？

按"修复违规"那节的 `git mv` 步骤走。git 会识别为 rename，diff 是干净的。

### Q: front matter 里 `title` 相同会冲突吗？

不会。`title` 只影响文章页的 `<h1>` 和 `<title>` 标签，permalink 走文件名 slug。两篇文章 `title` 一样是允许的（"markdown 版" / "HTML 版" 加在正文里区分即可）。

### Q: 搜索框/标签云会同时显示两篇吗？

会。这是预期行为——它们是同主题的两个版本，用户按需选读。tag/category 列表会按 title 排序显示两次。

## 参考

- 实际迁移 commit：见 git log `git log --diff-filter=R -- docs/`
- 违规检测代码：`tools/sync-hexo.py` 第 478-499 行
- permalink 来源：hexo 7 的 `node_modules/hexo/dist/plugins/processor/post.js:49`（`data.slug = info.title;` 强制用文件名）

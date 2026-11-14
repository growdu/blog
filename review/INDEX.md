# 审校进度索引

审校范围：`docs/` 全树（621 篇）里**面向读者的技术文章**（426 篇）。
非内容（站点目录页、代码仓库说明、内部工作文档、外链指北、只有标题的未成稿）
连同速查/清单/操作类、非技术内容共 195 篇已排除——分类与逐篇清单见
[`scope/2026-11-14-scope-classification.md`](scope/2026-11-14-scope-classification.md)。

规范见 [`README.md`](README.md)，落地机制见
[`specs/2026-11-13-content-review-design.md`](specs/2026-11-13-content-review-design.md)，
实现计划见 [`plans/2026-11-13-content-review.md`](plans/2026-11-13-content-review.md)。

## 怎么读这张表

| 列 | 含义 |
| --- | --- |
| 记录 | 审校记录；点进去是逐条建议 |
| 支柱 | `docs/` 下的一级目录 |
| 状态 | 待审 → 审校中 → 建议中 → 已确认 → 已合入 |
| 信号 | 检查器给出的 warn 级信号条数（0~19，是「命中了几条规则」） |
| 待确认 | 「事实待核」里还没销掉的条目数——状态为「已合入」时必须是 0 |
| 不阻塞 | 标了「不适用」的条目数：事实本身还没核实，但本次改动没碰它，不卡合并 |
| 批次 | 试点 / 1 / 2 … |

**信号为 0 不等于文章没问题**——检查器只出机械信号，技术深度、定位、语气这类
判断是人工做的，机械信号干净的文章照样可能需要改。

## 进度

已审 5 篇，全部来自首批试点（数据库内核四支柱）。范围扩到全树后，
按信号密度排序继续——排序依据见范围分类文档的「逐支柱分布」。

| 记录 | 支柱 | 状态 | 信号 | 待确认 | 不阻塞 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| [postgresql-mvcc](database/postgresql-mvcc.md) | database | 已合入 | 0 | 0 | 1 | 试点 |
| [postgresql-logical-replication-worker-model](database/postgresql-logical-replication-worker-model.md) | database | 已合入 | 0 | 0 | 1 | 试点 |
| [06-heap-and-mvcc](db/postgresql/learning-path/06-heap-and-mvcc.md) | db | 已合入 | 0 | 0 | 2 | 试点 |
| [checkpoint机制浅析](pgsql/checkpoint机制浅析.md) | pgsql | 已合入 | 0 | 0 | 0 | 试点 |
| [分布式一致性协议](cluster/分布式一致性协议.md) | cluster | 已合入 | 0 | 0 | 2 | 试点 |

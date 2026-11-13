# 审校进度索引

首轮范围：`docs/` 数据库内核四支柱（`database` / `db` / `pgsql` / `cluster`，282 篇）。
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
| 待确认 | 「事实待核」里还没销掉的条目数 |
| 批次 | 试点 / 1 / 2 … |

**信号为 0 不等于文章没问题**——检查器只出机械信号，技术深度、定位、语气这类
判断是人工做的，机械信号干净的文章照样可能需要改。

## 进度

| 记录 | 支柱 | 状态 | 信号 | 待确认 | 批次 |
| --- | --- | --- | --- | --- | --- |
| [postgresql-mvcc](database/postgresql-mvcc.md) | database | 建议中 | 0 | 5 | 试点 |
| [postgresql-logical-replication-worker-model](database/postgresql-logical-replication-worker-model.md) | database | 建议中 | 0 | 5 | 试点 |
| [06-heap-and-mvcc](db/postgresql/learning-path/06-heap-and-mvcc.md) | db | 建议中 | 0 | 5 | 试点 |
| [checkpoint机制浅析](pgsql/checkpoint机制浅析.md) | pgsql | 建议中 | 1 | 5 | 试点 |

# Mermaid 图表语法错误清单

> 由 `mermaid@10.9.8` 的解析器实测生成：把 `docs/` 下每个 ` ```mermaid ` 块喂给
> `mermaid.parse()`，记录抛错的那些块。`source/_posts/` 由 `tools/sync-hexo.py` 从
> `docs/` 生成，因此本清单的**行号以 `docs/` 下的源文件为准**。

- 总图表数：**1239**
- 解析失败：**102**（8.2%）
- 受影响页面：**58**

## 根因速查

| 现象 | 原因 | 修法 |
|---|---|---|
| `A[文字]::: class` | mermaid v10 的类名与 `:::` 之间**不允许空格** | 写成 `A[文字]:::class` |
| `A[文字 (含括号)]` | 未加引号的标签里出现 `(` `)` `:` `;` `,` `"` | 给标签加双引号：`A["文字 (含括号)"]` |
| `--> [多词标签]` | 箭头后面直接跟带空格的匿名节点 | 给它一个 ID：`--> B[多词标签]` |
| `-- 文本 -->` / `-. 文本 .->` | 点线/虚线边上的文字含 `:` 等符号 | 用引号包住：`-. "文本" .->` |
| `-->|"文字"<br/>更多` | 引号闭合后又跟了 `<br/>` | 把 `<br/>` 挪进引号内 |
| `mindmap` 节点含 `:` `(` | mindmap 语法比 flowchart 严格得多 | 改用缩进层级，去掉标点 |
| `grpah` | 拼写错误 | 改成 `graph` |

## 明细

### docs/ai/19_AI是你的杠杆普通人也能用的AI实战教程.md

- **第 459 行**（块 #0，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[你懂 / 会做]::: root --> B[重复的部分]::: warm --> C[交给 AI]::: hot --> D[10x 效率]::: hot
  ```

- **第 482 行**（块 #1，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[你的独特经验]::: root --> B[结构化 / SOP / 知识库]::: warm --> C[通过 AI 分发]::: hot --> D[无限次复用]::: hot
  ```

- **第 674 行**（块 #2，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[你现在的处境]::: root --> B{你的时间紧迫?}
  ```

### docs/database/citus-columnar-deep-dive/index.md

- **第 161 行**（块 #3，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/citus-deep-dive/index.md

- **第 53 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/cstore-fdw-deep-dive/index.md

- **第 39 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 203 行**（块 #4，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pg-duckdb-deep-dive/index.md

- **第 44 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pg-stat-statements-deep-dive/index.md

- **第 26 行**（块 #0，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 53 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 281 行**（块 #4，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pgaudit-deep-dive/index.md

- **第 26 行**（块 #0，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pgbackrest-deep-dive/index.md

- **第 44 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pgcrypto-deep-dive/index.md

- **第 25 行**（块 #0，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 44 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/pgvector-deep-dive/index.md

- **第 50 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/postgis-deep-dive/index.md

- **第 244 行**（块 #8，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 535 行**（块 #15，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/database/postgresql-core-features/index.md

- **第 131 行**（块 #3，类型 `flowchart`，报错在块内第 7 行）

  ```
  C -.->|"10 逻辑复制 / 12 可插拔 AM 是“跨架构”"]
  ```

- **第 809 行**（块 #24，类型 `flowchart`，报错在块内第 2 行）

  ```
  A["文档 text"] --> "tsvector (to_tsvector)"
  ```

- **第 967 行**（块 #28，类型 `quadrantChart`，报错在块内第 3 行）

  ```
  x-axis "接近 SQL" vs "接近业务"
  ```

### docs/database/postgresql-history/index.md

- **第 586 行**（块 #14，类型 `mindmap`，报错在块内第 9 行）

  ```
  商业 PG (EDB / RedHat) 同步更新
  ```

- **第 771 行**（块 #19，类型 `flowchart`，报错在块内第 9 行）

  ```
  C -.->"提交评审"| G
  ```

### docs/database/postgresql-latch-mechanism/index.md

- **第 1084 行**（块 #3，类型 `sequenceDiagram`，报错在块内第 11 行）

  ```
  - 内核把 SIGURG 投到 B 的 signalfd
  ```

- **第 1112 行**（块 #4，类型 `sequenceDiagram`，报错在块内第 3 行）

  ```
  procSendSignal::procSendSignal as 目标进程
  ```

### docs/database/postgresql-logical-replication-ddl-trigger-apply-worker/index.md

- **第 646 行**（块 #4，类型 `sequenceDiagram`，报错在块内第 10 行）

  ```
  Pub->>HookPub: BEGIN; CREATE TABLE orders ...; CREATE TABLE orders_p1 PARTITION OF ...; ALTER PUBLICATION pub_orders ADD TABLE orders; COMMIT;
  ```

### docs/database/postgresql-logical-replication-end-to-end-flow/index.md

- **第 56 行**（块 #0，类型 `flowchart`，报错在块内第 8 行）

  ```
  A -->|"落盘到 subscriber 的 pg_wal/0000..."]
  ```

### docs/database/postgresql-logical-replication-monitoring/index.md

- **第 422 行**（块 #3，类型 `flowchart`，报错在块内第 12 行）

  ```
  F1[pg_wal_lsn_diff(lsn_a, lsn_b)<br/>+ pg_size_pretty<br/>÷ EXTRACT(EPOCH)]:::calc
  ```

### docs/database/postgresql-logical-replication-reorderbuffer-transaction/index.md

- **第 381 行**（块 #4，类型 `stateDiagram-v2`，报错在块内第 2 行）

  ```
  [*] --> BORN : 第一次见到 xid / ReorderBufferTXNByXid(create=true) / reorderbuffer.c:652
  ```

- **第 504 行**（块 #5，类型 `flowchart`，报错在块内第 3 行）

  ```
  Q1{rbtxn_is_streamed<br/>(RBTXN_IS_STREAMED)?}
  ```

- **第 629 行**（块 #6，类型 `flowchart`，报错在块内第 5 行）

  ```
  D["final_lsn<br/>(commit/abort LSN)"]:::end
  ```

### docs/database/postgresql-logical-replication-streaming-spill/index.md

- **第 823 行**（块 #7，类型 `flowchart`，报错在块内第 3 行）

  ```
  Q1 -- Publisher --> P1[改 ReorderBufferXXX (reorderbuffer.c)]
  ```

- **第 872 行**（块 #8，类型 `flowchart`，报错在块内第 4 行）

  ```
  pub1 --> pub2{streaming + |
  ```

### docs/database/postgresql-logical-replication-tables-lifecycle/index.md

- **第 599 行**（块 #4，类型 `flowchart`，报错在块内第 6 行）

  ```
  subgraph workers[共享内存 workers[] (max_logical_replication_workers 个槽)]
  ```

- **第 652 行**（块 #5，类型 `erDiagram`，报错在块内第 29 行）

  ```
  name subslotname FK-to-pg_replication_slots
  ```

- **第 1000 行**（块 #7，类型 `flowchart`，报错在块内第 9 行）

  ```
  B3 -.FK srsubid-> B4
  ```

### docs/database/postgresql-logical-replication-worker-model/index.md

- **第 125 行**（块 #1，类型 `stateDiagram-v2`，报错在块内第 4 行）

  ```
  STARTING --> CONNECTING : run_apply_worker(): walrcv_connect
  ```

### docs/database/postgresql-partition-handling/index.md

- **第 868 行**（块 #5，类型 `sequenceDiagram`，报错在块内第 29 行）

  ```
  
  ```

### docs/database/postgresql-rangevar-and-data-structures/index.md

- **第 672 行**（块 #9，类型 `graph`，报错在块内第 17 行）

  ```
  D1[pgoutput plugin] --> D2[OpenTable<br/>(RangeVar 重新构造)]
  ```

### docs/database/postgresql-row-lock-deep-dive/index.md

- **第 308 行**（块 #4，类型 `graph`，报错在块内第 12 行）

  ```
  D -.锁住不允许任何写修改。-> UB[修改 key / DELETE]
  ```

### docs/database/postgresql-running-xacts-snapshot/index.md

- **第 233 行**（块 #4，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

- **第 1569 行**（块 #26，类型 `flowchart`，报错在块内第 8 行）

  ```
  G["7. txn->base_snapshot 是 ReorderBuffer 视角的"事务能否发送"开关<br/>(NULL → 不发;非 NULL → 以 base_snapshot 为模板拼 snapshot_now)"]
  ```

### docs/database/postgresql-senior-kernel-developer/index.md

- **第 482 行**（块 #7，类型 `graph`，报错在块内第 2 行）

  ```
  SQL[SQL]:::parser-->[expr tree]:::parser
  ```

- **第 561 行**（块 #9，类型 `graph`，报错在块内第 6 行）

  ```
  E --> F[Query<br/>(RTE + Expr)]
  ```

- **第 645 行**（块 #11，类型 `graph`，报错在块内第 3 行）

  ```
  B --> C[PlanState<br/>(递归)]
  ```

### docs/database/postgresql-toast-deep-dive/index.md

- **第 77 行**（块 #0，类型 `graph`，报错在块内第 5 行）

  ```
  B3 --> C[Heap page<br/>(8KB 内)]
  ```

- **第 1316 行**（块 #12，类型 `graph`，报错在块内第 2 行）

  ```
  A[SELECT substr(text, 1000, 100)]:::input --> B["detoast_attr_slice<br/>@ detoast.c"]
  ```

### docs/database/timescaledb-deep-dive/index.md

- **第 52 行**（块 #1，类型 `mindmap`，报错在块内第 ? 行）

  ```
  mindmap
  ```

### docs/db/benchmarksql/benchmarksql使用教程.md

- **第 602 行**（块 #5，类型 `quadrantChart`，报错在块内第 3 行）

  ```
  x-axis 低延迟 --> 高延迟
  ```

### docs/db/logical_decode/logical_parallel_apply/逻辑复制并行apply依赖冲突检测设计文档.md

- **第 346 行**（块 #12，类型 `flowchart`，报错在块内第 2 行）

  ```
  A["T0 outside window<br/>write R.K=5"]::: out
  ```

### docs/db/logical_decode/logical_parallel_apply/逻辑复制并行apply接口文档.md

- **第 52 行**（块 #0，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[Logical Replication]::: root --> B["Serial Apply<br/>单事务"]
  ```

- **第 74 行**（块 #1，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[大量小事务]::: root --> B[串行 apply] --> C[CPU 利用率低] --> D[Subscriber 瓶颈]
  ```

- **第 217 行**（块 #3，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[已提交事务 1..N]::: in --> B[Transaction Window]
  ```

### docs/db/logical_decode/logical_parallel_apply/逻辑复制并行apply概要设计文档.md

- **第 55 行**（块 #0，类型 `flowchart`，报错在块内第 3 行）

  ```
  WAL[WAL]::: pub --> DEC[Logical Decoding]::: pub
  ```

- **第 118 行**（块 #1，类型 `flowchart`，报错在块内第 2 行）

  ```
  A["streaming=parallel<br/>单事务内"]::: root --> B[Parallel Apply Worker]::: root
  ```

- **第 276 行**（块 #5，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[T1 已 commit]::: old --> B[T2 在 window 1]::: cur
  ```

- **第 330 行**（块 #8，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[Tx1]::: n --> C[Tx3]
  ```

- **第 427 行**（块 #12，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[一条事务]::: root --> B{事务大小}
  ```

### docs/db/logical_decode/逻辑复制源码分析.md

- **第 841 行**（块 #1，类型 `graph`，报错在块内第 2 行）

  ```
  XLogSendLogical-->XLogReadRecord-->LogicalDecodingProcessRecord-->｜非级联｜GetFlushRecPtr
  ```

- **第 1667 行**（块 #11，类型 `grpah`，报错在块内第 ? 行）

  ```
  grpah TB
  ```

### docs/db/performance/flame-graph-analysis/index.md

- **第 526 行**（块 #19，类型 `flowchart`，报错在块内第 2 行）

  ```
  A["A 函数 30%"] -->|?"调用"| B["B 函数 25%"]
  ```

### docs/db/postgresql/learning-path/08-locks-and-concurrency.md

- **第 964 行**（块 #3，类型 `graph`，报错在块内第 2 行）

  ```
  T1[事务 A<br/>持: lock(id=1)<br/>等: lock(id=2)]
  ```

### docs/db/postgresql/learning-path/10-advanced-topics.md

- **第 429 行**（块 #1，类型 `graph`，报错在块内第 10 行）

  ```
  TQ[1["TupleQueue<br/>(tqueue.c)"]
  ```

### docs/db/postgresql/learning-path/12-physical-replication.md

- **第 461 行**（块 #2，类型 `stateDiagram-v2`，报错在块内第 23 行）

  ```
  Reserved --> Dropped: pg_drop_replication_slot
  ```

### docs/db/postgresql/learning-path/13-logical-replication.md

- **第 2319 行**（块 #22，类型 `graph`，报错在块内第 17 行）

  ```
  CAT -.->|按 (xmin, xmax) 过滤| CD
  ```

- **第 2511 行**（块 #29，类型 `sequenceDiagram`，报错在块内第 7 行）

  ```
  P->>WS: BEGIN; long running txn
  ```

### docs/db/postgresql/pgoutput_change到HeapTupleSatisfiesVisibility调用栈分析/index.md

- **第 507 行**（块 #8，类型 `flowchart`，报错在块内第 4 行）

  ```
  C --> D{snapbuild.c}<br/>Commit 到达 xmin/xmax 边界?
  ```

### docs/db/postgresql/postgresql-apply-leader-worker-code-analysis/index.md

- **第 58 行**（块 #0，类型 `flowchart`，报错在块内第 12 行）

  ```
  PA -. "设置: shared->xact_state / fileset_state ..." --> LA
  ```

### docs/db/postgresql/postgresql-apply-parallel-lock-stream/index.md

- **第 117 行**（块 #1，类型 `sequenceDiagram`，报错在块内第 15 行）

  ```
  style LA fill:#fee2e2,stroke:#dc2626,color:#000
  ```

- **第 409 行**（块 #9，类型 `flowchart`，报错在块内第 2 行）

  ```
  LA[LA 等 PA-2 完成] -->|LA 拿 AccessShare<br/>(等 PA-2 释放 XACT lock)| P2[PA-2 持 Exclusive]
  ```

### docs/db/postgresql/postgresql-apply-parallel-worker-code-analysis/index.md

- **第 751 行**（块 #9，类型 `sequenceDiagram`，报错在块内第 11 行）

  ```
  Pub->>RB: BEGIN; INSERT ... x N
  ```

### docs/db/postgresql/postgresql-apply-parallel-worker/index.md

- **第 39 行**（块 #0，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[publisher 大事务<br/>10 万条 INSERT]::: root --> B[WAL stream]
  ```

- **第 70 行**（块 #1，类型 `flowchart`，报错在块内第 3 行）

  ```
  WAL[WAL 流]::: pub
  ```

- **第 581 行**（块 #8，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[ParallelApplyWorkerPool<br/>HTAB]::: root --> B{key = xid}
  ```

### docs/db/postgresql/postgresql-create-replication-slot-deep-dive/index.md

- **第 164 行**（块 #1，类型 `flowchart`，报错在块内第 6 行）

  ```
  E --> F[构造 (slot_name, lsn) 元组]
  ```

- **第 1132 行**（块 #7，类型 `flowchart`，报错在块内第 5 行）

  ```
  D --> E[LoadOutputPlugin 加载 plugin<br/>(fast_forward 时跳过)]
  ```

### docs/db/postgresql/postgresql-injection-points-test-unreachable/index.md

- **第 411 行**（块 #4，类型 `sequenceDiagram`，报错在块内第 6 行）

  ```
  Test->>GIN: BEGIN; INSERT INTO gin_index ...
  ```

### docs/db/postgresql/postgresql-logical-replication-add-guc/index.md

- **第 124 行**（块 #2，类型 `flowchart`，报错在块内第 9 行）

  ```
  D1 --> E1[需要 pg_reload_conf() 才会生效]:::sighupapply
  ```

### docs/db/postgresql/postgresql-logical-replication-apply-parallel-tuning/index.md

- **第 370 行**（块 #4，类型 `flowchart`，报错在块内第 13 行）

  ```
  Launch -->|否| Serial[退回 LA 自己 apply<br/>(不并行)]
  ```

### docs/db/postgresql/postgresql-logical-replication-catalog-visibility/index.md

- **第 407 行**（块 #1，类型 `flowchart`，报错在块内第 6 行）

  ```
  D --是--> D1[needs_snapshot=true<br/>AddCommitted<br/>xmax = max(xmax, subxid)]
  ```

- **第 799 行**（块 #3，类型 `sequenceDiagram`，报错在块内第 13 行）

  ```
  RB->>RB: 取/建 stub txn;txn_flags |= RBTXN_HAS_CATALOG_CHANGES
  ```

- **第 842 行**（块 #4，类型 `flowchart`，报错在块内第 10 行）

  ```
  G --> H{txn.xid == xid(本次提交者)?}
  ```

### docs/db/postgresql/postgresql-logical-replication-end-to-end/index.md

- **第 751 行**（块 #11，类型 `sequenceDiagram`，报错在块内第 25 行）

  ```
  R->>DB: UPDATE t SET val=100 WHERE id=1<br/>(或:<br/> DELETE WHERE id=1;<br/> INSERT (1, 100);<br/>如果表无主键)
  ```

### docs/db/postgresql/postgresql-logical-replication-lsn-flow/index.md

- **第 628 行**（块 #3，类型 `sequenceDiagram`，报错在块内第 51 行）

  ```
  WK->>SubDB: BEGIN; UPDATE t SET val=100 WHERE id=1; COMMIT
  ```

### docs/db/postgresql/postgresql-logical-replication-stream-publisher/index.md

- **第 162 行**（块 #1，类型 `sequenceDiagram`，报错在块内第 7 行）

  ```
  plugin_plugin as logical.proto
  ```

- **第 876 行**（块 #5，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[一条 INSERT t(1, 'a')] --> B[约 30-100 字节]
  ```

### docs/db/postgresql/postgresql-reorder-buffer-code-analysis/index.md

- **第 25 行**（块 #0，类型 `flowchart`，报错在块内第 2 行）

  ```
  WAL[WAL Record<br>(heap/heap2/xlog)]:::wal
  ```

- **第 461 行**（块 #5，类型 `flowchart`，报错在块内第 18 行）

  ```
  End["ReorderBufferCleanupTXN"]:::end
  ```

- **第 545 行**（块 #6，类型 `flowchart`，报错在块内第 11 行）

  ```
  Done["退出循环"]:::end
  ```

### docs/db/postgresql/postgresql-reorderbuffer-c-function-reference/index.md

- **第 225 行**（块 #1，类型 `flowchart`，报错在块内第 34 行）

  ```
  IN -->|"使用 ReorderBufferChange"|  PY[output plugin]
  ```

### docs/db/postgresql/postgresql-row-lock/index.md

- **第 108 行**（块 #1，类型 `flowchart`，报错在块内第 10 行）

  ```
  H1 --> C1[""]:::excl
  ```

### docs/db/postgresql/postgresql-snapbuild-deep-dive/index.md

- **第 68 行**（块 #0，类型 `flowchart`，报错在块内第 9 行）

  ```
  S1[只跟踪"已提交且改 catalog"的 xid]
  ```

- **第 434 行**（块 #5，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[SnapBuildBuildSnapshot] --> B[计算 ssize:<br/>sizeof SnapshotData + xcnt*sizeof(Xid) + 1*toplevel Xid]
  ```

- **第 479 行**（块 #6，类型 `flowchart`，报错在块内第 12 行）

  ```
  H --> I[构造"反向"快照<br/>SnapBuildBuildSnapshot]
  ```

- **第 679 行**（块 #10，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[SnapBuildCommitTxn] --> B{state == START OR<br/>(BUILDING_SNAPSHOT && xid &lt; next_phase_at)?}
  ```

- **第 1092 行**（块 #17，类型 `flowchart`，报错在块内第 16 行）

  ```
  M -->|是| O[lsn = hi &lt;&lt; 32 | lo]
  ```

- **第 1146 行**（块 #18，类型 `sequenceDiagram`，报错在块内第 28 行）

  ```
  Note over SB: 此时 xid 起点 &gt;= FULL_SNAPSHOT<br/>的 next_phase_at 的事务可解码
  ```

- **第 1239 行**（块 #19，类型 `sequenceDiagram`，报错在块内第 9 行）

  ```
  Note over SB: state &lt; CONSISTENT<br/>走 restore 路径
  ```

- **第 1317 行**（块 #22，类型 `sequenceDiagram`，报错在块内第 17 行）

  ```
  SB->>SB: state &lt; CONSISTENT
  ```

### docs/db/postgresql/postgresql-snapbuild-find-snapshot-deep-dive/index.md

- **第 78 行**（块 #0，类型 `flowchart`，报错在块内第 2 行）

  ```
  A[DecodingContextFindStartpoint<br/>(logical.c:635)] --> B[XLogReadRecord]
  ```

### docs/linux/cpu-affinity-top-guide/index.md

- **第 89 行**（块 #3，类型 `flowchart`，报错在块内第 5 行）

  ```
  C0 --> S0["SMT Thread 0"]
  ```

### docs/pgsql/postgresql启动流程.md

- **第 17 行**（块 #0，类型 `graph`，报错在块内第 4 行）

  ```
  
  ```

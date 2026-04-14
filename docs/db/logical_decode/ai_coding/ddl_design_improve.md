# 逻辑复制DDL支持详细设计方案

## 设计背景与目标

逻辑复制当前仅支持同步DML操作。为了提升用户使用体验和增强逻辑复制功能，需要扩展支持DDL（数据定义语言）的自动同步。

## 需求概述

### Publication语法扩展

**原有接口：**
```sql
CREATE PUBLICATION name
    [ FOR ALL TABLES
      | FOR publication_object [, ...] ]
    [ WITH ( publication_parameter [= value] [, ... ] ) ]

where publication_object is one of:

    TABLE table_and_columns [, ...]
    TABLES IN SCHEMA { schema_name | CURRENT_SCHEMA } [, ...]
```

**扩展后接口：**
```sql
CREATE PUBLICATION name
    [ FOR ALL TABLES
      | FOR publication_object [, ...] ]
    [ WITH ( publication_parameter [= value] [, ... ], ddl [ = value] [, ...]) ]
```

**ddl选项取值范围：**
- `table` - 表结构变更
- `index` - 索引变更
- `type` - 类型变更
- `function` - 函数变更
- `domain` - 域变更
- `trigger` - 触发器变更
- `view` - 视图变更
- `rule` - 规则变更
- `schema` - 模式变更
- `extension` - 扩展变更
- `all` - 所有DDL类型
- `manual` - 手动同步DDL

### Subscription语法扩展

**原有接口：**
```sql
CREATE SUBSCRIPTION subscription_name
    CONNECTION 'conninfo'
    PUBLICATION publication_name [, ...]
    [ WITH ( subscription_parameter [= value] [, ... ] ) ]
```

**扩展后接口：**
```sql
CREATE SUBSCRIPTION subscription_name
    CONNECTION 'conninfo'
    PUBLICATION publication_name [, ...]
    [ WITH ( subscription_parameter [= value] [, ... ], ddl [ = value] [, ... ] ) ]
```

## 关键设计决策

### 1. DDL选项限制规则

**严格类型限制策略：**
- `FOR TABLE`或`FOR TABLES IN SCHEMA` publication：**只允许** `table` 和 `index` 类型
- 如果用户尝试指定其他类型（function, domain, trigger, view, rule, schema, extension, all），**直接报错**
- `FOR ALL TABLES` publication：允许所有DDL类型

**设计理由：**
- 确保语义清晰，避免用户误解
- 防止不匹配的DDL类型被忽略而产生意外行为
- 与现有逻辑复制范围概念保持一致

### 2. manual选项实现

**手动同步函数：**
```sql
-- 为manual选项提供的同步函数
SELECT pg_sync_ddl('ddl语句');
```

**实现要求：**
1. `manual`选项表示DDL不会自动同步
2. 用户必须显式调用`pg_sync_ddl()`函数触发同步
3. 函数应返回同步的记录数量或状态信息
4. 支持事务上下文中的调用

执行上面的函数后需要把ddl语句直接同步到订阅端。（暂不实现，ddl可不支持manual选项）

### 3. 系统表详细设计

#### pg_publication_sync表定义

```sql
CREATE TABLE pg_catalog.pg_publication_sync (
    lsn pg_lsn NOT NULL,                    -- 写入记录时的LSN位置，用于顺序保证和清理
    timestamp timestamptz NOT NULL DEFAULT now(),  -- 事件发生时间
    message_type char(1) NOT NULL,          -- 消息类型: 'A'新增, 'D'删除, 'Q'DDL SQL
    message_data text,                      -- 事件详细信息
    namespace text,                         -- 当前search_path，格式如"[mynsp,public,pg_catalog]"
    publication text[] NOT NULL,            -- publication名称数组
    message_extra json                      -- 额外信息，JSON格式
);
```

#### 字段详细说明

1. **lsn** (pg_lsn)
   - 主键组成部分
   - 用于确保DDL消息的全局顺序
   - 支持基于LSN的清理机制

2. **message_type** (char(1))
   - 'Q': DDL SQL消息（所有DDL语句）
   - 'A': 新增对象消息（表被添加到publication）
   - 'D': 删除对象消息（表从publication移除）

3. **message_data** (text)
   - 对于'Q'类型：存储原始DDL SQL语句
   - 对于'A'/'D'类型：JSON格式的对象信息，如`{"schema": "public", "table": "users"}`

4. **namespace** (text)
   - 存储执行DDL时的search_path
   - 用于在订阅端还原执行环境

5. **publication** (text[])
   - 存储适用的publication名称数组
   - 支持一条DDL消息对应多个publication

6. **message_extra** (json)
   - 必选字段：`version`（PostgreSQL版本）, `sql_mode`（SQL模式）
   - 可选字段：其他执行上下文信息

#### 索引设计

```sql
-- 主键：保证LSN在单个publication内的唯一性
ALTER TABLE pg_publication_sync ADD PRIMARY KEY (lsn, publication);

-- 时间索引：支持基于时间的查询和清理
CREATE INDEX pg_publication_sync_timestamp_idx ON pg_publication_sync(timestamp);

-- publication索引：支持按publication过滤
CREATE INDEX pg_publication_sync_publication_idx ON pg_publication_sync USING gin(publication);
```

### 4. DDL提取与发布机制

#### DDL识别机制

参照`log_statement=ddl`的实现（`src/backend/tcop/postgres.c`中的`check_log_statement`函数）：

1. **提取位置**：在`standard_ProcessUtility`函数中，`isCompleteQuery`设置为`true`之后
2. **SQL提取**：使用`pstmt->stmt_location`和`pstmt->stmt_len`从`queryString`中提取原始SQL
3. **DDL类型判断**：使用`GetCommandLogLevel()`函数判断是否为DDL语句

#### 消息发布流程

**Q类型消息发布（所有DDL语句）：**
```json
{
    "message_type": "Q",
    "namespace": "[mynsp,public,pg_catalog]",
    "publication": ["pub1", "pub2"],
    "message_data": "CREATE TABLE t1(id int PRIMARY KEY)",
    "message_extra": {
        "version": "16",
        "sql_mode": "standard",
        "current_database": "mydb",
        "current_user": "postgres"
    }
}
```

**A/D类型消息发布（表增删变更）：**
- 参照`AlterSubscription_refresh`的实现逻辑
- 当表通过`ALTER PUBLICATION ... ADD TABLE`添加到publication时，发布'A'消息
- 当表通过`ALTER PUBLICATION ... DROP TABLE`从publication移除时，发布'D'消息
- 对于已存在表执行`ALTER TABLE`等DDL，**只发布'Q'消息**

```json
{
    "message_type": "A",
    "namespace": "[public]",
    "publication": ["pub1"],
    "message_data": "{\"schema\": \"public\", \"table\": \"users\"}",
    "message_extra": {"operation": "add_table_to_publication"}
}
```

#### 发布条件检查

1. **DDL选项检查**：确认publication启用了相应的ddl选项
2. **类型权限检查**：
   - 对于`FOR TABLE`/`FOR TABLES IN SCHEMA`：只允许`table`和`index`
   - 对于`FOR ALL TABLES`：允许所有DDL类型
3. **manual选项处理**：如果为`manual`，不自动发布消息
4. **消息插入**：将格式化后的消息插入`pg_publication_sync`表

### 5. 订阅端处理方案

#### 处理架构

**复用现有apply worker，不创建专门DDL worker：**
- table sync worker：**不处理**DDL消息，专注表数据同步
- apply worker：处理所有消息，包括`pg_publication_sync`表的变更

#### DDL消息处理流程

1. **消息识别**：apply worker识别到`pg_publication_sync`表的变更
2. **类型判断**：根据`message_type`字段决定处理逻辑
3. **Q类型处理**：
   - 提取`message_data`中的原始SQL
   - 使用`namespace`恢复search_path环境
   - 应用`message_extra`中的版本/模式信息
   - 安全执行DDL语句
4. **A/D类型处理**：更新本地publication关系映射

#### 执行顺序与事务保证

1. **LSN顺序保证**：按`lsn`字段顺序处理消息，确保DDL/DML执行顺序一致
2. **事务隔离**：每个DDL在独立事务中执行
3. **错误处理**：
   - DDL执行失败时记录错误日志
   - 继续处理后续消息（不阻塞复制）
   - 提供错误统计和恢复机制

#### 安全性考虑

1. **SQL注入防护**：对原始SQL进行安全性检查
2. **权限验证**：确保订阅端用户有执行DDL的权限
3. **依赖关系处理**：处理DDL之间的依赖关系
4. **冲突解决**：处理与本地对象的命名冲突

### 6. 清理机制

#### pg_publication_sync_prune()函数

```sql
-- 手动清理函数
SELECT pg_publication_sync_prune();

-- 带参数的清理函数（可选扩展）
SELECT pg_publication_sync_prune(
    retention_days => 30,      -- 保留最近30天记录
    min_lsn => '0/0'::pg_lsn   -- 清理该LSN之前的记录
);
```

#### 清理策略

**基于订阅进度清理：**
- 当所有订阅的apply worker都确认应用了某LSN之前的记录
- 基于每个订阅的`confirmed_flush_lsn`判断

**混合清理条件（建议实现）：**
1. 时间条件：记录创建时间超过N天
2. LSN条件：记录lsn小于所有订阅的最小confirmed_flush_lsn
3. 状态条件：记录已被所有订阅处理

#### 自动清理选项（未来扩展）
- 可配置的自动清理后台任务
- 基于WAL保留策略的自动清理

### 7. 实现工作分解

#### 阶段1：语法扩展与验证
1. 修改`src/backend/parser/gram.y`：
   - 扩展`CREATE PUBLICATION`语法支持`ddl`选项
   - 扩展`CREATE SUBSCRIPTION`语法支持`ddl`选项
2. 修改`src/backend/commands/publicationcmds.c`：
   - 添加`parse_publication_ddl_options()`函数
   - 实现DDL选项验证逻辑
3. 修改`src/backend/commands/subscriptioncmds.c`：
   - 添加订阅端DDL选项验证
   - 检查publication的DDL支持情况
4. 增加pg_publication系统表字段，记录要发布的ddl类型；
5. 增加pg_subscription系统表字段，记录要发布的ddl类型；

#### 阶段2：系统表创建
1. 创建`src/include/catalog/pg_publication_sync.h`
2. 创建`src/include/catalog/pg_publication_sync_d.h`
3. 更新Catalog.pm映射
4. 创建初始数据加载脚本

#### 阶段3：发布端实现
1. 修改`src/backend/tcop/utility.c`：
   - 在`standard_ProcessUtility`中添加DDL捕获逻辑
   - 实现DDL消息格式化与插入
2. 修改`src/backend/commands/publicationcmds.c`：
   - 实现表增删时的'A'/'D'消息发布
3. 创建DDL提取工具函数

#### 阶段4：订阅端实现
1. 修改`src/backend/replication/logical/worker.c`：
   - 添加DDL消息识别逻辑
   - 实现DDL安全执行机制
2. 修改`src/backend/replication/logical/proto.c`：
   - 扩展协议支持DDL消息传输

#### 阶段5：辅助功能
1. 实现`pg_sync_ddl()`函数
2. 实现`pg_publication_sync_prune()`函数
3. 添加系统视图：`pg_publication_sync_info`

### 8. 测试策略

#### 单元测试
1. **语法解析测试**：验证DDL选项解析正确性
2. **选项验证测试**：测试FOR TABLE/SCHEMA的类型限制
3. **消息格式测试**：验证JSON消息格式正确性

#### 集成测试
1. **端到端同步测试**：
   - 创建表、索引、视图等对象
   - 验证自动同步功能
   - 测试manual选项的手动同步
2. **复杂场景测试**：
   - 多个publication的DDL同步
   - 嵌套DDL操作（创建表后立即创建索引）
   - 大事务中的DDL操作

#### 回归测试
1. **兼容性测试**：确保不影响现有逻辑复制功能
2. **升级测试**：测试从无DDL支持版本升级
3. **故障恢复测试**：DDL执行失败的处理机制

#### 性能测试
1. **DDL消息发布性能**：大量DDL操作的性能影响
2. **订阅端应用性能**：DDL消息的处理性能
3. **系统表清理性能**：大量记录下的清理操作性能

### 9. 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| DDL执行失败导致复制中断 | 高 | 独立事务执行，失败不影响后续消息 |
| 安全漏洞（SQL注入） | 高 | 严格的SQL安全性检查，权限验证 |
| 性能影响 | 中 | 异步处理，优化消息格式，索引设计 |
| 依赖关系处理复杂 | 中 | 简化处理：按到达顺序执行，依赖检查 |
| 升级兼容性问题 | 中 | 详细升级文档，向后兼容设计 |

### 10. 后续扩展方向

1. **DDL过滤**：支持基于正则表达式的DDL语句过滤
2. **冲突解决策略**：提供可配置的冲突解决机制
3. **DDL回滚支持**：支持订阅端DDL回滚操作
4. **多版本支持**：支持不同PostgreSQL版本间的DDL同步
5. **DDL预检查**：在发布前验证DDL在订阅端的可执行性


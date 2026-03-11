# 逻辑复制支持DDL需求分析

## 需求内容

postgresql当前的逻辑复制仅支持复制DML，不支持复制DDL，需要手动在目标端执行DDL。

为提升用户使用体验，需要实现逻辑复制支持DDL自动同步。

要达到的主要目的：同一个数据库对象的DDL语句不需要在每个目标端都执行一次。
当用户在发布端创建一张表时，订阅端只需要执行一条命令就可以自动同步DDL。

是否需要自动同步DDL应该由订阅端决定，当实现逻辑复制支持DDL功能后，发布端默认支持，至于要往哪个订阅者发送DDL则由订阅者在订阅的时候决定。要往订阅者发送那些ddl也由订阅端决定。

## 需求分析

### 用户接口分析

#### 方案一：复用当前用户接口

当前逻辑复制采用发布订阅者模式，已经有一套成熟的用户接口，用户已经习惯当前的逻辑复制接口。

可考虑基于当前的用户接口来扩展支持DDL复制，而不做大的变更。

#### 方案二： 设计新的接口

保留当前的逻辑复制接口不变，在此基础上设计新的接口，要开启逻辑复制支持DDL需要使用新接口配置。

当开启逻辑复制支持DDL时，需要的操作步骤会变多。

### 实现方式分析

#### 插件方式实现

当前社区逻辑复制支持DDL有第二象限公司实现的pglogical，其采用的是插件形式实现。

在启用逻辑复制支持DDL功能时需要创建pglogical插件。

#### 内核集成实现

当前逻辑复制通过walsender和walreceiver来实现，直接集成到内核里面，可以采用直接扩展replication模块来实现支持DDL。

### 不同目的端分析

逻辑解码的源端一般是postgressql数据库，但是目的端可能是不同的数据库或者第三方组件。

当前的逻辑复制采用发布者、订阅者模式来设计。

发布者和订阅者是多对多的方式，一个发布者可能有多个订阅者订阅，一个订阅者也可以订阅多个发布者。

发布者主要是定义了一些同步的表和规则集合，订阅者则是指定了要同步哪些规则集合。

**从这个角度看，一种可行的实现方式是：对于DDL同步来说，DDL完全可以是一个特殊的发布者，然后对于需要同步的订阅者来说，可以多订阅一个发布者就行。**

#### 发布者分析

发布端创建，指定要发布什么给下游，目标是单个表或者一些表（指定shema下的表、所有表）。可以限制要发布什么行为：insert/update/delete/truncate，默认全部行为都发送。

```sql
CREATE PUBLICATION name
    [ FOR ALL TABLES
      | FOR publication_object [, ... ] ]
    [ WITH ( publication_parameter [= value] [, ... ] ) ]
```


- 可以指定发布所有表，也可以指定发布一个或者多个表
- 除了制定发布的表外，还可以指定要发布的操作，比如insert

with参数用于控制可选选项。

```sql
WITH ( publication_parameter = value )
```

| 参数                         | 含义     |
| -------------------------- | ------ |
| publish                    | 复制哪些操作 |
| publish_via_partition_root | 分区复制方式，是否 |

**如果要在发布端对是否同步DDL做控制，可以在with选项里增加ddl控制项。**

比如：

```sql
CREATE PUBLICATION insert_only
FOR TABLE users
WITH (publish = 'ddl,insert');
```

但是当ddl需要显示配置时，就意味着逻辑复制的默认行为不会同步DDL。

完整示例。

- 复制所有表

```sql
CREATE PUBLICATION pub_all
FOR ALL TABLES;
```

- 复制部分表

```sql
CREATE PUBLICATION sales_pub
FOR TABLE orders, customers;
```

- 只复制insert

```sql
CREATE PUBLICATION log_pub
FOR TABLE logs
WITH (publish = 'insert');
```

- 列级复制

```sql
CREATE PUBLICATION user_pub
FOR TABLE users (id, name);
```

** 需要注意的是当开启ddl同步的时候，是否支持列级复制。因为在逻辑复制中，并不要求发布端和订阅端的表结构完全一致。**

由这里引申出来的结论就是：是否开启自动同步DDL，应该是由发布端和订阅端共同决定的，或者说就是应该由订阅端来决定的。

发布端定义了是否有ddl同步这个能力，订阅端定义了是否需要开启ddl同步。

#### 订阅者分析

订阅端创建，指定要对哪个或哪些publication发起订阅。

```sql
CREATE SUBSCRIPTION subscription_name
    CONNECTION 'conninfo'
    PUBLICATION publication_name [, ...]
    [ WITH ( subscription_parameter [= value] [, ... ] ) ]
```

##### subscription_name

订阅名称。

```sql
CREATE SUBSCRIPTION my_sub;
```

- 在 订阅数据库中唯一
- 会创建多个 后台 worker

系统表为pg_subscription。

```sql
SELECT * FROM pg_subscription;
```

```sql
ostgres=# SELECT * FROM pg_subscription;
 oid | subdbid | subskiplsn | subname | subowner | subenabled | subbinary | substream | subtwophasestate | subdisableonerr | subconninfo | subslotname | subsy
nccommit | subpublications 
-----+---------+------------+---------+----------+------------+-----------+-----------+------------------+-----------------+-------------+-------------+------
---------+-----------------
(0 rows)
```

##### CONNECTION 参数

```sql
CONNECTION 'conninfo'
```

指定如何连接发布端sql。

```sql
CONNECTION 'host=192.168.1.10 port=5432 dbname=test user=rep password=123456'
```

node: 该用户必须有 replication 权限.

##### PUBLICATION

```sql
PUBLICATION publication_name [, ...]
```

指定订阅哪些 publication。

订阅端会 合并所有 publication 的数据流。

##### WITH 参数（subscription_parameter）

| 参数                 | 默认    | 说明                    |
| ------------------ | ----- | --------------------- |
| copy_data          | true  | 是否复制初始数据              |
| enabled            | true  | 是否立即启动                |
| create_slot        | true  | 是否创建 replication slot |
| slot_name          | 自动    | 使用哪个 slot             |
| synchronous_commit | off   | 同步提交策略                |
| binary             | false | 是否二进制复制               |
| streaming          | on    | 是否流式复制                |

当前逻辑复制的两个前提条件：

1. 订阅端必须先创建表；（scheme必须一致，）
2. 表必须有主键；

#### 快照机制分析

在发布者-订阅者模型中，数据的发送推进是通过快照机制来保证的。

WAL记录的是页面的修改，光靠WAL是无法解码成SQL/json这些易读的格式的，我们还需要系统表信息来描述表结构、Tuple结构。因此我们要构建访问系统表的快照，使用这个快照来访问系统表，根据系统表信息把WAL解释成SQL等格式。


### 冲突解决分析

### 权限控制分析

### 迁移工具分析

### 竞品分析

#### pglogical分析

pglogical采用的是postgresql插件机制实现的，通过利用postgresql里预留的hook接口，捕获DDL。

以及使用流复制预留的output接口进行解码。

pglogical与postgresql的逻辑复制时间线关系如下：

| 时间   | 事件                                     |
| ---- | -------------------------------------- |
| 2014 | PostgreSQL 9.4 引入 logical decoding     |
| 2015 | 2ndQuadrant 发布 pglogical               |
| 2017 | PostgreSQL 10 引入原生 logical replication |

pglogical 比 PG 内置逻辑复制更早，pglogical是PostgreSQL 逻辑复制的“实验版本”。

PG10 的逻辑复制就是把 pglogical 的一部分能力合入内核。

在pglogical中，有pglogical.create_node、pglogical.create_subscription接口。

在PG15中，借鉴这些接口有了CREATE PUBLICATION、CREATE SUBSCRIPTION接口。
换句话说，postgresql官方已经移植了一部分pglogical的功能，我们可以基于它的架子继续移植DDL同步。

基于上面的背景，一种可行的方案是：不考虑 pglogical 的全部功能，只想基于 PostgreSQL 15 的逻辑复制，把 DDL 复制能力移到内核。

关键步骤如下：

| 步骤                  | 描述                                                     |
| ------------------- | ------------------------------------------------------ |
| 1. 捕获 DDL           | 在 `ProcessUtility()` 内核里判断 stmt 类型，拦截 DDL              |
| 2. 写 WAL            | 写入 LogicalMessage，定义 `DDL_MESSAGE` type                |
| 3. logical decoding | 内核 decoder 读取 WAL record，并把 DDL 发送到 replication stream |
| 4. apply worker     | 订阅端收到 DDL message，调用 `ProcessUtility` 执行 DDL           |

```shell
Publisher Core (PostgreSQL 15)
+------------------------+
| ProcessUtility()       | <-- 捕获 DDL
|  if DDL:              |
|     log_logical_message_for_ddl()
+------------------------+
          |
          v
+------------------------+
| WAL (LogicalMessage)   |
+------------------------+
          |
          v
+------------------------+
| Logical Decoding       | <-- decode DDL_MESSAGE
+------------------------+
          |
          v
+------------------------+
| Replication Stream     |
+------------------------+
          |
          v
Subscriber Core
+------------------------+
| Apply Worker           |
|  if DDL_MESSAGE:       |
|     ProcessUtility()   |
+------------------------+
```

基于现有的PG15的接口进行扩展，可选的接口是：

```sql
CREATE PUBLICATION pub1
FOR TABLE t1
WITH (publish = 'insert, update, delete, ddl');
```
或者更加明确一点（减少对原有语法的修改）：

```sql
CREATE PUBLICATION pub1
FOR ALL TABLES
WITH (
    publish = 'insert, update, delete',
    publish_ddl = true
);
```

对应订阅端的语法可以变更为：

```sql
CREATE SUBSCRIPTION sub1
CONNECTION 'host=... dbname=...'
PUBLICATION pub1
WITH (
    copy_data = true,
    enable_ddl = true
);
```


#### polardb-for-postgres分析

#### gaussdb分析

## 需求分解

需求优先级表

### 分解到sql引擎的需求

### 分解到存储引擎的需求

### 分解到文档的需求

### 分解到运维工具的需求

### 分解到可用性的需求

### 分解到自动化测试的需求
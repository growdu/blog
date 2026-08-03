# 逻辑复制支持DDLAI提示词

## 需求

逻辑复制需要支持自动同步DDL。

逻辑复制当前仅支持同步DML，为了提升用户使用体验和增强逻辑同步功能。

### publication

原来的publication用户接口：

```sql
CREATE PUBLICATION name
    [ FOR ALL TABLES
      | FOR publication_object [, ... ] ]
    [ WITH ( publication_parameter [= value] [, ... ] ) ]

where publication_object is one of:

    TABLE table_and_columns [, ... ]
    TABLES IN SCHEMA { schema_name | CURRENT_SCHEMA } [, ... ]

and table_and_columns is:

    [ ONLY ] table_name [ * ] [ ( column_name [, ... ] ) ] [ WHERE ( expression ) ]
```
需要增加ddl选项，接口变更为：

```sql
CREATE PUBLICATION name
    [ FOR ALL TABLES
      | FOR publication_object [, ... ] ]
    [ WITH ( publication_parameter [= value] [, ... ], ddl [ = value] [, ... ]) ]

where publication_object is one of:

    TABLE table_and_columns [, ... ]
    TABLES IN SCHEMA { schema_name | CURRENT_SCHEMA } [, ... ]

and table_and_columns is:

    [ ONLY ] table_name [ * ] [ ( column_name [, ... ] ) ] [ WHERE ( expression ) ]
```
其中，ddl可取的值如下：

- table
- index
- type
- function
- domain
- trigger
- view
- rule
- schema
- extension
- all

其中table 和index在for table，for table in schema，for all tables下都生效，而function、domain、trigger、view、rule、schema、extension、all只在for all tables下生效，需要在实现时进行限制。

如果publication是FOR TABLE或FOR TABLES IN SCHEMA，ddl选项只能包含table和index。如果用户指定了function等类型，应该报错。

manual则是需要用户手动执行命令同步ddl，不会自动同步。应该提供一个函数如pg_sync_ddl(ddl)来手动触发同步。

### subscription

原来的接口为：

```sql
CREATE SUBSCRIPTION subscription_name
    CONNECTION 'conninfo'
    PUBLICATION publication_name [, ...]
    [ WITH ( subscription_parameter [= value] [, ... ] ) ]
```
同样的增加ddl选项，接口变更为：

```sql
CREATE SUBSCRIPTION subscription_name
    CONNECTION 'conninfo'
    PUBLICATION publication_name [, ...]
    [ WITH ( subscription_parameter [= value] [, ... ], ddl [ = value] [, ... ] ) ]
```
ddl的取值范围与publication一致。publication用于控制发布，subscription用于控制是否订阅。

subscription在订阅时需要确定publication是否存在对应的发布，不存在需要报错。

## 设计实现

整体设计原则：

采用记录客户端ddl的query_string到新建的系统表pg_publication_sync，逻辑同步时如果开启了ddl同步，就把pg_publication_sync当作普通表使用dml同步过去。在该表中会记录ddl的原始字符串，订阅端收到后可以重新执行。

pg_publication_sync表的定义如下：

| 字段 | 类型 | 描述 |
|--------|------|----------|
|lsn	|lsn|	写入这个记录时，lsn位置，用于定时删除不需要的记录（做个函数清理pg_publication_sync表里不需要的信息: select pg_publication_sync_prune() ,由用户手动执行）|
|timestamp	|timestamp| with time zone	事件上发生的时间|
|message_type	|char|	消息类型，'A' 表示新增对象、'D'表示删除对象、'Q' DDL SQL信息，其它类型按需要扩展|
|message_data	|text|	事件详细信息，根据message_type按需要定义即可|
|namespace	|text|	当前search_path|
|publication	|text[]|	publication列表，需要根据这个列表过滤数据|
|ddl_type	|text[]|	记录ddl的类型，订阅端需要根据这个字段对比本端的ddl类型，确认是否需要apply|
|target_table	|text|	该ddl对应的table，如果是非table类的ddl，为null，主要是根据target table来确定该行记录是否需要发布|
|message_extra	|json|	事件的额外信息，json格式，必选字段：版本、语法模式。其它可选参数按需添加：如一些特殊参数、大小写敏感等|

### 提取ddl

可以完全参照log_statement=dll的实现（详见：check_log_statement），parseTree里会记录stmt对应的SQL文本，在query_string里的位置：standard_ProcessUtility的入参pstmt、queryString，得到DDL的原始SQL。

### 发布DDL

在standard_ProcessUtility中isCompleteQuery设置为true后发布DDL。即往pg_publication_sync中新增表。

1. 发布ddl消息message_type=‘Q’

```json
{
    "message_type": "Q",
    "namespace": "[mynsp,public,pg_catalog]",   --当前环境namespace
    "publication": "[pub1,pub2]",   --满足上面规则的publicaton
    "message_data": "CREATE TABLE t1(id int) ", --原始SQL
    "message_extra": "版本、语法模式、关键参数",   --apply时使用的必要的额外信息，json格式，按需添加
}

```
2.发步同步消息（message_type=‘A/D’）

```json
{
    "message_type": "A",     --A表示新增，D表示删除（只有这种情况需要message_type='D'的消息）
    "publication": "[pub1,pub2]",  --被添加或者删除的pg_publication_rel.prpubid，且publication.ddl里有table类型
    "message_data": " {schema='nsp', table_name='tbl'} "  --新增的表对象，可以用json格式
}

```
pg_publication_sync需要跟随DML发布。

所有ddl都需要发布Q消息，A/D消息是用于发布变更，A消息细节可以参考：AlterSubscription_refresh,D消息可以参考AlterSubscription_refresh。

### 如何解码

发布端在发送数据时，需要解析wal日志，在读取到pg_publication_sync表数据时，需要把pg_publication_sync的行数据取出来，并进行过滤匹配。
以普通表的方式发送到订阅端。
需要注意的是，发布端在解码时会把系统表排除，需要根据pg_publication_sync的oid把这个表在解码流程中放行。

### 如何apply

订阅端在收到pg_publication_sync表的数据时需要进行特殊处理，识别到ddl消息后，将message_data提取出来执行。

订阅端直接复用DML的apply woker，然后按顺序解析执行就行，需要注意的是table sync worker不能处理DDL消息。

订阅端通过解析表名是pg_publication_sync来识别ddl同步，当发现是这张表时，就需要执行ddl同步逻辑。

## 主要工作事项

1.用户接口适配；
2.系统表实现；
3.发布端适配；
4.订阅端适配；
5.编译构建；
6.测试用例编写；
7.测试验证；
8.测试报告输出；
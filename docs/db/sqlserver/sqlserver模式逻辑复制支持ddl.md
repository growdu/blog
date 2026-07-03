# sqlserver模式逻辑复制支持ddl

## 背景现状

当前数据库使用babelfish插件（bbf）来支持sqlserver模式，bbf采用双端口的设计：
即数据库在启动时会监听多个端口，一般是pg原生的端口和tsql端口，比如5432和1433.

sqlserver模式的sql就走1433端口，pg模式的sql就走5432端口。

对于ddl、dml这样的语句比较容易区分，且sqlserver模式和pg模式都有对应的语法。

但是对于一些pg内核特有的语法，sqlserver没有对应的语法，比如postgresql的逻辑复制和物理复制。

对于逻辑复制来说，连接tsql端口无法创建逻辑复制，无法识别postgresql的逻辑复制语句或者无法使用等价的tsql语句来创建逻辑复制。

对于逻辑复制来说，sqlserver模式有两种解决方法：

1.创建逻辑复制连接pg端口，创建成功后再连接tsql端口执行tsql语句；（所有逻辑复制相关的语句都走pg端口）—— 2个端口 --》不需要开发
2. 所有操作都连接tsql端口执行；-- 1 个端口 --》需要开发，tsql端口需要适配识别postgresql逻辑复制语句


### postgresql逻辑复制语句

| 类型     | SQL                                |
| ------ | ---------------------------------- |
| 发布     | CREATE PUBLICATION                 |
| 订阅     | CREATE SUBSCRIPTION                |
| 修改发布   | ALTER PUBLICATION                  |
| 修改订阅   | ALTER SUBSCRIPTION                 |
| 删除发布   | DROP PUBLICATION                   |
| 删除订阅   | DROP SUBSCRIPTION                  |
| 复制槽    | pg_create_logical_replication_slot |
| 查看复制   | pg_stat_subscription               |
| 查看slot | pg_replication_slots               |

若选择只使用一个端口的方式，则上述的语句都需要适配到sqlserver模式。

**主要问题就是：如何定义用户的使用方式，是使用一个端口可以完成完整的逻辑复制功能，还是两个端口（一个用于执行逻辑复制语句，另外一个用于执行ddl、dml等）。**

## sqlserver模式下支持ddl自动同步

对于逻辑复制支持ddl来说，主要涉及如下三个问题：

1. 捕获ddl；
2. ddl 插入pg_publication_sync表；
3. ddl发送到订阅端；
4. 订阅端apply ddl；

由于bbf的实现机制，前三步与原生pg模式均一致，唯一的区别主要在第4步。

订阅端如何apply ddl又会受到前面描述的使用一个端口还是两个端口来完成完整逻辑复制的功能。

1. 使用一个端口可以完成完整的逻辑复制功能，那创建逻辑复制使用的就是tsql的端口，订阅端的连接本身就在tsql的上下文里，直接就可以执行；（适配工作量较小，只需要区分数据库模式）
2. 当使用两个端口（一个用于执行逻辑复制语句，另外一个用于执行ddl、dml等）的时候，就需要订阅端在接收到ddl后，初始化一个tsql的上下文，在worker内部调用bbf来解析执行ddl；（适配工作量较大，需要适配ddl到tsql再到pg存储引擎的流程）；

因而ddl的实现也会受限于当前sqlserver模式下对用户使用逻辑复制的预期行为（ddl同步和当前逻辑复制共用同一套端口）。
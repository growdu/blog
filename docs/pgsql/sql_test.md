# sql_test

TPC(事务处理性能委员会：Transaction Processing Performance Council)，是由数 10 家会员公司创建的非盈利组织，总部设在美国。TPC 的主要成员是计算机软硬件厂家，其主要成员包括 IBM，HP，Oracle，Microsoft 等。TPC 的功能是制定商务应用标准程序（Benchmark）的标准规范，性能和价格度量，并管理测试结果的发布。TPC 不给出基准测试程序的代码，而只给出基准程序的标准规范。任何厂家或其它测试者都可以根据规范，最优的构造自己的系统。TPC 已经推出的基准程序包括：TPC-A，TPC-B，TPC-C，TPC-D，TPC-E，TPC-W。

- TPC-C 是在线事务处理（OLTP）的基准程序
- TPC-D 是决策支持的基准程序
- TPC-E 是大型企业的信息服务的基准程序

## TPC-C(TPCC)

TPC-C 是一种衡量 OLTP 系统性能和可伸缩性的基准测试项目。它由一系列的 OLTP 工作流组成，包括查询，更新及队列式小批量事务在内的广泛数据库功能。它模拟了一个典型的 OLTP 应用环境中的活动，这些活动由一系列复杂的事务组成。TPC-C 工作流应该具备以下特性：

- 适当复杂的 OLTP 事务
- 在线和延迟事务执行模型
- 多用户
- 适当的系统和应用执行时间
- 大量的磁盘输入和输出
- 事务完整性（ACID）
- 随机的数据访问
- 数据库由各种大小，属性和关系的表组成

### TPC-C 输入数据流

TPC-C 系统需要处理的交易有以下五种：

1. New-Order： 客户输入一笔新的订货交易
2. Payment：更新客户账户余额以反应其支付状况
3. Delivery：发货（批处理交易）
4. Order-Status：查询客户最近交易的状态
5. Stock-Level：查询仓库库存状况，以便能够及时补货。

各个类型的交易在系统中所占的比例：

1. New-Order： 45%
2. Payment：43%
3. Delivery：4%
4. Order-Status：4%
5. Stock-Level：4%

对于前四种类型的交易，要求响应时间在 5 秒以内；对于库存状况的查询交易，要求响应时间在 20 秒以内。

这五种交易作用在图 1 所示的九张表上，事务操作类型包括更新，插入，删除和取消操作。

### TPC-C 输出指标

TPC-C 的测试结果主要有两个指标：

- 流量指标（tpmC）：描述了系统在执行 Payment，Order-Status，Delivery，Stock-level 这四种交易的同时，每分钟可以处理的 New-Order 交易的数量。流量指标值越大越好。

- tpm 是 transactions per minute 的简称；C 指 TPC 中的 C 基准程序。它的定义是每分钟内系统处理的新订单个数。要注意的是，在处理新订单的同时，系统还要按图 1 的要求处理其 它 4 类事务 请求。从图 1 可以看出，新订单请求不可能超出全部事务请求的 45％，因此，当一个 系统的性能为 1000tpmC 时，它每分钟实际处理的请求数是 2000 多个。

- 性价比（Price/tpmC）：测试系统价格与流量指标的比值。性价比越小越好

## benchmarksql

BenchmarkSQL是对OLTP数据库主流测试标准TPC-C的开源实现。目前最新版本为V5.0，该版本支持Firebird，Oracle和PostgreSQL数据库，测试结果详细信息存储在CSV文件中，并可以将结果转换为HTML报告。

# reference

1. https://www.jianshu.com/p/769611dd86b7
# pg-ferret

- pg-ferret通过ebpf给postgres backend的函数插入uprobes/uretprobes.

- pg-ferret提供一个用户态collector（loadbar），把kernel收到的probe事件收集起来，
合并成"spans"/trace,然后通过OpenTelemetry（OLTP）导出到traceing后端。（比如grafana tempo）

- 动态attach，不需要修改postgres源码，也不需要重启或者手动插在。适合生产环境或调试环境使用。

pg-ferret主要跟踪如下信息：

- 函数调用entry+exit：对于被probe的postgres函数（user-level函数），当函数开始执行或者返回时会触发事件

- 调用参数和上下文：uprobe允许读取函数入口时的参数

- 返回值和执行结果： uretprobe可以在函数返回时读取返回值

- 调用时长：在entry时记录时间戳，在return时取当前时间计算差值，可以计算函数调用的耗时。

- 跟踪调用堆栈：pg-ferret的用户空间collector会把entry和return事件合并为trace spans。然后通过oltp导出。
形成完整的调用链，便于在trace系统中做分布式trace/可视化。

- 多函数/全流程监控

pg-ferret的主要目的：

- 零侵入

- 详细可视化trace

- 排错/性能分析

- 统计/监控/audit

- hook任意函数

pg-ferret的潜在问题：

- 需要符号表，带调试信息

- 性能开销/高频调用

- 当前仅支持用户态函数

- 数据隐私/安全

## 函数耗时计算

函数耗时计算是在span_end的时候由oltp计算的。
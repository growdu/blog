# vpp代码流程分析

常规程序都是从main函数开始执行，main函数执行完后程序退出。但vpp利用gcc的 \_\_attribute\_\_((constructor))特性，使很多函数都在main函数之前执行。主要是插件的配置、注册等操作。当然这些配置和注册操作只是告诉vpp有哪些插件和配置，具体的注册加载执行还需要使用dlopen的方式，按照接口约定拿到具体的执行函数才能进行注册加载以及后续的插件处理。

> VLIB_INIT_FUNCTION用来定义构造函数，注册函数到vlib_main_t->init_function_registrations，这个链表在main()函数之前创建。
>
> vlib_main()-> vlib_call_all_init_functions()注册的函数在这里被调用初始化，最后执行函数vlib_main_loop()。
>
> 像这样由宏定义和构造函数创建的全局链表的方式还有如下几个:
>
> ·    VLIB_API_INIT_FUNCTION
>
> ·    VLIB_CLI_COMMAND
>
> ·    VLIB_CONFIG_FUNCTION
>
> ·    VLIB_EARLY_CONFIG_FUNCTION
>
> ·    VLIB_MAIN_LOOP_ENTER_FUNCTION
>
> ·    VLIB_MAIN_LOOP_EXIT_FUNCTION
>
> ·    VLIB_REGISTER_NODE

vpp具体来说，包含如下几个部分：

- 基础数据结构（重点是hash和vec）
- 堆管理（内存池）
- 线程管理
- 日志管理
- 插件管理
- 定时器
- 节点调度

## 代码流程

```mermaid
graph TB
启动-->读取配置文件,解析参数-->main线程绑核-->初始化堆-->查找插件路径-->vlib_unix_main-->thread0
```

- main

```mermaid
graph TB
main-->|初始化vpp的堆,映射内存|clib_mem_init_thread_safe
clib_mem_init_thread_safe-->clib_mem_init-->create_mspace-->|使用mmap将内存匿名映射到vpp进程内|CALL_MMAP-->clib_mem_set_heap-->vpe_main_init-->vlib_unix_main
```

- vlib_unix_main

```mermaid
graph TB
vlib_unix_main-->|筛选enable的插件|vlib_plugin_config-->vlib_plugin_early_init
vlib_plugin_early_init-->vlib_load_new_plugins-->load_one_plugin-->|执行每个插件的early_init|early_init-->vlib_call_all_config_functions-->|执行每个插件的config函数|config_function_registrations-->clib_elf_main_init-->vlib_thread_stack_init-->clib_calljmp-->thread0
```

- thread0

```mermaid
graph TB
thread0-->vlib_main-->clib_time_init-->vlib_physmem_init-->vlib_buffer_main_init-->vlib_thread_init-->vlib_map_stat_segment_init-->vlib_register_all_static_nodes-->vlib_node_main_init-->vpe_api_init-->vlibmemory_init-->map_api_segment_init-->vlib_call_all_init_functions-->vlib_buffer_create_free_list-->vlib_call_all_config_functions-->vlib_call_all_main_loop_enter_functions-->vlib_main_loop
```

- vlib_main_loop

```mermaid
graph TB
vlib_main_loop-->vlib_main_or_worker_loop-->dispatch_process-->dispatch_node
vlib_main_loop-->dispatch_node-->dispatch_node
```

- dpdk plugin

```mermaid
graph TB
load_one_plugin-->dpdk_early_init
load_one_plugin-->dpdk_config
dpdk_process_node-->dpdk_process-->dpdk_lib_init
dpdk_input_node-->dpdk_device_input-->rte_eth_rx_burst
dpdk_deviceclass-->tx_burst_vector_internal-->rte_eth_tx_burst
```


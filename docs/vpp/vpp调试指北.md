# vpp调试指北

常用程序调试有如下几种方式：

- 日志打印
- gdb调试

## 日志打印

- 可以使用printf直接打印到当前shell
- vpp自带的日志模块会使用syslog记录日志

## gdb调试

### 直接使用gdb调试

```shell
gdb vpp
(gdb)set args param
(gdb) b break_point
(gdb) r
```

重点在于需要使用set args设置参数，同时需添加断点。

## 使用attach

vpp按正常模式启动，启动后使用top找到进程号，利用gdb attach调试。

```shell
gdb attach pid
```

vpp本身提供了如下全局函数，可用来查看vecetor的相关信息：

```shell
(gdb) p vl(vm->node_main.nodes)
$8 = 575
(gdb) p pe(vm->node_main.nodes)
$9 = 575
(gdb) p pifi(vm->node_main.nodes,576)
$10 = 1
(gdb) p pifi(vm->node_main.nodes,575)
$11 = 1
(gdb) p pifi(vm->node_main.nodes,574)
$12 = 0
(gdb) p debug_hex_bytes(vm->node_main.nodes,20)
74c408e7ffff000044af27e9ffff00001454fce6
$13 = void
(gdb) p debug_hex_bytes(vm->node_main.nodes,8)
74c408e7ffff0000
$14 = void
(gdb) p debug_hex_bytes(vm->node_main.nodes,1)
74
$15 = void
(gdb) p debug_hex_bytes(vm->node_main.nodes,2)
74c4
```
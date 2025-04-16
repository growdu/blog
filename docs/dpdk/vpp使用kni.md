# vpp使用kni

## 加载rte_kni.ko

在dpdk插件的main.c通过判断/dev/kni是否存在来确定rte_kni模块是否加载。

若没有加载需要使用如下命令加载：

```shell
insmod rte_kni.ko carrier=on
```

<font colot="red">注意：carrier=on不能省略，因为kni模块该配置默认关闭，会导致kni无法发包。</font>

## dpdk插件分流

在dpdk插件中根据报文类型选择要将报文送到什么地方。
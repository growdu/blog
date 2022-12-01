# fastgtpu配置及cli说明文档

## 配置

vpp加载时会读取startup.conf的配置，fastgtpu的配置如下：

```shell
fastgtpu {
        # 发送队列大小，值为2的幂次方
        # 如20表示发送队列大小为2^20
        tx-queue 20
        # 报文是否送往运用层，配置该参数后收到报文直接丢弃，不做任何处理
        tx-to-application-off
}
```

## cli

可以通过vppctl查看fastgtpu插件状态和清除统计信息。

```shell
vpp# show fastgtpu stats
vpp# clear fastgtpu
```


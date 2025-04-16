# vpp适配ptp方案

vpp主要在5G小基站侧基于dpdk用于收发包处理。而中国移动对基站侧的ptp协议实现要求如下：

- 应支持OC，可选支持BC
- 支持BMC状态信息提取，但不强制要求支持状态决策算法和选源算法
- 基站设备应支持PTP端口应可设置为Enable和Disable，并应可配置Slave_Only功能使能和不使能
- PTP报文封装应支持PTP over IEEE Std 802.3/Ethernet方式，可选支持 PTP over UDP over IPv4方式，可选支持VLAN功能
- 支持组播，单播可选支持
- 支持one-step模式，two-step模式可选
- 支持支持E2E延时机制，P2P延时机制可选
- 支持时延不对称补偿设置功能，补偿范围+/-100us，补偿步长不大于10ns

当前dpdk实现了ptpclient，支持如下功能：

- 仅支持slaver
- 仅支持E2E
- 仅支持做oc
- 不支持BMC算法，使用第一个发现的master作为主时钟
- 支持one-step模和two-step模式
- 支持组播
- PTP报文封装仅支持PTP over IEEE Std 802.3/Ethernet方式

按照当前功能分析对比，ptpclient能满足中国移动对基站侧的ptp协议实现要求。

以下两个配置要添加实现也较简单，不影响核心功能。

- 基站设备应支持PTP端口应可设置为Enable和Disable，并应可配置Slave_Only功能使能和不使能
- 支持时延不对称补偿设置功能，补偿范围+/-100us，补偿步长不大于10ns

## 实现

基于vpp的dpdk插件实现，dpdk在收到报文后，先过滤ptp报文，对ptp报文进行处理，处理完成后再交由下一步流程处理。

## 配置

在dpdk插件中添加` ptpclient 1`来开启和添加ptpclient，使用`ptpclient-time-sync`来控制是否同步系统时间。配置样例如下：

```shell
dpdk {
        ## Change default settings for all intefaces
        huge-dir /mnt/hugepages
        no-pci
        num-mem-channels 1
        kni 1
        ptpclient 1
        dev default {
                ## Number of receive queues, enables RSS
                ## Default is 1
                num-rx-queues 1
                num-rx-desc 40960
                #num-rx-desc 81920
                rss { ipv4 }

                ## Number of transmit queues, Default is equal
                ## to number of worker threads or 1 if no workers treads
                num-tx-queues 1
                num-tx-desc 8192
        }
        proc-type primary
        log-level 7
}
```

## reference

主要参考文档为1588v2时间接口规范 QB-B-017-2010.doc，以及dpdk ptpclient源码样例。

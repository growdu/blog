---
title: "一致性协议"
description: "一致性协议：Raft、DCF、totem、disk-paxos 与 ZooKeeper —— 主从怎么选、账怎么记、网络分区时会不会脑裂。"
cascade:
  categories:
    - 一致性协议
tags:
  - 一致性协议
---

# 一致性协议

一致性协议：Raft、DCF、totem、disk-paxos 与 ZooKeeper —— 主从怎么选、账怎么记、网络分区时会不会脑裂。

## 本系列文章

- [dcf写入机制](./dcf写入机制.md)
- [dcf投票系统详解](./dcf投票系统详解.md)
- [dcf运行机制](./dcf运行机制.md)
- [openguass dcf源码阅读](./openguass%20dcf源码阅读.md)
- [一文读懂openguass dcf网络模块](./一文读懂openguass%20dcf网络模块.md)
- [常用压缩算法编程](./常用压缩算法编程.md)
- [corosy-qdevice源码阅读](./corosy-qdevice源码阅读.md)
- [corosync-qdevice中ffsplit与lsm算法的区别](./corosync-qdevice中ffsplit与lsm算法的区别.md)
- [corosync-qdevice源码阅读](./corosync-qdevice源码阅读.md)
- [corosync-qdevice详解](./corosync-qdevice详解.md)
- [corosync共享多仲裁方案设计](./corosync多仲裁方案设计.md)
- [corosync源码阅读](./corosync源码阅读.md)
- [disk-paxos详解](./disk-paxos详解.md)
- [libqb源码详解](./libqb源码详解.md)
- [totem协议详解](./totem协议详解.md)
- [c-raft分布式存储方案](./c-raft分布式存储方案.md)
- [c-raft](./c-rart.md)
- [raft协议动态调整quorum](./raft协议动态调整quorum.md)
- [raft重要概念](./raft重要概念.md)
- [zookeeperC语言API编程指南](./zookeeperC语言API编程指南.md)
- [zookeeper主备集群demo](./zookeeper主备集群demo.md)
- [zookeeper使用说明文档](./zookeeper使用说明文档.md)
- [zookeeper使用说明文档](./zookeeper安装部署教程.md)
- [数据库分布式集群动态调整quorum值方案对比](./分布式集群动态调整quorum值方案对比.md)
- [初始化需要加-c参数，会生成dcf相关文件](./opengauss%20dcf搭建%20-%20墨天轮.md)
- [openguass dcf启动详解](./openguass%20dcf启动详解.md)
- [openguass 升级机制](./openguass升级机制.md)
- [openguass架构详解](./openguass架构详解.md)

---
description: "corosync-qdevice 源码阅读笔记：网络投票算法、消息类型与 qnetd 仲裁的注册流程。"
---
# corosync-qdevice源码阅读

```c
qdevice_net_algorithm_register_all
msgio_read

TLV_VOTE_ACK

MSG_TYPE_ASK_FOR_VOTE

qnetd_algorithm_register_all
```
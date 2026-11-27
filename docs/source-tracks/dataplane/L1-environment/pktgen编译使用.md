---
description: "pktgen 的编译步骤：x86 与 arm 两条交叉编译链路的环境变量与 make config 用法。"
---
# pktgen编译使用

## 编译

### x86

```shell
export RTE_SDK=/home/duanyingshou/code/dpdk
export RTE_TARGET=x86_64-pktgen-linuxapp-gcc
make config T=x86_64-pktgen-linuxapp-gcc
```
### arm
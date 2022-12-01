# cdu_nxp2160_ptp1588v2实现方案

ptp1588v2是一套软件协议标准，借助于软硬件时间戳来进行时间同步。因而其需要两方面的支持：

- 硬件支持时间戳或软件层面直接添加时间戳
- 软件层面需按照IEEE1588实现相关的协议

当前cdu-nxp2160板子硬件（网卡）支持时间戳功能，硬件层面满足要求。软件层面实现IEEE1588v2协议又分为两种情况：

- 基于linux内核的系统栈
- 基于dpdk的用户栈

## 系统栈

基于系统栈的话可直接使用第三方开源实现，具体又分为两种：

- ptpd
- linuxptp

一般常用linuxptp实现的ptp4l，ptpd可作替代方案或备用方案。

## 用户栈

基于dpdk的用户栈来实现IEEE1588v2，当前没有第三方开源实现，需对linuxptp或者ptpd进行移植适配。

当前dpdk中实现了简单的ptpclient，仅提供ptp的slaver功能。

## 基于dpdk的用户栈1588v2移植方案

### 基于kni移植

kni功能提供了在使用dpdk的同时能使用系统栈的功能，kni会在linux系统中虚拟出一个网口，基于该网口运行linuxptp。

但当前kni虚拟出的网口不支持ptp hardware clock功能，这将会导致ptp4l无法运行。但网卡硬件确实提供了硬件时间戳的功能，因而需针对kni对ptp4l进行适配。

具体的适配方案又分为两种：

- 适配kni

  适配kni即需要修改kni驱动代码，使其虚拟出的网口支持ptp hardware clock。

- 适配ptp4l

  适配ptp4l即需修改ptp4l源码，需要修改其打时间戳的逻辑，替换相关接口为dpdk提供的时间接口；同时涉及到将ptp4l集成到dpdk中，或者说需考虑dpdk与ptp4l交互的方式。

#### 适配kni

基于kni移植主要需对kni驱动进行适配，适配的具体层面为虚拟出的网口需支持ptp hardware clock功能。主要涉及代码改动为kni网口驱动代码。

- 当前网口ptp配置

```shell
root@HX-Technical-A:~# ethtool -T vEth0
Time stamping parameters for vEth0:
Capabilities:
        software-receive      (SOF_TIMESTAMPING_RX_SOFTWARE)
        software-system-clock (SOF_TIMESTAMPING_SOFTWARE)
PTP Hardware Clock: none
Hardware Transmit Timestamp Modes: none
Hardware Receive Filter Modes: none
```

- 预期kni网口ptp配置

```shell
root@HX-Technical-A:~# ethtool -T vEth0
Time stamping parameters for eth3:
Capabilities:
        hardware-transmit     (SOF_TIMESTAMPING_TX_HARDWARE)
        hardware-receive      (SOF_TIMESTAMPING_RX_HARDWARE)
        hardware-raw-clock    (SOF_TIMESTAMPING_RAW_HARDWARE)
PTP Hardware Clock: 0
Hardware Transmit Timestamp Modes:
        off                   (HWTSTAMP_TX_OFF)
        on                    (HWTSTAMP_TX_ON)
        one-step-sync         (HWTSTAMP_TX_ONESTEP_SYNC)
Hardware Receive Filter Modes:
        none                  (HWTSTAMP_FILTER_NONE)
        all                   (HWTSTAMP_FILTER_ALL)
```

#### 适配ptp4l

适配ptp4l主要所做工作分为三个方面：

1. 修改其启动逻辑，不依赖于网口的ptp hardware clock选项；
2. 修改其时间戳获取和修改接口，调用dpdk提供的时间戳接口；
3. 设计dpdk与ptp4l的交互通信方式；（当前dpdk所在的vpp进程与ptp4l是两个独立的进程。）

### 基于linuxptp移植

基于linuxptp移植即将相关代码逻辑全部适配到用户栈，具体是在基于dpdk的vpp中添加插件，实现整套IEEE1588v2协议。
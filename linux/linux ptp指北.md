# linux ptp指北

## ptp是什么

PTP（Precision Time Protocol）精确时间协议，由IEEE1588规定，用于同步网络中两台机器的时间。1558使用延时-请求测量机制达到主从时间同步。

## PTP协议相关

### 时钟类型

PTP按照时钟类型分为：

- OC

  普通时钟

- TC

  透明时钟

- BC

  边界时钟

### 承载方式

PTP报文支持多种报文承载方式：

- 基于MAC
- 基于UDP

### 报文类型

PTP报文分为事件报文和通用报文：

- Sync
- Delay_Req
- PDelay_Req
- PDelay_Resp

- Announce
- Follow_Up
- Delay_Resp
- Pdelay_Resp_Follow_Up
- Management
- Signaling

### PTP报文参数

- 发包频率

### 时间戳发送类型

- 1-step

  1-Step 在从机端更简单，因为它必须只接收一条消息，而对于两步，从时钟必须先接收两条消息才能设置自己的时间。

- 2-step

  在发送端或主端，由于将所需信息附加到 1 步同步消息所涉及的处理工作，使用 2 步更容易。2-step 不需要在消息离开时将时间戳写入消息，这可以使 2-step 主时钟在硬件方面预先便宜。这也增加了灵活性——可以在不改变硬件的情况下改变数据包的编码方式。

  如果使用 10 Gigabit 或更高的以太网链路，2-Step 也是唯一的选择，因为以更高比特率编码消息的时间有限。

## ptp4l

ptp4l是linux下面PTP协议的实现程序，使用ptp4l可以收发ptp报文。

### 命令行参数

```shell
[root@localhost x86]#  ./ptp4l -h

usage: ptp4l [options]

 Delay Mechanism

 -A        Auto, starting with E2E
 -E        E2E, delay request-response (default)
 -P        P2P, peer delay mechanism

 Network Transport

 -2        IEEE 802.3
 -4        UDP IPV4 (default)
 -6        UDP IPV6

 Time Stamping

 -H        HARDWARE (default)
 -S        SOFTWARE
 -L        LEGACY HW

 Other Options

 -f [file] read configuration from 'file'
 -i [dev]  interface device to use, for example 'eth0'
           (may be specified multiple times)
 -p [dev]  Clock device to use, default auto
           (ignored for SOFTWARE/LEGACY HW time stamping)
 -s        slave only mode (overrides configuration file)
 -l [num]  set the logging level to 'num'
 -m        print messages to stdout
 -q        do not print messages to the syslog
 -v        prints the software version and exits
 -h        prints this message and exits
```

### 使用

- 边界时钟

  作为边界时钟时，需要两个网口，一个网口做slaver，与上游高精度时钟同步；另一个网口做master，与下游时钟同步。

  - IEEE 802.3

  ```shell
  # master
  ptp4l -2 -i eth0 -m -H
  # slaver
  ptp4l -2 -i eth1 -m -H -s
  ```

  - udp4

  ```shell
  # master ip
  ifconfig eth0 174.168.1.12
  ptp4l -4 -i eth0 -m -H
  # slaver ip
  ifconfig eth1 174.168.1.13
  ptp4l -4 -i eth1 -m -H -s
  ```

- 普通时钟

  - IEEE 802.3

    ```shell
    ptp4l -2 -i eth0 -m -H -s
    ```

  - udp4

    ```shell
    ifconfig eth1 174.168.1.13
    ptp4l -4 -i eth1 -m -H -s
    ```

### 配置文件

使用-f ptp4l.cfg指定使用配置文件。

```shell
The configuration file is divided into sections. Each section starts with a line containing its name enclosed in brackets and it follows with settings. Each setting is placed on a separate line, it contains the name of the option and the value separated by whitespace characters. Empty lines and lines starting with # are ignored.

The global section (indicated as [global]) sets the program options, clock options and default port options. Other sections are port specific sections and they override the default port options. The name of the section is the name of the configured port (e.g. [eth0]). Ports specified in the configuration file don't need to be specified by the -i option. An empty port section can be used to replace the command line option.
Port Options

logAnnounceInterval
    The mean time interval between Announce messages. A shorter interval makes ptp4l react faster to the changes in the master-slave hierarchy. The interval should be the same in the whole domain. It's specified as a power of two in seconds. The default is 1 (2 seconds). 
logSyncInterval
    The mean time interval between Sync messages. A shorter interval may improve accuracy of the local clock. It's specified as a power of two in seconds. The default is 0 (1 second). 
logMinDelayReqInterval
    The minimum permitted mean time interval between Delay_Req messages. A shorter interval makes ptp4l react faster to the changes in the path delay. It's specified as a power of two in seconds. The default is 0 (1 second). 
logMinPdelayReqInterval
    The minimum permitted mean time interval between Pdelay_Req messages. It's specified as a power of two in seconds. The default is 0 (1 second). 
announceReceiptTimeout
    The number of missed Announce messages before the last Announce messages expires. The default is 3. 
transportSpecific
    The transport specific field. Must be in the range 0 to 255. The default is 0. 
path_trace_enabled
    Enable the mechanism used to trace the route of the Announce messages. The default is 0 (disabled). 
follow_up_info
    Include the 802.1AS data in the Follow_Up messages if enabled. The default is 0 (disabled). 
delay_mechanism
    Select the delay mechanism. Possible values are E2E, P2P and Auto. The default is E2E. 
network_transport
    Select the network transport. Possible values are UDPv4, UDPv6 and L2. The default is UDPv4.

Program and Clock Options

twoStepFlag
    The local clock is a two-step clock if enabled. One-step clocks are not supported yet. The default is 1 (enabled). 
slaveOnly
    The local clock is a slave-only clock if enabled. The default is 0 (disabled). 
priority1
    The priority1 attribute of the local clock. It is used in the best master selection algorithm, lower values take precedence. Must be in the range 0 to 255. The default is 128. 
priority2
    The priority2 attribute of the local clock. It is used in the best master selection algorithm, lower values take precedence. Must be in the range 0 to 255. The default is 128. 
clockClass
    The clockClass attribute of the local clock. It denotes the traceability of the time distributed by the grandmaster clock. The default is 248. 
clockAccuracy
    The clockAccuracy attribute of the local clock. It is used in the best master selection algorithm. The default is 0xFE. 
offsetScaledLogVariance
    The offsetScaledLogVariance attribute of the local clock. It characterizes the stability of the clock. The default is 0xFFFF. 
domainNumber
    The domain attribute of the local clock. The default is 0. 
free_running
    Don't adjust the local clock if enabled. The default is 0 (disabled). 
freq_est_interval
    The time interval over which is estimated the ratio of the local and peer clock frequencies. It is specified as a power of two in seconds. The default is 1 (2 seconds). 
assume_two_step
    Treat one-step responses as two-step if enabled. It is used to work around buggy 802.1AS switches. The default is 0 (disabled). 
tx_timestamp_retries
    The number of retries to fetch the tx time stamp from the kernel when a message is sent. The default is 100. 
clock_servo
    The servo which is used to synchronize the local clock. Currently only one servo is implemented, a PI controller. The default is pi. 
pi_proportional_const
    The proportional constant of the PI controller. When set to 0.0, the value will be selected from 0.7 and 0.1 for the hardware and software time stamping respectively. The default is 0.0. 
pi_integral_const
    The integral constant of the PI controller. When set to 0.0, the value will be selected from 0.3 and 0.001 for the hardware and software time stamping respectively. The default is 0.0. 
pi_offset_const
    The maximum offset the PI controller will correct by changing the clock frequency instead of stepping the clock. When set to 0.0, the controller will never step the clock. The default is 0.0. 
ptp_dst_mac
    The MAC address where should be PTP messages sent. Relevant only with L2 transport. The default is 01:1B:19:00:00:00. 
p2p_dst_mac
    The MAC address where should be peer delay messages the PTP peer. Relevant only with L2 transport. The default is 01:80:C2:00:00:0E. 
logging_level
    The maximum logging level of messages which should be printed. The default is 6 (LOG_INFO). 
verbose
    Print messages to the standard output if enabled. The default is 0 (disabled). 
use_syslog
    Print messages to the system log if enabled. The default is 1 (enabled). 
time_stamping
    The time stamping method. The allowed values are hardware, software and legacy. The default is hardware.
```

### default.cfg

```shell
[global]
#
# Default Data Set
#
twoStepFlag             1
slaveOnly               0
socket_priority         0
priority1               128
priority2               128
domainNumber            0
#utc_offset             37
clockClass              248
clockAccuracy           0xFE
offsetScaledLogVariance 0xFFFF
free_running            0
freq_est_interval       1
dscp_event              0
dscp_general            0
dataset_comparison      ieee1588
G.8275.defaultDS.localPriority  128
maxStepsRemoved         255
#
# Port Data Set
#
logAnnounceInterval     1
logSyncInterval         0
operLogSyncInterval     0
logMinDelayReqInterval  0
logMinPdelayReqInterval 0
operLogPdelayReqInterval 0
announceReceiptTimeout  3
syncReceiptTimeout      0
delayAsymmetry          0
fault_reset_interval    4
neighborPropDelayThresh 20000000
masterOnly              0
G.8275.portDS.localPriority     128
asCapable               auto
BMCA                    ptp
inhibit_announce        0
inhibit_delay_req       0
ignore_source_id        0
#
# Run time options
#
assume_two_step         0
logging_level           6
path_trace_enabled      0
follow_up_info          0
hybrid_e2e              0
inhibit_multicast_service       0
net_sync_monitor        0
tc_spanning_tree        0
tx_timestamp_timeout    1
unicast_listen          0
unicast_master_table    0
unicast_req_duration    3600
use_syslog              1
verbose                 0
summary_interval        0
kernel_leap             1
check_fup_sync          0
#
# Servo Options
#
pi_proportional_const   0.0
pi_integral_const       0.0
pi_proportional_scale   0.0
pi_proportional_exponent        -0.3
pi_proportional_norm_max        0.7
pi_integral_scale       0.0
pi_integral_exponent    0.4
pi_integral_norm_max    0.3
step_threshold          0.0
first_step_threshold    0.00002
max_frequency           900000000
clock_servo             pi
sanity_freq_limit       200000000
ntpshm_segment          0
msg_interval_request    0
servo_num_offset_values 10
servo_offset_threshold  0
write_phase_mode        0
#
# Transport options
#
transportSpecific       0x0
ptp_dst_mac             01:1B:19:00:00:00
p2p_dst_mac             01:80:C2:00:00:0E
udp_ttl                 1
udp6_scope              0x0E
uds_address             /var/run/ptp4l
#
# Default interface options
#
clock_type              OC
network_transport       UDPv4
delay_mechanism         E2E
time_stamping           hardware
tsproc_mode             filter
delay_filter            moving_median
delay_filter_length     10
egressLatency           0
ingressLatency          0
boundary_clock_jbod     0
#
# Clock description
#
productDescription      ;;
revisionData            ;;
manufacturerIdentity    00:00:00
userDescription         ;
timeSource              0xA0
```




# nxp运行vpp

## 初次运行

- 不带dpdk

```c
./vpp[1276]: clib_elf_parse_file: open `linux-vdso.so.1': No such file or directory
FASTGTPU_STUB_ENABLE unset (null)!!
use spin_lock to access mbuf share memory!
BH: SHMA(/tmp/bh0.shma) created: key 0x00162c1b shmid 2
BH: SHMA(/tmp/bh0.shma.m) created: key 0x00162c1d shmid 3
set fastgtpu_speed affinity with core[0]
#BH Warn: cpuid[27] is too large, should smaller than 16 on this system!
cuup_timer: Waring: sched_setaffinity failed.
Set cuup_timer affinity with core[27]
BH: SHMA(/tmp/rlc1.shma) created: key 0x00162c27 shmid 4
BH: SHMA(/tmp/rlc1.shma.m) created: key 0x00162c29 shmid 5
register gtpu send callback = 0xffff7d926a68 successful!
Meta is Available!
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: nat_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: lb_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: lacp_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: mactime_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: nsim_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: stn_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: avf_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: acl_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: nsh_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: cdp_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: memif_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: pppoe_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: ioam_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: gtpu_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: flowprobe_test_plugin.so
./vpp[1276]: load_one_vat_plugin:67: Loaded plugin: vmxnet3_test_plugin.so
BH: Set cuup_dispatcher affinity with Core[0]
BH: Set bh-worker0 affinity with Core[15]
2021/07/06 UTC 04:45:10.876997 cuup[1276] ERROR 0 sendto() failed 2 (No such file or directory)
./vpp[1276]: CRITICAL 0 odsServer.cc:120 sendto() failed 2 (No such file or directory)
cuup_timer is successful!
```

运行成功，但存在如下报错：

1. BH Warn: cpuid[27] is too large, should smaller than 16 on this system!

目前暂不清楚该日志由何处打印

2. cuup_timer: Waring: sched_setaffinity failed.

3. 2021/07/06 UTC 04:45:10.876997 cuup[1276] ERROR 0 sendto() failed 2 (No such file or directory)

4. ./vpp[1276]: CRITICAL 0 odsServer.cc:120 sendto() failed 2 (No such file or directory)

- 带dpdk

nxp板子默认配置了四个尺寸的大页，但vpp运行加载dpdk插件时，最多支持读取三个尺寸的大页，导致在nxp板子上运行支持dpdk插件的vpp启动失败，无法获取到大页内存信息。

解决方法：

1. 修改dpdk源码，取消只读取三个尺寸大页的限制，具体为修改lib/librte_eal/common/eal_internal_cfg.h

```c
#define MAX_HUGEPAGE_SIZES 3  /**< support up to 3 page sizes */
```

将上述代码中的3修改为大于3的值。

### vpp配置

- 环境设置

- dpdk资源配置

  - default

    ```shell
    root@HX-Technical-A:~/tools# restool dprc show dprc.2
    dprc.2 contains 25 objects:
    object          label           plugged-state
    dpni.4                          plugged
    dpbp.7                          plugged
    dpbp.6                          plugged
    dpbp.5                          plugged
    dpbp.4                          plugged
    dpci.1                          plugged
    dpci.0                          plugged
    dpseci.8                        plugged
    dpseci.7                        plugged
    dpseci.6                        plugged
    dpseci.5                        plugged
    dpseci.4                        plugged
    dpseci.3                        plugged
    dpseci.2                        plugged
    dpseci.1                        plugged
    dpdmai.1                        plugged
    dpdmai.0                        plugged
    dpmcp.39                        plugged
    dpio.19                         plugged
    dpio.18                         plugged
    dpio.17                         plugged
    dpio.16                         plugged
    dpcon.66                        plugged
    dpcon.65                        plugged
    dpcon.64                        plugged
    
    export DPCON_COUNT=3
    export DPBP_COUNT=4
    export DPMCP_COUNT=1
    export DPSECI_COUNT=8
    export DPIO_COUNT=4
    export DPCI_COUNT=2
    export DPDMAI_COUNT=2
    ```

    

  ```shell
  export ROOT_DPRC=dprc.1
  export PARENT_DPRC=dprc.2
  
  export DPCON_COUNT=3
  export DPBP_COUNT=4
  export DPMCP_COUNT=1
  export DPSECI_COUNT=8
  export DPIO_COUNT=4
  export DPCI_COUNT=2
  export DPDMAI_COUNT=2
  echo 1024 > /proc/sys/vm/nr_hugepages
  echo 0 > /proc/sys/vm/swappiness
  export DPRC=dprc.2
  ```

- vpp 配置

  ```shell
  #!/bin/bash
  #rm -rf /mnt/hugepages
  #mkdir -p /mnt/hugepages
  #mount -t hugetlbfs none /mnt/hugepages
  echo 6 > /proc/sys/vm/nr_hugepages
  echo 0 > /proc/sys/vm/swappiness
  export LD_LIBRARY_PATH=/root/vpp/lib
  export PATH=/root/vpp/bin:$PATH
  groupadd -f -r vpp
  ```

- startup.conf

  ```shell
  heapsize 256M
  plugin_path /root/vpp/lib/vpp_plugins
  
  unix {
    interactive
    #nodaemon
    gid vpp
    log /tmp/vpp.log
    full-coredump
    cli-listen /run/vpp/cli.sock
    #startup-config /etc/vpp/interface.txt
  }
  
  api-trace {
    on
  }
  
  api-segment {
    gid vpp
  }
  
  session {
    evt_qs_memfd_seg
  }
  
  socksvr {
    socket-name /tmp/vpp-api.sock
  }
  
  cpu {
  	main-core 1
  	corelist-workers 3
  }
  
  dpdk {
          ## Change default settings for all intefaces
          huge-dir /mnt/hugepages
          no-pci
          num-mem-channels 1
           dev default {
                  ## Number of receive queues, enables RSS
                  ## Default is 1
                  num-rx-queues 1
  				num-rx-desc 8912
                  # rss { ipv4 }
  
                  ## Number of transmit queues, Default is equal
                  ## to number of worker threads or 1 if no workers treads
                  num-tx-queues 1
  	}
  	proc-type primary
          #log-level  8
  }
  
  plugins {
          ## Adjusting the plugin path depending on where the VPP plugins are
          path /root/vpp/lib/vpp_plugins
          vat-path /root/vpp/lib/vpp_api_test_plugins
  
          plugin default { enable }
          plugin gtpu_plugin.so { disable }
          #plugin fastgtpu_plugin.so { disable }
  
  }
  ```
  
- interface.txt

  - 转发

    ```shell
    set int state TenGigabitEthernet0 up
    set int ip address TenGigabitEthernet0 192.168.8.24/24
    set int ip address TenGigabitEthernet0 192.168.9.24/24
    set interface mac address TenGigabitEthernet0 42:4b:54:ae:6e:05
    set int mtu 1500 TenGigabitEthernet0
    set ip arp static TenGigabitEthernet0 192.168.8.25 90:e2:ba:8d:02:f0
    ```

  - libup

    - netmask 16

    ```shell
    set int state TenGigabitEthernet0 up
    set int ip address TenGigabitEthernet0 192.168.8.25/16
    set interface mac address TenGigabitEthernet0 42:4b:54:ae:6e:05
    set int mtu 1500 TenGigabitEthernet0
    ```


  <font color="red">使用fastup时（加载fastgtpu插件），需要注意ip应在同一网络中以保证联通。</font>

  如使用pktgen进行报文回放时，因报文中源ip为192.168.9.243，目的ip为192.168.8.25，为保证网络联通，在vpp侧设置IP时应将子网掩码设置为16。

### 调试

```shell
# 从dpdk-input跟踪1个报文的轨迹
trace add dpdk-input 1
# 展示表格
show trace
```

```shell
00:02:51:352581: dpdk-input
  TenGigabitEthernet0 rx queue 0
  buffer 0x9be79: current data 0, length 1486, free-list 0, clone-count 0, totlen-nifb 0, trace 0x0
                  ext-hdr-valid
                  l4-cksum-computed l4-cksum-correct
  PKT MBUF: port 0, nb_segs 1, pkt_len 1486
    buf_len 2176, data_len 1486, ol_flags 0x2, data_off 128, phys_addr 0x9d4f9ec0
    packet_type 0x611 l2_len 0 l3_len 0 outer_l2_len 0 outer_l3_len 0
    rss 0xcb1c70c9 fdir.hi 0x0 fdir.lo 0xcb1c70c9
    Packet Offload Flags
      PKT_RX_RSS_HASH (0x0002) RX packet with RSS hash result
    Packet Types
      RTE_PTYPE_L2_ETHER (0x0001) Ethernet packet
      RTE_PTYPE_L3_IPV4 (0x0010) IPv4 packet without extension headers
      RTE_PTYPE_L4_NONFRAG (0x0600) Non-fragmented IP packet
  IP4: 90:e2:ba:8d:02:f0 -> 42:4b:54:ae:6e:05
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xf304
    fragment id 0xaecb, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:02:51:352606: ethernet-input
  frame: flags 0x3, hw-if-index 1, sw-if-index 1
  IP4: 90:e2:ba:8d:02:f0 -> 42:4b:54:ae:6e:05
00:02:51:352614: ip4-input-no-checksum
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xf304
    fragment id 0xaecb, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:02:51:352623: ip4-lookup
  fib 0 dpo-idx 5 flow hash: 0x00000000
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xf304
    fragment id 0xaecb, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:02:51:352629: ip4-local
    UDP: 192.168.9.243 -> 192.168.8.25
      tos 0x00, ttl 64, length 1472, checksum 0xf304
 fragment id 0xaecb, flags DONT_FRAGMENT
    UDP: 2152 -> 2152
      length 1452, checksum 0x991a
00:02:51:352635: ip4-drop
    UDP: 192.168.9.243 -> 192.168.8.25
      tos 0x00, ttl 64, length 1472, checksum 0xf304
      fragment id 0xaecb, flags DONT_FRAGMENT
    UDP: 2152 -> 2152
      length 1452, checksum 0x991a
00:02:51:352641: error-drop
  ip4-input: ip4 source lookup miss
```

```shell
vpp -localExtGnbNgUpAddr 192.168.8.25  -pdcpCoreIpAddress 192.0.2.2 -cellNumber 1 -l2IpAddress1 192.0.2.10 -loglevel 6 -log_max_num 10 -c  /etc/vpp/startup.conf

------------------- Start of thread 0 vpp_main -------------------
Packet 1

00:00:50:840492: dpdk-input
  TenGigabitEthernet0 rx queue 0
  buffer 0x9c04d: current data 0, length 1486, free-list 0, clone-count 0, totlen-nifb 0, trace 0x0
                  ext-hdr-valid
                  l4-cksum-computed l4-cksum-correct
  PKT MBUF: port 0, nb_segs 1, pkt_len 1486
    buf_len 2176, data_len 1486, ol_flags 0x2, data_off 128, phys_addr 0xa63013c0
    packet_type 0x611 l2_len 0 l3_len 0 outer_l2_len 0 outer_l3_len 0
    rss 0xcb1c70c9 fdir.hi 0x0 fdir.lo 0xcb1c70c9
    Packet Offload Flags
      PKT_RX_RSS_HASH (0x0002) RX packet with RSS hash result
    Packet Types
      RTE_PTYPE_L2_ETHER (0x0001) Ethernet packet
      RTE_PTYPE_L3_IPV4 (0x0010) IPv4 packet without extension headers
      RTE_PTYPE_L4_NONFRAG (0x0600) Non-fragmented IP packet
  IP4: 90:e2:ba:8d:02:f0 -> 42:4b:54:ae:6e:05
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xef41
    fragment id 0xb28e, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:00:50:840508: ethernet-input
  frame: flags 0x3, hw-if-index 1, sw-if-index 1
  IP4: 90:e2:ba:8d:02:f0 -> 42:4b:54:ae:6e:05
00:00:50:840521: ip4-input-no-checksum
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xef41
    fragment id 0xb28e, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:00:50:840533: ip4-lookup
  fib 0 dpo-idx 5 flow hash: 0x00000000
  UDP: 192.168.9.243 -> 192.168.8.25
    tos 0x00, ttl 64, length 1472, checksum 0xef41
    fragment id 0xb28e, flags DONT_FRAGMENT
  UDP: 2152 -> 2152
    length 1452, checksum 0x991a
00:00:50:840549: ip4-local
    UDP: 192.168.9.243 -> 192.168.8.25
      tos 0x00, ttl 64, length 1472, checksum 0xef41
      fragment id 0xb28e, flags DONT_FRAGMENT
    UDP: 2152 -> 2152
      length 1452, checksum 0x991a
00:00:50:840554: ip4-drop
    UDP: 192.168.9.243 -> 192.168.8.25
      tos 0x00, ttl 64, length 1472, checksum 0xef41
      fragment id 0xb28e, flags DONT_FRAGMENT
    UDP: 2152 -> 2152
      length 1452, checksum 0x991a
00:00:50:840561: error-drop
  ip4-input: ip4 source lookup miss
```

#### 抓包

```shell
 # 抓包
pcap tx trace status
pcap tx trace on max 1000 intfc TenGigabitEthernet0 file vppTest.pcap
pcap tx trace status
pcap tx trace off
   # 写入的位置位于/tmp，不能指定文件夹，旧的会被新的同名文件覆盖。pcap dispatch trace off后pcap包将截止。包文件为vppcapture
pcap rx trace status
pcap rx trace on max 1000 intfc TenGigabitEthernet0 file vppTest.pcap
pcap rx trace status
pcap rx trace off
```

#### 启动时丢包

```shell

    tx frames ok                                     2423618
    tx bytes ok                                   3601496348
    rx frames ok                                     2423623
    rx bytes ok                                   3601496898
    rx errors                                            126
    extended stats:
      rx good packets                                2423623
      tx good packets                                2423618
      rx good bytes                               3601496898
      tx good bytes                               3601496348
      rx errors                                          126
      rx q0packets                                   2423618
      rx q1packets                                         5
      tx q0packets                                   2423618
      ingress multicast frames                             5
      ingress multicast bytes                            550
      ingress discarded frames                           126
      cgr reject frames                                  126
      cgr reject bytes                                187236

```

丢包在rx-errors，进一步定位丢包在dpdk的ierror是。

- 使用dpdk进行转发无丢包
  - 说明性能没有问题，某个参数没有最优
- 使用vpp在刚启动时丢包

#### 原因

dpdk的rx ring过小，导致刚启动时流量过大无法将包全部收上来。<font color="red">修改vpp启动文件中dpdk的rx ring大小可解决丢包。</font>

在startup.conf文件中设置num-rx-desc，默认值为1024，按实际测试情况：

```shell
dev default {
                ## Number of receive queues, enables RSS
                ## Default is 1
                num-rx-queues 1
                # dpdk rx ring size
                num-rx-desc 8912

                # rss { ipv4 }
                ## to number of worker threads or 1 if no workers treads
                num-tx-queues 1
}
```

##### 无回调

- 1g线速1024大小不丢包
- 5g线速4096大小不丢包
- 10g线速8912大小不丢包

##### 有回调

- 5g线速8192大小不丢包
- 6g线速40960大小不丢包
- 7g线速40960会出现rx-miss

```shell
vpp# show interface
              Name               Idx    State  MTU (L3/IP4/IP6/MPLS)     Counter          Count
TenGigabitEthernet0               1      up          1500/0/0/0     rx packets             111049438
                                                                    rx bytes            165019456612
                                                                    drops                          6
                                                                    ip4                    111049432
                                                                    rx-miss                  1672902
local0                            0     down          0/0/0/0

```

rx-miss表示网卡收到了包，表示rte_rx_queue已经塞满了数据包，所以该包被丢失。此时该包存在于物理网卡的RX FIFO中，但是不会存在于内存中的rte_rx_queue中。

rx-miss表示从网卡到内存写入数据包时的丢包个数，因此需要从以下2个方面进行调试：

-  PCIe是否存在瓶颈
- rte_rx_queue中的数据包没有及时消费掉
  1. 检查cpu运行模式，如果当前运行在powersave模式下，可以将其修改为performance，提升CPU频率
  2. 程序性能不佳，无法及时消耗掉rte_rx_queue中的数据包

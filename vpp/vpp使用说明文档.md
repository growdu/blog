# vpp使用说明文档

先将vpp_arm64.tar.gz复制到目标机器上进行解压，解压后的目录结构如下：

```shell
root@localhost-Technical-B:~/vpp/vpp# ls
bin  dpaa2  vpp_readme  include  install.sh  kmod  lib  share  startup.conf  usertools  vpp_papi-1.6.2-py2.7.egg
```

首先阅读vpp_readme，可根据该文档进行安装。

安装时需要运行install.sh脚本，该脚本主要把该目录下的文件拷贝到目的安装路径，并设置环境变量。使用如下命令进行安装：

```shell
chmod +x install.sh
./install.sh /mnt/
```

## 环境准备

### 绑定dpdk网口

```shell
dynamic_dpl.sh dpmac.4
export DPRC=dprc.2
```

## 驱动模块加载

- 若需要开启kni功能，则需要加载rte_kni.ko模块，使用如下命令加载：

  ```shell
  insmod rte_kni.ko carrier=on
  ```

  需要注意的是carrier=on在dpdk18.05版本后不能省略，因为dpdk18.05版本后carrier默认为off。

- 若不需要开启kni功能，则需要确保rte_kni.ko模块已经被卸载

  使用如下命令查看rte_kni.ko是否存在

  ```shell
  lsmod | grep rte_kni
  ```

  若存在则使用如下命令进行卸载：

  ```shell
  rmmod rte_kni
  ```

## vpp配置文件

vpp配置文件与vpp配置一致，可直接参考vpp startup.conf相关配置（包括kni）。

- 线程参数

  ```shell
  cpu {
          main-core 4
          corelist-workers 5
  }
  ```

  一般使用一个main线程和一个worker线程。

- dpdk参数

  ```shell
  dpdk {
          ## Change default settings for all intefaces
          huge-dir /mnt/hugepages
          no-pci
          num-mem-channels 1
          # kni count
          #kni 1
           dev default {
                  ## Number of receive queues, enables RSS
                  ## Default is 1
                  num-rx-queues 1
                  num-rx-desc 40960
                  #num-rx-desc 65536
                  rss { ipv4 }
  
                  ## Number of transmit queues, Default is equal
                  ## to number of worker threads or 1 if no workers treads
                  num-tx-queues 1
          }
          proc-type primary
          log-level 7
  }
  
  ```

  其中需要特别留意的是num-rx-desc，该值是dpdk的环形收包缓冲区大小，若设置过小会导致dpdk丢包。按当前测试结果来看40960为最优值，若大流量时出现大量rx-errors可适当增大该值。

  另外若需要启用kni功能，直接在dpdk配置中添加

  ```shell
  kni count
  ```

  即可，其中count是要支持kni的网口个数。kni网口个数依赖于实际的物理网口个数，kni个数无法超过实际物理网口个数。即kni是与物理网口一一对应的。

- 插件参数

  ```shell
  plugins {
          ## Adjusting the plugin path depending on where the VPP plugins are
          path /path/lib/vpp_plugins
          vat-path /path/lib/vpp_api_test_plugins
  
          plugin default { enable }
          plugin gtpu_plugin.so { disable }
  }
  ```

  插件配置中需指明vpp_plugins的路径，另外需将原生的gtpu插件禁用。

## kni配置和使用

- 配置

  当启用kni功能时，对于一个物理网口来说，除vpp本身进行数据包处理外，还会在操作系统中虚拟出一个网口，一般命名为vEth0，其中0跟随kni个数增加。

  对于虚拟出来的网口可使用linux下的ifconfig、ethtool工具对其进行配置。可以将其当作正常的物理网口来使用。

- 查看

  查看kni统计信息，可直接使用vppctl工具。

  ```shell
  vpp# show int
                Name               Idx    State  MTU (L3/IP4/IP6/MPLS)     Counter          Count
  TenGigabitEthernet0               1      up          1500/0/0/0
  local0                            0     down          0/0/0/0
  ----------------------------------------------------------------------------------------------------
  vEth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 9216
          inet 121.168.1.12  netmask 255.255.255.0  broadcast 121.168.1.255
          inet6 fe80::b0c4:a3ff:feba:2ddf  prefixlen 64  scopeid 0x20<link>
          ether b2:c4:a3:ba:2d:df  txqueuelen 1000  (Ethernet)
          RX packets 8  bytes 708 (708.0 B)
          RX errors 0  dropped 0  overruns 0  frame 0
          TX packets 16  bytes 1364 (1.3 KB)
          TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
  ```

  ```shell
  vpp# show int addr
  TenGigabitEthernet0 (up):
    L3 192.168.8.25/16
  local0 (dn):
  ----------------------------------------------------------------------------------------------------
  vEth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 9216
          inet 121.168.1.12  netmask 255.255.255.0  broadcast 121.168.1.255
          inet6 fe80::b0c4:a3ff:feba:2ddf  prefixlen 64  scopeid 0x20<link>
          ether b2:c4:a3:ba:2d:df  txqueuelen 1000  (Ethernet)
          RX packets 0  bytes 0 (0.0 B)
          RX errors 0  dropped 0  overruns 0  frame 0
          TX packets 10  bytes 796 (796.0 B)
          TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0
  ```

- 分流

  分流是指需要决定一个报文是该送往kni经内核协议栈处理，还是该送往vpp由用户态协议栈处理。当前默认分流原则为GTPU报文送往用户态协议栈，非GTPU报文送往内核协议栈。因当前无其他分流策略，暂时不支持分流策略配置，均采用默认分流策略。

<font color="red">需要特别注意的是，当前kni和vpp可以配置相同的ip，也可以配置不同的ip。但kni和vpp的网口物理地址必须相同。</font>
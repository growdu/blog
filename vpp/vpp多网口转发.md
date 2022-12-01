# vpp多网口转发

vpp接管两个网口，当前需实现功能从网口1进来的流量由网口2发送出去。

## 二层转发

二层转发使用l2 bridge方式转发，需创建网桥。

vpp二层转发配置如下：

```shell
vpp# show int
              Name               Idx    State  MTU (L3/IP4/IP6/MPLS)     Counter          Count
vpp0               1      up          9000/0/0/0
vpp1               2      up          9000/0/0/0
local0                            0     down          0/0/0/0
vpp#set interface l2 bridge vpp0 100
vpp#set interface l2 bridge vpp1 100
vpp#l2fib add mac_addr 100 vpp0
vpp# show l2fib all
```

### 三层转发

三层转发需使用nat44功能，设置一张网口进，另一张网口出。

```shell
vpp# show int
              Name               Idx    State  MTU (L3/IP4/IP6/MPLS)     Counter          Count
vpp0               1      up          9000/0/0/0
vpp1               2      up          9000/0/0/0
local0                            0     down          0/0/0/0
vpp#set int ip address vpp0 192.168.1.12/24
vpp#set int ip address vpp1 172.168.1.12/24
vpp#ip route add 0.0.0.0/0 via 172.168.1.12 
vpp# nat44 add address 172.168.1.12
vpp# set int nat44 in vpp1 out vpp0
```

```shell
set interface mac address TenGigabitEthernet1 42:4b:54:ae:6e:05
set int ip address TenGigabitEthernet1 172.168.1.12/24
set int ip address TenGigabitEthernet0 192.168.8.25/24
ip route add 0.0.0.0/0 via 172.168.1.12
nat44 add address 172.168.1.12
set int nat44 in TenGigabitEthernet1 out TenGigabitEthernet0
```

cpub对外网口1接入，经ip层转发到cpub对内网口2，经ip层转发到cpua对内网口1进行业务逻辑处理。在cpub上未进行业务处理。

```shell
set int state TenGigabitEthernet0 up
set int state TenGigabitEthernet1 up
set interface mac address TenGigabitEthernet1 42:4b:54:ae:6e:05
set int ip address TenGigabitEthernet0 192.168.8.24/16
set int ip address TenGigabitEthernet1 172.168.1.12/24
set interface mac address TenGigabitEthernet0 92:51:e6:5c:01:d2
set ip arp static TenGigabitEthernet1 192.168.8.24 92:51:e6:5c:01:d2
set ip arp static TenGigabitEthernet0 192.168.8.25 92:51:e6:5c:01:00
set fastgtpu test ip dst 192.168.8.25
set fastgtpu test ip src 192.168.8.24
set fastgtpu test mode 3
```

cpub对外网口1接入，网口1先进行业务处理和分流，再将报文由cpub对内网口1发出，cpua对内网口1收包后进行业务处理。两个cpu都会进行业务处理。

```shell
set int state TenGigabitEthernet0 up
set int state TenGigabitEthernet1 up
set interface mac address TenGigabitEthernet1 42:4b:54:ae:6e:05
set int ip address TenGigabitEthernet0 172.168.8.24/16
set int ip address TenGigabitEthernet1 192.168.8.25/16
set interface mac address TenGigabitEthernet0 92:51:e6:5c:01:d2
set ip arp static TenGigabitEthernet0 172.168.8.25 92:51:e6:5c:01:00
set fastgtpu test ip dst 172.168.8.25
set fastgtpu test ip src 172.168.8.24
set fastgtpu test mode 3
start fastgtpu test
```


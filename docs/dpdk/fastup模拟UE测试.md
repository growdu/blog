# fastup模拟UE测试

## 测试流程

1. 在docker上启动模拟phy；
2. 在核心网机器启动核心网；
3. 在docker上启动模拟UE，并与核心网建立连接，创建用户，发送数据；
4. 抓取数据报文；（仅第一次需要抓取）
5. 使用另一个网口（当前为x86服务器网口）用pktgen回放上一步抓取的报文；
6. 报文成功回放到核心网，可以将模拟UE杀掉；（因为抓取的报文仅有一个UE id，模拟UE退出后，UE id不改变可一直回放报文）

先在同一个docker上启动模拟phy和模拟UE，同时抓下一个全流程的包，后续用于pktgen打流回放。

- 模拟phy

  ```shell
  # 10.252.1.180 root/123456 
  #启动docker
  docker start fastup_SimUE
  # 接入docker
  docker exec -it fastup_SimUE  /bin/bash
  cd testUE/
  source  venv/bin/activate
  cd test
  python3 test_simulator_gnb_phy.py
  ```
- 核心网

  ```shell
  # 先ssh 10.252.2.62 root/root 在ssh 114.168.1.12 root/root
  source /mnt/fastup/fastup_env.sh # 仅需要在该机器上执行一次，避免重复执行（重启后需重新执行）
  export FASTUP_SPEED_CORE=6
  sp.sh
  #切换核心网到分离模式
  #修改/opt/bbu/oam/cm 下的protStackCfg.sh
  ```

- 模拟UE

  模拟用于主要用于激活用户和抓取回放报文。

  ```shell
  # 启动docker
  #docker start fastup_SimUE
  # 接入docker
  docker exec -it fastup_SimUE  /bin/bash
  cd testUE/
  source  venv/bin/activate
  cd test
  python3 test_simulator_ue.py
  ```

  当出现

- 查看UE状态及核心网数据

  ```shell
  # 先ssh 10.252.2.62 root/root 在ssh 114.168.1.12 root/root
  # 查看phy是否正常
  cli -n cucpgnb served-cell-list
  # 查看UE连接情况
  cli -q -n ducell0 display-ue-info
  # 查看协议栈端流量情况
  watch -n 1 cli -n cuup net-stat
  ```
  
- pktgen

  ```shell
  ./app/x86_64-native-linuxapp-gcc/pktgen -c 0xe0000 --socket-mem 2048 -n 2 -- -P -m [18:19].0 -s 0:5gc_cdu.pcap -T --crc-strip
  ./app/x86_64-native-linuxapp-gcc/pktgen -c 0xe0000 --socket-mem 2048 -n 2 -- -P -m [18:19].0 -s 0:5gc.pcap -T --crc-strip
  ```

## 测试结果

- 丢包

  **ingress discarded frames**

  ```shell
      rx errors                                              3
      extended stats:
        rx good packets                               57737810
        rx good bytes                              87184063700
        rx errors                                            3
        rx q0packets                                  57737810
        ingress multicast frames                            21
        ingress multicast bytes                           2310
        ingress discarded frames                             3
  ```

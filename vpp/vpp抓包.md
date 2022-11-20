# vpp抓包

vpp支持抓包，对报文抓取后保存到文件中，并通过wireshark分析报文。

要进行抓包需要先进入vppctl，抓包分为rx和tx：

- tx

  ```shell
  # 查看tx 抓包状态
  vpp# pcap tx trace status
  max is 100 for any interface to file /tmp/vpe.pcap
  pcap tx capture is off...
  # 开启抓包
  # max 1000指定最多抓取1000个报文
  # intfc intface_name 指定抓取的网口
  # file vppTest.pcap指定抓包文件保存时的文件名，最终会保存在/tmp目录下
  vpp# pcap tx trace on max 1000 intfc intface_name file vppTest.pcap
  # 设置好后再查看一下tx的抓包状态
  vpp# pcap tx trace status
  max is 1000 for interface local0 to file /tmp/vppTest.pcap
  pcap tx capture is on: 48 of 1000 pkts..
  # 运行一段时间后，有报文收发即可停止抓包
  vpp# pcap tx trace off
  captured 48 pkts...
  saved to /tmp/vppTest.pcap...
  ```

- rx

  rx抓包与tx一致，将上面的tx换为rx即可。
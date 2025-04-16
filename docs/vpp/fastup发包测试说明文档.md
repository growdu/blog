# fastgtpu发包测试说明文档

# 背景

fastgtpu作为vpp的一个插件，只能被动收包，无法主动发包，需对其进行发包适配。

## fastgtpu主动发包

### 控制参数

- 发包模式

  共有三种发包模式：

  - 独立线程发包（速率可配置）
  - 独立线程1:1回包
  - 在fastgtpu线程中1:1回包

- 发包速率

  发包速率主要通过pps来控制。

- 发包控制

  可通过如下参数对发包进行控制：

  - 需要发送的总的包个数

    发送完后即停止

  - pps

    设置每秒发送的报文数

  - 报文包长

    设置每个报文的长度

  - 批量发包个数

    设置每一次将多少个包送到发送队列里面。

## 控制模型

```c
// 主动发包测试模式
enum fastgtpu_tx_debug_mode {
    TX_SIGNEL_THREAD_FULL = 1, // tx在独立线程中全力发包
    TX_SIGNEL_THREAD_ECHO =2,  // tx在独立线程中1:1回传报文
    TX_FASTGTPU_THREAD_ECHO =3 // tx在fastgtpu线程中1:1回传报文
};

// 主动发包控制结构
struct fastgtpu_tx_debug_t {
    enum fastgtpu_tx_debug_mode mode;
    uint64_t rx_count; // 收到的报文数
    uint64_t tx_count; // 已经发送的报文数
    uint64_t tx_plan_count; // 全量发包计划发送的报文数，到达此值时停止发送
    uint64_t pps;   // 发包速率，按pps算
    uint32_t length; // 报文长度
    uint8_t  run_flag; // 运行标志，1 运行；0 停止
    uint32_t bulk_count; // 全量发包时批量发包个数
    ip4_address_t src_addr4;
    ip4_address_t dst_addr4;
};


```

## 配置

启动时可在startup.conf启动文件中添加fastgtpu配置模块，进行参数配置和功能开启。配置样例如下：

```shell
fastgtpu {
		# 发送模式，取值1,2,3;
		# 1 独立线程发包（速率可配置）
		# 2 独立线程1:1回包
		# 3 在fastgtpu线程中1:1回包
        tx-debug-mode 1
        # 发送的总报文，值为2的幂次方
        # 30表示要发送2^30个报文
        tx-debug-send 30
        # 批量发包的个数
        # 20表示每次发包发送20个报文
        tx-debug-bulk-count 20
        # 设置报文发送速率
        # 如800000表示每秒发送800000个报文
        tx-debug-pps 800000
        # 设置报文长度
        tx-debug-length 1000
        # 发送队列大小，值为2的幂次方
        # 如20表示发送队列大小为2^20
        tx-queue 20
        # 报文是否送往运用层，配置该参数后收到报文直接丢弃，不做任何处理
        tx-to-application-off
}
```

## cli

可以通过vppctl发送命令对发包测试进行控制。

- 启动发包

  ```shell
  vpp# start fastgtpu test
  ```

- 停止发包

  ```shell
  vpp# stop fastgtpu test
  ```

- 设置速率

  ```shell
  vpp# set fastgtpu test pps 1000
  ```

- 设置包长

  <font color="red">若未设置报文长度，默认为1460.（报文长度设置暂未实现）</font>

  ```shell
  vpp# set fastgtpu test length 1000
  ```

- 设置发送模式

  ```shell
  vpp# set fastgtpu test mode 2
  ```

- 设置发包测试源ip

  ```shell
  vpp# set fastgtpu ip src <ip>
  ```

- 设置发包测试目的ip

  ```shell
  vpp# set fastgtpu ip dst <ip>
  ```

- 查看包长、速率、收发包

  ```shell
  vpp# show fastgtpu stats
  ```

- 清楚收发包等统计信息

  ```shell
  vpp# clear fastgtpu
  ```

  

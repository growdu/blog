# 流复制心跳超时问题

## 基本概念

- walsender 主库数据发送进程
- walreceiver 备库数据接收进程

## 问题现象

在当前流复制过程中，当walreceiver进程在收到大量数据报文时会出现walsender因keepalive心跳报文超时而导致流复制断开。

### 原因分析

当数据报文较多时，walreceiver可能因收包或写入时间过长而导致回复keepalive报文不及时。

### 期望表现

当数据报文较多，walreceiver卡在处理数据报文时，仍然能回复心跳。

## keepalive机制分析

流复制的大致流程如下：

1. 主库启动，主库监听相应的端口，并等待备库的连接；
2. 备库启动，并与主库监听的端口建立tcp连接，与主库同步wal日志状态，并发送流复制请求；
3. 主备库建立连接后便开始数据传输，在数据传输的同时，主库会定时发送keepalive来检查备库的状态，备库收到keepalive报文后需进行回复；主库在超时时间内收到keepalive的回复后会重新计算下一次心跳报文的发送时间，若主库未在超时时间内收到keepalive回复报文则认为备库处理超时，会进行拆链；

### walsender心跳发送机制

walsender通过wal_sender_timeout确认keepalive超时时间，默认为60s。其生效机制如下：

1. 若收到walreceiver回复的报文，不论是keepalive报文还是数据文本，均会更新last_reply_time;
2. 当last_reply_time与当前时间间隔达到wal_sender_timeout的一半时（默认为30s），walsender会发送keepalive报文；
3. 当last_reply_time与当前时间间隔达到wal_sender_timeout值时，walsender认为walreceiver处理超时，将会断开流复制；

### walreceiver心跳发送机制

- 收到心跳报文
  
  walreceiver收到心跳报文后，会立马回复心跳报文，且不存在写入操作。

- 收到数据报文
  
  walreceiver收到数据报文后，会在将socket的buffer缓冲区内的数据接收处理完成后回复reply报文，wlasender收到这种报文回复后同样可以重置walsender的last_reply_time;

- 主动发送reply报文
  
  当walreceiver在wal_receiver_timeout/2时间内没有收到walsender的心跳报文或者数据报文，walreceiver也会主动发送reply报文，并需要walsender回复。
  
  同样的walreceiver在wal_receiver_timeout时间内没有收到walsender的心跳报文或者数据报文，walreceiver会认为walsender超时而断开连接。

### walreceiver报文接收回复及其实现

```c
                /* See if we can read data immediately */
                len = walrcv_receive(wrconn, &buf, &wait_fd);
                if (len != 0)
                {
                    /*
                     * Process the received data, and any subsequent data we
                     * can read without blocking.
                     */
                    for (;;)
                    {
                        if (len > 0)
                        {
                            /*
                             * Something was received from primary, so reset
                             * timeout
                             */
                            last_recv_timestamp = GetCurrentTimestamp();
                            ping_sent = false;
                            XLogWalRcvProcessMsg(buf[0], &buf[1], len - 1,
                                                 startpointTLI);
                        }
                        else if (len == 0)
                            break;
                        else if (len < 0)
                        {
                            ereport(LOG,
                                    (errmsg("replication terminated by primary server"),
                                     errdetail("End of WAL reached on timeline %u at %X/%X.",
                                               startpointTLI,
                                               LSN_FORMAT_ARGS(LogstreamResult.Write))));
                            endofwal = true;
                            break;
                        }
                        len = walrcv_receive(wrconn, &buf, &wait_fd);
                    }

                    /* Let the primary know that we received some data. */
                    XLogWalRcvSendReply(false, false);

                    /*
                     * If we've written some records, flush them to disk and
                     * let the startup process and primary server know about
                     * them.
                     */
                    XLogWalRcvFlush(false, startpointTLI);
```

​     
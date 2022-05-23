# 缩短tcp超时时间的方法

在tcp链路中，当网络异常时，缩短tcp超时时间一般有如下方法：

- TCP_USER_TIMEOUT(需要内核2.6.37及其以上版本)
- SIOCOUTQ
- tcp_retries2

## TCP_USER_TIMEOUT

需要内核2.6.37及其以上版本才支持该选项。

>TCP_USER_TIMEOUT选项是TCP层的socket选项，选项接受unsigned int类型的值。值为数据包被发送后未接收到ACK确认的最大时长，以毫秒为单位，例如设置为10000时，代表如果发送出去的数据包在十秒内未收到ACK确认，则下一次调用send或者recv，则函数会返回-1，errno设置为ETIMEOUT，代表connection timeout。

```c
unsigned int timeout = 10000;
if (-1 == setsockopt(fd, IPPROTO_TCP, TCP_USER_TIMEOUT, &timeout, sizeof(timeout))) {
    fprintf(stderror, "set TCP_USER_TIMEOUT option error: %s", strerror(errno));
}
```

## SIOCOUTQ

> linux提供了ioctl(fd, SIOCOUTQ, &count)方法来查询一个tcp socket的write buffer是否清空。发送方一般可以用这个方法来判断对端是否收到报文。当底层网卡将缓冲区的数据全部发送成功时，获取的count=0.

```c
#include <sys/ioctl.h>
 
#include <linux/sockios.h>
 
int value;
 
ioctl(client_fd,SIOCOUTQ,&value);
```

## tcp_retries2

> 在丢弃激活(已建立通讯状况)的TCP连接之前﹐需要进行多少次重试。默认值为15，根据RTO的值来决定，相当于13-30分钟(RFC1122规定，必须大于100秒).(这个值根据目前的网络设置,可以适当地改小,我的网络内修改为了5)

```c
int name[] = {CTL_NET, NET_IPV4, NET_IPV4_TCP_RETRIES2};
long value = 0;
size_t size = sizeof(value);
if(!sysctl(name, sizeof(name)/sizeof(name[0]), &value, &size, NULL, 0) {
  value // It contains current value from /proc/sys/net/ipv4/tcp_retries2
}
value = ... // Change value if it needed
if(!sysctl(name, sizeof(name)/sizeof(name[0]), NULL, NULL, &value, size) {
  // Value in /proc/sys/net/ipv4/tcp_retries2 changed successfully
}
```

<font color="red">需要特别留意的是tcp_retries2针对的是系统上的所有链路。</font>

## reference

1. https://stackoverflow.com/questions/5907527/application-control-of-tcp-retransmission-on-linux/5907951#5907951
2. https://blog.csdn.net/thwack/article/details/79960935
3. https://developer.aliyun.com/article/840000

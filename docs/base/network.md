

# 网络

## 1 常用网络服务

|服务|软件|
|:--|:--|
|DHCP 服务器|dhcpd|
|邮件发送服务器|sendmail|
|邮件列表服务器|mailman|
|接收邮件的服务器|pop3|
|web 站点|apache/nginx|
|防火墙服务|iptables 工具配置 netfilter|

## 2 网路诊断

逐步检查网络的各个层次：物理链接、链路层、网络层直到应用层，熟悉使用各种如下的工具，包括 

* ethereal/tcpdump
* hping
* nmap
* netstat
* netpipe
* netperf
* vnstat
* ntop

## 3 网络开发

|功能|工具|
|:--|:--|
|客户端/服务器架构|socket 编程|
|数据包抓获和协议分析|libpap 等函数库|
|实现某个协议|参考相关的 RFC 文档，并通过 socket 编程来实现|

### 3.1 linux网络编程步骤

#### 3.1.1 创建套接字

通过 ip地址 可以确定目标主机，通过端口号可以将数据准确地交给目标程序，而 ip地址:端口号 就是我们所说的 套接字。

套接字的创建通过函数 socket ，该函数需要包含头文件 `<sys/types.h>` 和 `<sys/socket.h>` ，该函数的声明为：

```C
//作用：创建一个套接字
//参数：
//   domain : 指定通讯协议族，常用的有 ：
//      AF_INET(IPv4通讯)
//      AF_INET6(IPv6通讯)
//      AF_LOCAL(本地通讯)
//   type : 常用的有 ：
//      SOCK_STREAM(有序、可靠、双向、基于连接的字节流，即TCP)
//      SOCK_DGRAM(无连接、不可靠数据报，即UDP)
//   protocol : 通常取0
//返回值
//   成功 : 返回新创建的套接字文件描述符
//   失败 : 返回 -1，错误代码存于 errno 中，通过引入 <errno.h> 可以引入该变量
int socket(int domain, int type, int protocol)
```

```C
//建立TCP连接
int tcp_fd = socket(AF_INET , SOCK_STREAM , 0);
//建立UDP连接
int udp_fd = socket(AF_INET , SOCK_DGRAM , 0);
```

#### 3.1.2 TCP连接与通信

无论是tcp还是udp，第一步都需要创建套接字，而之后的操作差异较大，TCP在数据收发前，需要建立连接，而UDP不需要建立连接就可以收发数据。

* 建立TCP SERVER

1.通过 socket() 系统调用创建一个套接字；

2.使用 bind() 系统调用将所创建的套接字绑定到指定的端口上；

3.通过 listen() 将进行端口绑定的套接字进行端口侦听，使客户端能够连接；

4.通过 accept() 接受客户端的连接，该函数将会被阻塞，直至客户端连接上来；

5.数据收发 read / write；

会使用到的结构体：

```C
struct sockaddr_in{
    short sin_family;
    u_short sin_port;
    struct in_addr sin_addr;
    char sin_zero[8];
};
truct in_addr{
  unsigned long s_addr;
};
```

**注：**如果在bind绑定时，指定端口0，意味着由系统随机选择一个可用端口来绑定。

* 建立TCP client

1.通过 socket() 系统调用创建一个套接字；

2.通过 connect() 系统调用将创建的套接字连接到TCP服务器上；

3.数据收发；数据收发的方式有很多，其中最简单的方式是使用系统调用 read() 和 write() 进行数据收发；

#### 3.1.3 UDP连接与通信

DP并不是基于连接的数据通讯，也就是说UDP server 并不通过accept接收客户端的连接，而UDP client 也不通过 connect 连接到服务器。

* UDP server

1.创建套接字 (socket)

2.绑定端口 (bind)

3.数据通讯 (读read / 写write)

与TCP服务器相比，少了 listen 和 accept 两个过程，即建立连接的两个步骤。

* UDP client

1.创建套接字 (socket)

2.数据通讯 (读recvfrom / 写sendto)


## 3.2 java网络编程

Java的网络编程主要涉及到的内容是Socket编程，那么什么是Socket呢？简单地说，Socket，套接字，就是两台主机之间逻辑连接的端点。TPC/IP协议是传输层协议，主要解决数据如何在网络中传输，而HTTP是应用层协议，主要解决如何包装数据。Socket，本质上就是一组接口，是对TCP/IP协议的封装和应用(程序员层面上)。

Socket编程主要涉及到客户端和服务器端两个方面，首先是在服务器端创建一个服务器套接字(ServerSocket)，并把它附加到一个端口上，服务器从这个端口监听连接。端口号的范围是0到65536，但是0到1024是为特权服务保留的端口号，我们可以选择任意一个当前没有被其他进程使用的端口。

客户端请求与服务器进行连接的时候，根据服务器的域名或者IP地址，加上端口号，打开一个套接字。当服务器接受连接后，服务器和客户端之间的通信就像输入输出流一样进行操作。

### 3.2.1 创建连接

Java为TCP协议提供了两个类：Socket类和ServerSocket类。

一个Socket实例代表了TCP连接的一个客户端，而一个ServerSocket实例代表了TCP连接的一个服务器端，一般在TCP Socket编程中，客户端有多个，而服务器端只有一个，客户端TCP向服务器端TCP发送连接请求，服务器端的ServerSocket实例则监听来自客户端的TCP连接请求，并为每个请求创建新的Socket实例，由于服务端在调用accept（）等待客户端的连接请求时会阻塞，直到收到客户端发送的连接请求才会继续往下执行代码，因此要为每个Socket连接开启一个线程。

服务器端要同时处理ServerSocket实例和Socket实例，而客户端只需要使用Socket实例。另外，每个Socket实例会关联一个InputStream和OutputStream对象，我们通过将字节写入套接字的OutputStream来发送数据，并通过从InputStream来接收数据。

#### 3.2.1.1 使用ServerSocket创建TCP服务器

Java中能接收其他通信实体连接请求的类是ServerSocket，ServerSocket对象用于监听来自客户端Socket连接，如果没有连接，它将一直处于等待状态。 

ServerSocket包含一个监听来自客户端连接请求的方法。

* Socket accpet()

如果接收到一个客户端Socket的连接请求，该方法将返回一个与客户端Socket对应的Socket；否则该方法将一直处于等待状态，线程也被阻塞。

* ServerSocket(int port) 

用指定的端口port来创建一个ServerSocket。该端口应该有一个有效的端口整数值，即0~65535。

* ServerSocket(int port, int backlog) 

增加一个用来改变连接队列长度的参数backlog。

* ServerSocket(int port, int backlog, IntetAddress localAddr) 

在机器存在多个IP地址的情况下，允许通过localAddr参数来指定将ServerSocket绑定到指定的IP地址。

服务端的工作是建立一个通信终端，并被动地等待客户端的连接。典型的TCP服务端执行如下两步操作： 

1.创建一个ServerSocket实例并指定本地端口，用来监听客户端在该端口发送的TCP连接请求

2.重复执行

&emsp;&emsp;1）调用ServerSocket的accept（）方法以获取客户端连接，并通过其返回值创建一个Socket实例； 

&emsp;&emsp;2）为返回的Socket实例开启新的线程，并使用返回的Socket实例的I/O流与客户端通信；

&emsp;&emsp;3）通信完成后，使用Socket类的close（）方法关闭该客户端的套接字连接。

```java
//创建一个ServerSocket，用于监听客户端Socket的连接请求
ServerSocket ss = new ServerSocket(3000);
//采用循环不断地接收来自客户端的请求
while(true)
{
    //每当接收到客户端Socket的请求时，服务器也对应产生一个Socket
    Socket s = ss.accept();
    //下面就可以使用Socket进行通信了
    ...
}
```


### 3.2.2 使用socket进行通信

客户端通常可使用Socket的构造器来连接到指定服务器，Socket通常可使用如下两个构造器：

* Socket(InetAddress/String remoteAddress, int port) 

创建连接到指定远程主机、远程端口的Socket，该构造器没有指定本地地址、本地端口，默认使用本地主机的默认IP地址，默认使用系统动态指定的IP地址。

* Socket(InetAddress/String remoteAddress, int port, InetAddress localAddr, int localPort) 

创建连接到指定远程主机、远程端口的Socket，并指定本地IP地址和本地端口号，适用于本地主机有多个IP地址的情形。

客户端向服务器端发送连接请求后，就被动地等待服务器的响应。典型的TCP客户端要经过下面三步操作：

1.创建一个Socket实例：构造函数向指定的远程主机和端口建立一个TCP连接；

2.通过套接字的I/O流与服务端通信；

3.使用Socket类的close方法关闭连接。

```java
//创建连接到本机、30000端口的Socket
Socket s = new Socket("127.0.0.1", 3000);
//下面就可以使用Socket进行通信
...
```


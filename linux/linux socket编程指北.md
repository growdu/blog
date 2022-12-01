# linux socket编程指北

以下server和client的c代码均拷贝自[博客](https://blog.csdn.net/weixin_41249411/article/details/89060985)，详细内容请阅读[原文](https://blog.csdn.net/weixin_41249411/article/details/89060985)。在其上添加了错误码打印，修改了服务端ip和端口，并增加了makefile脚本。

## server

```c
/*serve_tcp.c*/
#include<stdio.h>
#include<sys/socket.h>
#include<netinet/in.h>
#include<stdlib.h>
#include<arpa/inet.h>
#include<unistd.h>
#include<string.h>
#include <netinet/ip.h>

int main(){
	//创建套接字
	int serv_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);

	//初始化socket元素
	struct sockaddr_in serv_addr;
	memset(&serv_addr, 0, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_addr.s_addr = inet_addr("192.168.140.132");
	serv_addr.sin_port = htons(8888);
	// 设置ip头部里的tos值或者DSCP值
    // 设置对应DSCP的16进制即可，注意DSCP只使用1byte的前6bit，最后2bit保留
	// 如0xe0的二进制为11100000，去掉最后的两个保留位位111000，对应的DSCP值为56
	unsigned char  service_type = 0xe0;
    if(setsockopt(serv_sock, SOL_IP/*IPPROTO_IP*/, IP_TOS, (void *)&service_type, sizeof(service_type)) < 0) {
            printf("setsockopt(IP_TOS) failed:\n");
    }
	//绑定文件描述符和服务器的ip和端口号
	bind(serv_sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr));

	//进入监听状态，等待用户发起请求
	listen(serv_sock, 20);
	//接受客户端请求
	//定义客户端的套接字，这里返回一个新的套接字，后面通信时，就用这个clnt_sock进行通信
	struct sockaddr_in clnt_addr;
	socklen_t clnt_addr_size = sizeof(clnt_addr);
	int clnt_sock = accept(serv_sock, (struct sockaddr*)&clnt_addr, &clnt_addr_size);

	//接收客户端数据，并相应
	char str[256];
	read(clnt_sock, str, sizeof(str));
	printf("client send: %s\n",str);
	strcat(str, "+ACK");
	write(clnt_sock, str, sizeof(str));

	//关闭套接字
	close(clnt_sock);
	close(serv_sock);

	return 0;
}
```

- makefile

```c
all:
	gcc -g server.c -o server
clean:
	rm -rf server
```



## client

```c
/*client_tcp.c*/
#include<stdio.h>
#include<string.h>
#include<stdlib.h>
#include<unistd.h>
#include<arpa/inet.h>
#include<sys/socket.h>
#include <errno.h>
#include <netinet/ip.h>

int main(){
	//创建套接字
	int sock = socket(AF_INET, SOCK_STREAM, 0);

	//服务器的ip为本地，端口号1234
	struct sockaddr_in serv_addr;
	memset(&serv_addr, 0, sizeof(serv_addr));
	serv_addr.sin_family = AF_INET;
	serv_addr.sin_addr.s_addr = inet_addr("192.168.140.132");
	serv_addr.sin_port = htons(8888);
    // 设置ip头部里的tos值或者DSCP值
    // 设置对应DSCP的16进制即可，注意DSCP只使用1byte的前6bit，最后2bit保留
	// 如0xe0的二进制为11100000，去掉最后的两个保留位位111000，对应的DSCP值为56
	unsigned char  service_type = 0xe0;
    if(setsockopt(sock, SOL_IP/*IPPROTO_IP*/, IP_TOS, (void *)&service_type, sizeof(service_type)) < 0) {
            printf("setsockopt(IP_TOS) failed:\n");
    }
	int ret = connect(sock, (struct sockaddr*)&serv_addr, sizeof(serv_addr));
    if (ret ) {
           printf("connect failed, errno is %d\n", errno);
           exit(0);
    }
	//发送并接收数据
	char buffer[40];
	printf("Please write:");
	scanf("%s", buffer);
	write(sock, buffer, sizeof(buffer));
	read(sock, buffer, sizeof(buffer) - 1);
	printf("Serve send: %s\n", buffer);

	//断开连接
	close(sock);

	return 0;
}
```

- makefile

```makefile
all:
	gcc -g client.c -o client
clean:
	rm -rf cleint
```

当需要设置QOS时，具体是设置ip头部里面的TOS或者DSCP值，可在创建socket成功后调用如下接口设置：

```c
    // 设置对应DSCP的16进制即可，注意DSCP只使用1byte的前6bit，最后2bit保留
    // 如0xe0的二进制为11100000，去掉最后的两个保留位位111000，对应的DSCP值为56
	unsigned char  service_type = 0xe0;
    if(setsockopt(serv_sock, SOL_IP/*IPPROTO_IP*/, IP_TOS, (void *)&service_type, sizeof(service_type)) < 0) {
            printf("setsockopt(IP_TOS) failed:\n");
    }
```

### 运行

```shell
#先运行服务端
./server
#再运行客户端
./client
```

<font color="red">注意：若客户端在连接过程中出现错误码为113的连接失败情况，需将防火墙关闭(使用localhost不会出现该问题)。如centos使用如下命令关闭：</font>

```shell
 systemctl stop firewalld.service
```

## ipv6

需要留意的是，基于ipv6地址创建的socket与基于ipv4创建的socket略有不同。具体为地址结构不同，创建socket的类型也不同。

```c
        //创建套接字
        int serv_sock = socket(PF_INET6, SOCK_STREAM, 0);
        int ret = 0;
        //初始化socket元素
        struct sockaddr_in6 my_addr;
        memset(&my_addr, 0, sizeof(my_addr));

        // ipv6
        my_addr.sin6_family = PF_INET6;
        my_addr.sin6_port = htons(8888);
        inet_pton(AF_INET6, "fe80::20c:29ff:fe52:ae87", &my_addr.sin6_addr);
        //setsockopt(serv_sock, SOL_SOCKET, SO_BINDTODEVICE, "ens33", sizeof("ens33"));
        unsigned char  service_type = 0xe0;
        if(setsockopt(serv_sock, IPPROTO_IP, IP_TOS, (void *)&service_type, sizeof(service_type)) < 0) {
            printf("setsockopt(IP_TOS) failed:\n");
        }
        //绑定文件描述符和服务器的ip和端口号
        ret = bind(serv_sock, (struct sockaddr*)&my_addr, sizeof(my_addr));
```

其他步骤与ipv4相同。

<font color="red">需特别注意的是：ipv6地址分为scope link和scope global两种。对于scope link的ipv6地址（一般为系统基于mac自动生成），在使用其绑定socket时，需要调用setsockopt绑定网口，否则无法成功创建socket。对于scope global的ipv6地址（一般手动用ifconfig创建）则无需绑定可直接使用。</font>

# reference

1. https://blog.csdn.net/weixin_41249411/article/details/89060985
2. https://www.cnblogs.com/qijunzifeng/p/13753185.html
3. https://blog.csdn.net/zhengxianghdu/article/details/14106167
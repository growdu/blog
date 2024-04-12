![](https://csdnimg.cn/release/blogv2/dist/pc/img/original.png)

[糖果墙](https://blog.csdn.net/qq_38505969 "糖果墙") ![](https://csdnimg.cn/release/blogv2/dist/pc/img/newCurrentTime2.png) 于 2023-11-14 01:58:11 发布

## `win10`实现非标（非445）端口访问`samba`服务

> 背景：
> 
> -   由于公司有需求，在某个高性能宿主机节点上起了`N`多个`Docker`容器，而每个容器内的`/usr1`下都挂载了独立的数据卷，这个数据卷还不是宿主机的数据卷，因此需要在每个服务中安装独立的`samba`服务。
>     
> -   `samba`服务的标准是**占用`445`和`139`端口**。容器中可以默认使用`445`和`139`端口，然后映射到**宿主机的随机端口**上，实现每个容器都能启动独立的`samba`服务而不冲突。
>     
> -   那么问题就抛给`windows`用户了，`windows`上面想访问某个`samba`服务，就需要在[资源管理器](https://so.csdn.net/so/search?q=%E8%B5%84%E6%BA%90%E7%AE%A1%E7%90%86%E5%99%A8&spm=1001.2101.3001.7020)地址中输入`\\ip\共享目录`，然后就能访问到这个`ip`对应的`445`端口上启动的`samba`服务了，可是一旦服务器上的`samba`服务没有启动在`445`端口，通过默认的`ip`和端口就访问不到`samba`服务了，因为`windows`上面访问`samba`服务是不能指定端口的，只能是`445`端口。
>     
> -   那如何通过`\\ip\共享目录`连接到非`445`端口启动的`samba`服务呢？
>     

解决办法如下：

### 1\. 启用`SMB 1.0`协议和`Telnet`功能

在控制面板>程序>启用或关闭`Windows`功能中启用`SMB 1.0`协议和`Telnet`功能，启用后提示，**需要重启电脑才能生效**，这里先不重启，等设置好端口转发以后再重启。

![image-20231114010123380](https://img-blog.csdnimg.cn/img_convert/496a9aa55a1e51b428cf7c42c31e8dd4.png)

![image-20231114010322636](https://img-blog.csdnimg.cn/img_convert/51327f18b22b86e772d772ef33a15afe.png)

-   启用`SMB 1.0`协议了后面才能修改通过端口转发访问到`samba`服务
    
-   启用`Telnet`功能是为了确认你的`samba`服务是否正常工作，输入如下命令进行确认
    
    ```bash
    telnet ip 端口
    ```
    
    如果没有报无法访问的错误，就表示`samba`服务工作正常
    

### 2\. 禁用`445`端口的默认服务

`win+r`输入`services.msc`，在服务列表中停止并禁用`Server`服务

![image-20231114011412905](https://img-blog.csdnimg.cn/img_convert/42f9c4a3e06e4bab6428db2f59b56d7c.png)

### 3\. 启动`IP`端口转发服务

`win+r`输入`services.msc`，在服务列表中启动`IP Helper`服务，并把启动类型设置成自动。

![image-20231114011539069](https://img-blog.csdnimg.cn/img_convert/480932dd9ed47429da504efbd56018ab.png)

### 4\. 设置`IP`端口转发规则

```bash
netsh interface portproxy add v4tov4 listenport=445 listenaddress=localhost connectport=目标端口 connectaddress=目标IP
```

例如我要把访问`127.0.0.1:445`的请求都转发到`192.168.3.116:446`，命令如下

```bash
netsh interface portproxy add v4tov4 listenport=445 listenaddress=localhost connectport=446 connectaddress=192.168.3.11
```

查看是否设置成功

```bash
netsh interface portproxy show all
```

![image-20231114012339209](https://img-blog.csdnimg.cn/img_convert/04f4ac9fb95637a8583e6ae4241fc996.png)

到此就设置完了，重启下电脑，让SMB 1.0协议和端口转发服务生效

### 5\. 验证`IP`端口转发规则是否生效

查看端口转发监听是否生效:

```bash
netstat -ano|findstr 445
```

只要显示不是`4`就是代表成功的意思，否则就是不成功。

![image-20231114012534117](https://img-blog.csdnimg.cn/img_convert/a9d834773204b6519ccf031281dc2925.png)

这里的`6180`是进程号，在任务管理器的服务一栏下可以看到这是`ip`端口转发服务对应的进程号

![image-20231114012617958](https://img-blog.csdnimg.cn/img_convert/ebf93fb3c6b3a639bf3d5cd2b03859a6.png)

### 6\. 连接共享服务

如果显示正确，资源管理器的地址栏输入`\\localhost`，就可以访问到`samba`服务器的共享目录了。

![image-20231114013005906](https://img-blog.csdnimg.cn/img_convert/a160607d8dc34e58a13b635c0d0f4025.png)

### 7\. 映射网络驱动器

如果能通过`\\localhost`访问到`samba`服务的文件了，那么可以进一步把这个地址映射网络驱动器，效果就是跟`C`盘、`D`盘这种系统盘一样方便地访问了，按照截图的步骤操作即可

![image-20231114013456006](https://img-blog.csdnimg.cn/img_convert/4221904a4076adc1186d17efaacd11b4.png)

![image-20231114013758059](https://img-blog.csdnimg.cn/img_convert/7d67e4969112a500b0fcfab20b1088f9.png)

![image-20231114013945884](https://img-blog.csdnimg.cn/img_convert/cca310382434b1731bfd279ef7ab0d8f.png)

### 8\. 参考`wiki`

[https://zhizhuo.blog.csdn.net/article/details/129491719](https://zhizhuo.blog.csdn.net/article/details/129491719)
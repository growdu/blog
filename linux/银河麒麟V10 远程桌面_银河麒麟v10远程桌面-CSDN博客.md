### 安装

```
yum install tigervnc-server tigervnc-server-module
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/4967717af6f54d44ae22430eb2c583c1.png)

创建配置文件

```
vi /etc/systemd/system/vncserver@.service
```

写入一下内容：

```
[Unit]
Description=Remote desktop service (VNC)
After=syslog.target network.target

[Service]
Type=forking
WorkingDirectory=/root
User=root
ExecStartPre=/bin/sh -c '/usr/bin/vncserver -kill %i > /dev/null 2>&1 || :'
ExecStart=/usr/bin/vncserver %i -geometry 1920x1080
ExecStop=/usr/bin/vncserver -kill %i

[Install]
WantedBy=multi-user.target
```

重新加载

```
systemctl daemon-reload
```

启动[VNC](https://so.csdn.net/so/search?q=VNC&spm=1001.2101.3001.7020)服务

```
systemctl start vncserver@:1.service
```

> `vncserver@:1`的`1`表示启动VNC桌面id，VNC默认端口为5900,`1`配置VNC启动的端口为：`5901`

查看启动状态

```
systemctl status vncserver@:1.service
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/e40c747872694f949b0517618eb6a28f.png?x-oss-process=image/watermark,type_d3F5LXplbmhlaQ,shadow_50,text_Q1NETiBAQ2xpdmVuX2tlbg==,size_20,color_FFFFFF,t_70,g_se,x_16)

设置VNC开机启动

```
systemctl enable vncserver@:1.service
```

### 设置VNC登录口令

运行命令然后输入口令，并且确认。

```
vncpasswd
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/8b82943f2c2e49129035b7a22377dc1d.png)

### 登录访问

下载VNC Windows客户端

-   **TigerVNC**: [https://github.com/TigerVNC/tigervnc/releases](https://github.com/TigerVNC/tigervnc/releases)

点击Release中的SourceForge链接：  
![在这里插入图片描述](https://img-blog.csdnimg.cn/f51b1b7b0f224271ba1c7b37d3656294.png?x-oss-process=image/watermark,type_d3F5LXplbmhlaQ,shadow_50,text_Q1NETiBAQ2xpdmVuX2tlbg==,size_20,color_FFFFFF,t_70,g_se,x_16)  
点击下载  
![在这里插入图片描述](https://img-blog.csdnimg.cn/b73404c9ce044e668f6208d937ab1d9b.png?x-oss-process=image/watermark,type_d3F5LXplbmhlaQ,shadow_50,text_Q1NETiBAQ2xpdmVuX2tlbg==,size_20,color_FFFFFF,t_70,g_se,x_16)

TigerVNC为免安装软件，下载后双击启动即可。

![在这里插入图片描述](https://img-blog.csdnimg.cn/e0557fde178846f38e1d216e91e004d2.png)  
输入IP和端口，点击连接，然后输入口令就可以  
![在这里插入图片描述](https://img-blog.csdnimg.cn/ca6472e4816543838bb3c087a71199ee.png)

![在这里插入图片描述](https://img-blog.csdnimg.cn/8e3d292b317b43189fae20ad38bf89dd.png?x-oss-process=image/watermark,type_d3F5LXplbmhlaQ,shadow_50,text_Q1NETiBAQ2xpdmVuX2tlbg==,size_20,color_FFFFFF,t_70,g_se,x_16)

### 参考文献

\[1\]. [谢邵虎的博客 . 银河麒麟V10启用VNCServer . 2020.09 . https://xieshaohu.wordpress.com/2020/09/10/%E9%93%B6%E6%B2%B3%E9%BA%92%E9%BA%9Fv10%E5%90%AF%E7%94%A8vncserver/](https://xieshaohu.wordpress.com/2020/09/10/%E9%93%B6%E6%B2%B3%E9%BA%92%E9%BA%9Fv10%E5%90%AF%E7%94%A8vncserver/)
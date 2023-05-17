# [kali](https://so.csdn.net/so/search?q=kali&spm=1001.2101.3001.7020)搭建docker

### 更新kali源

```
sudo apt update
```

出错

![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627205846481.png?x-oss-process=image/watermark,type_ZmFuZ3poZW5naGVpdGk,shadow_10,text_aHR0cHM6Ly9ibG9nLmNzZG4ubmV0L3poaXhpNjY2,size_16,color_FFFFFF,t_70#pic_center)

更新一下密钥

```
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys ED444FF07D8D0BF6
```

### 安装[docker](https://so.csdn.net/so/search?q=docker&spm=1001.2101.3001.7020)

```
sudo apt install docker.io -y #安装docker
docker -v #docker版本
sudo systemctl status docker #查看docker状态
sudo systemctl start docker #启动docker
sudo systemctl enable docker #开机自动启动
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627205908387.png#pic_center)

### 安装pip3

```
sudo apt-get install python3-pip -y
```

出现错误

![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627210409494.png#pic_center)

解决

```
sudo apt install gcc-9-base
```

查看一下是否安装成功

```
pip3 -V
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627210516245.png#pic_center)

### 安装docker-compose

```
sudo pip3 install docker-compose 
docker-compose -v
```

查看docker是否能使用：

```bash
docker run hello-world
docker run ubuntu:15.10 /bin/echo "Hello world"
```

![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627210735647.png?x-oss-process=image/watermark,type_ZmFuZ3poZW5naGVpdGk,shadow_10,text_aHR0cHM6Ly9ibG9nLmNzZG4ubmV0L3poaXhpNjY2,size_16,color_FFFFFF,t_70#pic_center)  
![在这里插入图片描述](https://img-blog.csdnimg.cn/20210627210743660.png#pic_center)  
出现以上现象表示成功

### 基础命令

查看当前本地镜像

```
docker images
```

搜素镜像

```
docker search <想要搜索的镜像名>
```

拉取镜像

```
docker pull <想要拉取的镜像NAME>
```

停止容器

```
docker stop <容器ID或容器名>
```

查看容器端口映射情况

```
docker port <容器ID或容器名>
```

删除镜像

```
docker rmi <>
```

docker搭建漏洞环境及工具文章

- [docker中搭建vulhub漏洞环境](https://blog.csdn.net/zhixi666/article/details/118280338)  
  [docker中搭建ARL灯塔资产系统](https://blog.csdn.net/zhixi666/article/details/118552848)  
  [docker中安装OneForAll子域收集工具](https://blog.csdn.net/zhixi666/article/details/119184683?spm=1001.2014.3001.5501)

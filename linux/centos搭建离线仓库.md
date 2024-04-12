# centos搭建离线仓库

我们知道centos是通过yum来下载和管理软件，通过yum工具我们可以直接将rpm软件包下载下来安装到系统，是管理和安装软件非常便捷的一个工具。

在外网中，我们可以设置对应的镜像源为官方源或者阿里云、清华等地方的源，但是在内网环境中，我们要怎样才能使用yum下载软件呢？

这里有两种方式，都是基于iso镜像，一种是本地挂载，一种是http服务器挂载：

- 本地挂载

 将centos的iso镜像mount到某个目录下，然后修改/etc/yum.repos.d/CentOS-Base.repo，将其地址修改为本地地址。

- http服务器挂载

 将centos的iso镜像mount到目录，同时把目录下的所有文件拷贝到http服务器的目录下，使其可以通过http服务器访问。然后再修改/etc/yum.repos.d/CentOS-Base.repo，将其修改为http服务器的地址。

 但上面的方式只能解决基础软件包的下载问题，我们知道centos还有一些包是放在extra里面，而centos的iso镜像里并不包含extra的包，那么如何才能像上面那样配置extra的源呢？

 这个时候就需要用到reposync工具，在使用该工具之前，需要下载一些基础命令，使用如下命令下载：

 ```shell
 sudo yum install yum-utils createrepo
 ```
 
 先在一台可以访问外网的机器上，使用如下命令将extra包下载下来：

 ```shell
 sudo reposync --repoid=extras --download_path=./
 ```

下载完后需要建立索引文件

```shell
sudo createrepo -po extras extras
```

```shell
➜  extra ls
extras
➜  extra ls extras 
Packages  repodata
```

 然后再将整个exrtras包拷贝到http服务器目录上，使其可以通过http服务器访问。

 这个时候再来修改/etc/yum.repos.d/CentOS-Base.repo，增加[extra]项，其地址配置为http的extra目录地址。
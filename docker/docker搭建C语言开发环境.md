# docker搭建C语言开发环境

## docker 基础命令

- 查看镜像

```shell
docker images
```

- 查看运行的容器

```shell
docker container ls
docker ps -a
```
- 启动容器

```shell
docker run -d -it --name dev -p 8080:8080 --privileged=true /usr/sbin/init
```

- 连接到容器

```shell
docker exec -it id bash
```

- 停止容器

```shell
docker stop id
```

- 删除容器

```shell
docker container rm id
```

## 制作基础镜像

无网络环境下使用本地文件作为基础镜像：

```shell
yum -y --install-root=./code-server install gcc gcc-c++ kernel-devel make cmake  libstdc++-devel libstdc++-static glibc-devel openssl-devel gperftools-libs psmisc openssh-server sudo epel-release vim git ctags net-tools tcpdump protobuf-c protobuf-c-devel protobuf doxygen  java-1.8.0-openjdk java-1.8.0-openjdk-devel bison flex readline readline-devel icu libicu-devel yacc libxml2-devel libxml2
cd code-sever
tar -cvpf code-server.tar --directory=. --exclude=proc --exclude=sys --exclude=dev --exclude=boot .
```

```dockfile
FROM centos:centos7.6.1810

MAINTAINER duanyingshou

RUN yum -y --nogpgcheck install gcc gcc-c++ kernel-devel make cmake  libstdc++-devel libstdc++-static glibc-devel glibc-headers \
&& yum -y --nogpgcheck install openssl-devel gperftools-libs \
&& yum -y --nogpgcheck install psmisc openssh-server sudo epel-release \
&& yum -y --nogpgcheck install vim git ctags net-tools tcpdump \
&& yum -y --nogpgcheck install protobuf-c protobuf-c-devel protobuf doxygen  java-1.8.0-openjdk java-1.8.0-openjdk-devel\
&& yum -y --nogpgcheck install bison flex readline readline-devel icu libicu-devel yacc libxml2-devel libxml2 \
&& mkdir /var/run/sshd \
&& echo "root:test" | chpasswd \
&& sed -ri 's/^#PermitRootLogin\s+.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
&& sed -ri 's/UsePAM yes/#UsePAM yes/g' /etc/ssh/sshd_config \
&& ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key \
&& ssh-keygen -t dsa -f /etc/ssh/ssh_host_dsa_key \
RUN curl  -fsSL https://code-server.dev/install.sh | sh
CMD export  PASSWORD="code" && code-server --host 0.0.0.0
CMD ["/usr/sbin/sshd", "-D"]
```

写入dockerfile后执行如下命令：

```shell
docker build -t dev:last .
```

## 安装coder-server

```
sudo docker pull codercom/code-server:latest
sudo docker run -d -it --name code-server -p 8080:8080 \
            -v "/home/ha/cwork:/home/coder/project" \
            -u "$(id -u):$(id -g)" \
            -e "DOCKER_USER=$USER" \
            codercom/code-server:latest
```

查看code-server镜像大小,可以看到code-server的镜像挺大的，1.63GB。

```
codercom/code-server        latest          dc6f07d1c0f8   20 months ago   1.63GB
```

查看code-server内部组件

```
sudo docker container ls
sudo docker exec -it 19f8152c703f bash
```

查看code-server内部的操作系统版本：

```
ha@19f8152c703f:~$ gcc -v
bash: gcc: command not found
ha@19f8152c703f:~$ uname -a
Linux 19f8152c703f 3.10.0-1160.el7.x86_64 #1 SMP Mon Oct 19 16:18:59 UTC 2020 x86_64 GNU/Linux
ha@19f8152c703f:~$ cat /etc/*release
PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"
NAME="Debian GNU/Linux"
VERSION_ID="11"
VERSION="11 (bullseye)"
VERSION_CODENAME=bullseye
ID=debian
HOME_URL="https://www.debian.org/"
SUPPORT_URL="https://www.debian.org/support"
BUG_REPORT_URL="https://bugs.debian.org/"
```

可以看到容器内部的操作系统是debian，我们期望是centos7.6，与我们的要求不符合，
因而采用在基础镜像里安装code-server,安装完成后，我们再将其导出为我们需要的镜像。

## 下载code-server

```shell
wget https://github.com/coder/code-server/releases/download/v4.16.1/code-server-4.16.1-amd64.rpm
```

下载完成后记录下code-server的rpm包的安装目录，并将其映射到容器内部进行安装。

或者也可以下载下来后直接打包进容器，dockerfile如下所示：

```dockfile
FROM centos:centos7.6.1810

MAINTAINER duanyingshou

RUN yum -y --nogpgcheck install gcc gcc-c++ kernel-devel make cmake  libstdc++-devel libstdc++-static glibc-devel glibc-headers \
&& yum -y --nogpgcheck install openssl-devel gperftools-libs \
&& yum -y --nogpgcheck install psmisc openssh-server sudo epel-release \
&& yum -y --nogpgcheck install vim git ctags net-tools tcpdump \
&& yum -y --nogpgcheck install protobuf-c protobuf-c-devel protobuf doxygen  java-1.8.0-openjdk java-1.8.0-openjdk-devel\
&& yum -y --nogpgcheck install bison flex readline readline-devel icu libicu-devel yacc libxml2-devel libxml2 \
&& mkdir /var/run/sshd \
&& echo "root:test" | chpasswd \
&& sed -ri 's/^#PermitRootLogin\s+.*/PermitRootLogin yes/' /etc/ssh/sshd_config \
&& sed -ri 's/UsePAM yes/#UsePAM yes/g' /etc/ssh/sshd_config \
&& ssh-keygen -t rsa -f /etc/ssh/ssh_host_rsa_key \
&& ssh-keygen -t dsa -f /etc/ssh/ssh_host_dsa_key \
&& ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key \
&& ssh-keygen -t ecdsa -f /etc/ssh/ssh_host_ecdsa_key
&& mkdir -p /home/code 
COPY code-server-4.16.1-amd64.rpm /home/code/
CMD export  PASSWORD="code" && code-server --host 0.0.0.0
CMD ["/usr/sbin/sshd", "-D"]
```



## 启动容器

```shell
sudo docker run -d -it --name dev_server -p 8080:8080 -p 10024:22 \
            -v "/home/ha/docker/dev:/home/coder/" \
            -u "$(id -u):$(id -g)" \
            -e "DOCKER_USER=$USER" \
            --privileged=true \
            dev:latest \
            /usr/sbin/init
```

## 基于当前容器构建镜像

容器运行起来后,发现code-server未成功安装运行。寻找原因发现code-server未正确安装，进入容器内部手动安装。

```shell
rpm -i /home/code/code-server-4.16.1-amd64.rpm
which code-server
```

能看到code-server命令说明安装成功。

同时发现sshd服务未在容器启动时启动，需要封装脚本，并在.bashrc中执行。

在容器内部编写如下脚本：

```shell
#!/bin/bash

/usr/sbin/sshd
export  PASSWORD="code"
/usr/bin/code-server --bind-addr=0.0.0.0:8080 >/dev/null 2>&1 &
```

将其保存为.start_service.sh,并增加可执行权限。

然后在.bashrc中添加如下内容，保证启动容器时启动。

```shell
# start up sshd and code-server
if [ -f /root/.start_service.sh ]; then
        ./root/.start_service.sh
fi
```

然后基于该容器生成最新镜像。

```shell
docker commit -a "duanyingshou" -m "add code-server" id dev:v2
```

到这里，我们的容器已经制作完成了，已经有了一个基本开发环境，可以将其导出然后到其他地方使用。

## 导出容器

- 查看容器id

```
docker ps -a
```

- 根据容器id导出容器

```
docker export ${id} > name.tar
```

## 导入容器

```
docker import - name < name.tar
```

## 导出镜像

- 查看镜像id

```
docker images
```

- 找到镜像id后，将镜像保存

```
docker save id > name.tar
```

## 载入镜像

```
docker load < name.tar
```

## export 与save的区别

- export导出的镜像文件体积小于save保存的镜像

- docker import可以为镜像指定名称，docker load不能对载入的镜像重命名

- export未包含镜像所有的历史记录和元数据信息，无法进行回滚

- docker export 的应用场景：主要用来制作基础镜像，比如我们从一个 ubuntu 镜像启动一个容器，
然后安装一些软件和进行一些设置后，使用 docker export 保存为一个基础镜像。然后，把这个镜像分发给其他人使用，比如作为基础的开发环境。

- docker save 的应用场景：如果我们的应用是使用 docker-compose.yml 编排的多个镜像组合，
但我们要部署的客户服务器并不能连外网。这时就可以使用 docker save 将用到的镜像打个包，然后拷贝到客户服务器上使用 docker load 载入。

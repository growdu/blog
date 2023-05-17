Dockers 是有能力打包应用程式及其虚拟容器，可以在任何 Linux 伺服器上执行的依赖性工具，这有助於实现灵活性和便携性，应用程式在任何地方都可以执行，无论是公有云、私有云、单机等。  
[docker 是什么](https://www.docker.com/what-docker).

如果可以直接连接 docker 官网，可以直接使用以下命令安装。一条命令直接安装 docker。

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>curl -sSL http<span>s:</span>//<span>get</span>.docker.<span>com</span>/ | <span>sh</span></span><br></pre></td></tr></tbody></table>

如果以上安装失败，可以下载脚本后 [install\_docker.sh](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/install_docker.sh) 执行 `sh --mirror Aliyun`  
或

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>sudo wget http:<span>//</span>blog.yanzhe.tk<span>/2017/</span><span>11</span><span>/09/</span>docker-set-proxy<span>/install_docker.sh | sh --mirror Aliyun</span></span><br></pre></td></tr></tbody></table>

如需要设置非 root 用户自启 docker，需要将目标用户添加到 docker 分组，即是现在安装 docker 后会出现的提示

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span><span>sudo</span> usermod -aG docker <span>$USER</span></span><br></pre></td></tr></tbody></table>

docker 安装后出现 Cannot connect to the Docker daemon. 一般重启 docker 即可

## [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#Docker-%E8%AE%BE%E7%BD%AEhttp-https-socks5%E4%BB%A3%E7%90%86 "Docker 设置http,https socks5代理")Docker 设置 http,https socks5 代理

1.  为 docker 服务创建一个内嵌的 systemd 目录

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>mkdir -p /etc/systemd/system/docker.service.d</span><br></pre></td></tr></tbody></table>

2.  创建 /etc/systemd/system/docker.service.d/https-proxy.conf 文件，并添加 HTTP\_PROXY, 或 HTTPS\_PROXY 环境变量。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br></pre></td><td><pre><span>cd /etc/systemd/system/docker.service.d</span><br><span>sudo nano https-proxy.conf</span><br></pre></td></tr></tbody></table>

其中 ip 和 port,NO\_PROXY 分别改成实际情况的代理地址和端口：  
https-proxy.conf

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br></pre></td><td><pre><span>[Service]</span><br><span>Environment="HTTP_PROXY=socks5://127.0.0.1:1080/" "HTTPS_PROXY=socks5://127.0.0.1:1080/" "NO_PROXY=localhost,127.0.0.1,docker.io,yanzhe919.mirror.aliyuncs.com,99nkhzdo.mirror.aliyuncs.com,*.aliyuncs.com,*.mirror.aliyuncs.com,registry.docker-cn.com,hub.c.163.com,hub-auth.c.163.com,"</span><br></pre></td></tr></tbody></table>

3.  更新配置：

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>sudo systemctl daemon-reload</span><br></pre></td></tr></tbody></table>

4.  重启 Docker 服务：

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>sudo systemctl restart docker</span><br></pre></td></tr></tbody></table>

## [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#%E5%A6%82%E4%BD%BF%E7%94%A8%E5%9B%BD%E5%86%85%E9%95%9C%E5%83%8F%EF%BC%8C%E5%8F%AF%E7%94%A8 "如使用国内镜像，可用")如使用国内镜像，可用

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#docker-pull-%E5%AE%8C%E6%95%B4%E8%B7%AF%E5%BE%84-%E7%BD%91%E5%9D%80-name-repo-tag "docker pull 完整路径(网址/name/repo:tag)")docker pull 完整路径 (网址 /name/repo:tag)

您可以使用以下命令直接从该镜像加速地址进行拉取：

`docker pull registry.docker-cn.com/myname/myrepo:mytag`

例如:

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>docker pull registry.docker-cn.com/library/ubuntu:16.04</span><br></pre></td></tr></tbody></table>

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#%E4%BD%BF%E7%94%A8-%E2%80%93registry-mirror-%E9%85%8D%E7%BD%AE-Docker-%E5%AE%88%E6%8A%A4%E8%BF%9B%E7%A8%8B "使用 –registry-mirror 配置 Docker 守护进程")使用 –registry-mirror 配置 Docker 守护进程

您可以配置 Docker 守护进程默认使用 Docker 官方镜像加速。这样您可以默认通过官方镜像加速拉取镜像，而无需在每次拉取时指定 `registry.docker-cn.com`。

您可以在 Docker 守护进程启动时传入 `--registry-mirror` 参数：

<table><tbody><tr><td><pre><span>1</span><br></pre></td><td><pre><span>docker --registry-mirror=https://registry.docker-cn.com daemon</span><br></pre></td></tr></tbody></table>

为了永久性保留更改，您可以修改 `/etc/docker/daemon.json` 文件并添加上 `registry-mirrors` 键值。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br></pre></td><td><pre><span>{</span><br><span>  "registry-mirrors": ["https://registry.docker-cn.com"]</span><br><span>}</span><br></pre></td></tr></tbody></table>

修改保存后重启 Docker 以使配置生效。

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br></pre></td><td><pre><span><span>sudo</span> <span>systemctl daemon-reload</span></span><br><span><span>sudo</span> <span>systemctl restart docker</span></span><br><span><span>sudo</span> <span>systemctl enable docker</span></span><br></pre></td></tr></tbody></table>

阿里，使用需要登录自己的阿里账号，配置自己的地址

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br></pre></td><td><pre><span>sudo mkdir -p /etc/docker</span><br><span>sudo tee /etc/docker/daemon.json &lt;&lt;-'EOF'</span><br><span>{</span><br><span>  "registry-mirrors": ["https://99nkhzdo.mirror.aliyuncs.com"]</span><br><span>}</span><br><span>EOF</span><br><span>sudo systemctl daemon-reload</span><br><span>sudo systemctl restart docker</span><br><span>sudo systemctl enable docker</span><br></pre></td></tr></tbody></table>

## [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#docker-%E5%9F%BA%E6%9C%AC%E4%BD%BF%E7%94%A8%E7%A4%BA%E4%BE%8B "docker 基本使用示例")docker 基本使用示例

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#docker-%E5%AE%89%E8%A3%85%E5%B9%B6%E8%BF%90%E8%A1%8Cnginx "docker 安装并运行nginx")docker 安装并运行 nginx

> -   检查本地镜像

```
`docker images`
```

> -   拉取镜像

```
`docker pull nginx` 或是使用dockerfile文件build images
```

> -   运行容器，可指定后台运行 - d，指定映射端口 - p 主机：容器内，指定挂载目录 - v 主机：容器内

可 COPY nginx 默认配置文件

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br></pre></td><td><pre><span>mkdir -p ~/nginx/www ~/nginx/logs ~/nginx/conf</span><br><span>cd ~/nginx</span><br><span>docker run --name mynginx -d library/nginx</span><br><span>docker cp mynginx:/etc/nginx/nginx.conf /home/yanzhe/nginx/conf/nginx.conf</span><br><span>docker run -p 80:80 --name mynginx -v $PWD/www:/www -v $PWD/conf/nginx.conf:/etc/nginx/nginx.conf -v $PWD/logs:/wwwlogs  -d nginx</span><br></pre></td></tr></tbody></table>

> -   查看容器状态

```
-a所有
`docker ps -a`
```

> -   查看端口是否监听

```
`ss -na | grep :80`

或是
`netstat -na | grep 80`
```

> -   查看容器日志

```
`docker logs mynginx`
```

> -   进入容器

```
`docker exec -it mynginx bash`
```

> -   访问 web

```
`http://localhost:80`
```

> -   停止容器

```
`docker stop mynginx`
```

> -   启动 / 重启容器

```
`docker start mynginx` `docker restart mynginx`
```

> -   删除容器

```
`dockert rm mynginx`
```

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#docker "docker")docker

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#%E4%BD%BF%E7%94%A8war%E5%8C%85%EF%BC%8Ctomcat "使用war包，tomcat")使用 war 包，tomcat

> -   拉取 tomcat

```
`docker pull library/tomcat`
```

> -   使用 dockerfile

将 war 包与 dockerfile 放置于同级目录，创建 dockerfile

```
1234567#from library/tomcat#MAINTAINER yanzhe yz@gmail.comCOPY jpress.war /usr/local/tomcat/webapps
```

> -   build dockerfile

```
-t 指定name:tag
`docker build -t jpress:latest`
```

> -   运行容器

```
`docker run -d -p 8888:8080 jpress`
```

> -   查看端口是否监听

```
`ss -na | grep 8888`

或是
`netstat -na | grep 8888`
```

> -   访问 tomcat

```
`http://localhost:8888/jpress`
```

### [](https://blog.yanzhe.tk/2017/11/09/docker-set-proxy/#spring-boot "spring boot")spring boot

> -   添加 Dockerfile

在应用根目录下建立 Dockerfile 文件，内容如下：

<table><tbody><tr><td><pre><span>1</span><br><span>2</span><br><span>3</span><br><span>4</span><br><span>5</span><br><span>6</span><br><span>7</span><br><span>8</span><br><span>9</span><br><span>10</span><br><span>11</span><br><span>12</span><br><span>13</span><br><span>14</span><br><span>15</span><br><span>16</span><br></pre></td><td><pre><span>FROM maven:3.3.3</span><br><span></span><br><span>ADD pom.xml /tmp/build/</span><br><span>RUN cd /tmp/build &amp;&amp; mvn -q dependency:resolve</span><br><span></span><br><span>ADD src /tmp/build/src</span><br><span>        #构建应用</span><br><span>RUN cd /tmp/build &amp;&amp; mvn -q -DskipTests=true package \</span><br><span>        #拷贝编译结果到指定目录</span><br><span>        &amp;&amp; mv target/*.jar /app.jar \</span><br><span>        #清理编译痕迹</span><br><span>        &amp;&amp; cd / &amp;&amp; rm -rf /tmp/build</span><br><span></span><br><span>VOLUME /tmp</span><br><span>EXPOSE 8080</span><br><span>ENTRYPOINT ["java","-Djava.security.egd=file:/dev/./urandom","-jar","/app.jar"]</span><br></pre></td></tr></tbody></table>

由于项目使用 Maven 构建，故本次基础镜像选用 maven:3.3.3 官方镜像。  
官方维护的 Maven 镜像依赖于 Java 镜像构建，所以我们不需要使用 Java 镜像。

因为 Spring Boot 框架打包的应用是一个包含依赖的 jar 文件，内嵌了 Tomcat 和 Jetty 支持，所以我们只需要使用包含 Java 的 Maven 镜像即可，不需要 Tomcat 镜像。

为了减少镜像大小，在执行 Maven 构建之后，清理了构建痕迹。

在 Dockerfile 文件的最后，使用 ENTRYPOINT 指令执行启动 Java 应用的操作。

> -   构建 docker 镜像

```
`docker build -t docker-demo-spring-boot . `
```

> -   从镜像启动容器

```
`docker run -d -p 8080:8080 docker-demo-spring-boot`
```

> -   打开浏览器，或者使用 curl 访问如下地址

```
`http://127.0.0.1:8080`
```
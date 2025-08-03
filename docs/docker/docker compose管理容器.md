# docker compose管理容器

使用docker-compose部署code-server容器开发环境。

编辑docker-compose.yaml文件。

内容如下：

```shell
version: '3'
services:
  # 服务名称
  dev:
    # 镜像:版本
    image: code_server_ssh:v1
    # 本地 8085 -> 容器 8080
    ports:
      - '8085:8080'
      - '10028:22'
    environment:
      - PASSWORD=code
    # 数据卷 映射本地文件到容器
    volumes:
      - /fast1/code/cwork:/home/coder/work
    # 启动命令：daemon off 将 nginx 提到前台避免容器退出
    command: /usr/sbin/init

```



## 启动容器

```shell
sudo docker-compose up -d
```

## 查看容器状态

```shell
sudo docker-compose ps
```


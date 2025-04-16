# codeserver_docker

## 安装docker

```shell
sudo apt install docker-ce
```

## 制作镜像

dockerfile如下：

```dockerfile
FROM linuxserver/code-server
WORKDIR /config
RUN apt update \
  && apt install -y build-essential gdb vim zsh wget \
  && chsh -s /bin/zsh
CMD [ "/usr/local/bin/code-server --config /home/your_user/.config/code-server/config.yaml"
```

运行如下命令拉取镜像：

```shell
sudo docker build -t codeserver .
```


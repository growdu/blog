# docker搭建个人镜像仓库

## 安装registry

```shell
mkdir docker-registry
cd docker-registry
mkdir registry
mkdr auth
vim docker-compose.yml
```
docker-compose.yml的内容如下：

```shell
version: '3'
services:
  registry:
    image: registry
    container_name: registry
    volumes:
      - ./registry:/var/lib/registry
      - ./auth:/auth
    environment:
      - REGISTRY_AUTH=htpasswd
      - REGISTRY_AUTH_HTPASSWD_REALM=Registry_Realm
      - REGISTRY_AUTH_HTPASSWD_PATH=/auth/passwd
    restart: always
    ports:
      - "5000:5000"
```

用htpasswd先生成一个密码，然后将文件拷贝到auth下面，用这个用户名密码登录。

```shell
htpasswd -Bbc htpasswd.user admin 123456
mv htpasswd.user auth/passwd
```

然后再启动镜像：

```shell
docker-compose up -d
```

## 添加镜像仓库到registry

- 编辑docker配置文件 

在 /etc/docker/daemon.json 文件中写入如下内容：

```json
    {
        "registry-mirror": [
          "https://registry.docker-cn.com"
        ],
        "insecure-registries": [
          "ip:port"
        ]
    }
```

- 修改完成后重启docker服务


```shell
systemctl restart docker
```

- 登录到docker registry

```shell
(base) ➜  docker_registry git:(main) ✗ sudo docker login http://192.168.80.20:5000
Username: admin
Password: 
WARNING! Your password will be stored unencrypted in /root/.docker/config.json.
Configure a credential helper to remove this warning. See
https://docs.docker.com/engine/reference/commandline/login/#credentials-store

Login Succeeded
```

- 加上个人仓库标签然后push

```shell
docker tag registry 192.168.80.20:5000/registry
docker push 192.168.80.20:5000/registry
```

## 设置镜像仓库ui

- 编辑配置文件

```shell
vim registry_ui.yml
```

内容如下：

```yaml
version: '3'
services:
  registry-ui:
    image: konradkleine/docker-registry-frontend:v2
    container_name: registry_ui
    restart: always
    privileged: true
    environment:
      - ENV_DOCKER_REGISTRY_HOST=192.168.80.20
      - ENV_DOCKER_REGISTRY_PORT=5000
    ports:
      - "5001:80"
```

- 启动registry-ui

```shell
docker-compose -f registry_ui.yml up -d
```
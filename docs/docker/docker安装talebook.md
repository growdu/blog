官方Github： [https://github.com/talebook/talebook](https://github.com/talebook/talebook)

1、安装Docker

SH 代码:

```
#CentOS 7、Debian、Ubuntu
curl -sSL https://get.docker.com/ | sh
systemctl start docker
systemctl enable docker
```

2、安装Docker Compose

SH 代码:

```
curl -SL https://github.com/docker/compose/releases/download/v2.15.1/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

3、安装TaleBook

SH 代码:

```
mkdir -p /fast1/docker_data/talebook
vim docker-compose.yaml

version: "2.4"
services: 
  # optional, for meta plugins
  # please set "http://douban-rs-api" in settings
  douban-rs-api: 
    image: ghcr.io/cxfksword/douban-api-rs
    restart: always
  # main service
  talebook: 
    depends_on: 
      - douban-rs-api
    image: talebook/talebook
    ports: 
      - "8080:80"
      - "8443:443"
    restart: always
    volumes: 
      - "/fast1/docker_data/talebook:/data"

docker-compose up -d -f docker-compose.yaml
```

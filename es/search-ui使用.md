# search-ui使用

## 搭建elasticsearch

- 使用docker-compose启动elasticsearch

编辑docker-compose.yml文件，内容如下：

```yaml
version: '3'
services:
  elasticsearch:
    image: elasticsearch:8.9.0
    container_name: elasticsearch
    privileged: true
    environment:
      - "cluster.name=elasticsearch" #设置集群名称为elasticsearch
      - "discovery.type=single-node" #以单一节点模式启动
      - "ES_JAVA_OPTS=-Xms512m -Xmx1096m" #设置使用jvm内存大小
      - bootstrap.memory_lock=true
    volumes:
      - ./es/plugins:/usr/local/dockercompose/elasticsearch/plugins #插件文件挂载
      - ./es/data:/usr/local/dockercompose/elasticsearch/data:rw #数据文件挂载
      - ./es/logs:/usr/local/dockercompose/elasticsearch/logs:rw
    ports:
      - 9200:9200
      - 9300:9300
    deploy:
     resources:
        limits:
           cpus: "2"
           memory: 1000M
        reservations:
           memory: 200M
  kibana:
    image: kibana:8.9.0
    container_name: kibana
    depends_on:
      - elasticsearch #kibana在elasticsearch启动之后再启动
    volumes:
      - ./es/config/kibana:/usr/share/kibana/config/kibana.yaml
    ports:
      - 5601:5601
```

其中kibana.yaml的内容如下：

```shell
elasticsearch.hosts: http://elasticsearch:9200
server.host: "0.0.0.0"
server.name: kibana
xpack.monitoring.ui.container.elasticsearch.enabled: true
i18n.locale: zh-CN
```

- 进入elasticsearch终端，修改elasticsearch密码

```shell
# 进入容器内部
docker exec -it elasticsearch bash
# 修改密码
elasticsearch@4c37fcfb6f13:~$ ls
LICENSE.txt  NOTICE.txt  README.asciidoc  bin  config  data  jdk  lib  logs  modules  plugins
elasticsearch@4c37fcfb6f13:~$ bin/elasticsearch-reset-password --username elastic -i
WARNING: Owner of file [/usr/share/elasticsearch/config/users] used to be [root], but now is [elasticsearch]
WARNING: Owner of file [/usr/share/elasticsearch/config/users_roles] used to be [root], but now is [elasticsearch]
This tool will reset the password of the [elastic] user.
You will be prompted to enter the password.
Please confirm that you would like to continue [y/N]y


Enter password for [elastic]: 
Re-enter password for [elastic]: 
Password for the [elastic] user successfully reset.
elasticsearch@4c37fcfb6f13:~$
```

- 生成kibana的token

```shell
# 重启容器然后进入容器内部生成kibana的token
docker exec -it elasticsearch bash
elasticsearch@4c37fcfb6f13:~$ bin/elasticsearch-create-enrollment-token -s kibana
```

- 获取kibana验证码

```shell
# 在浏览器打开http://ip:5601,粘贴kibana的token，然后进入kibana容器内部获取验证码
sudo docker exec -it kibana bash       
kibana@fce2ab8aec1e:~$ ls
LICENSE.txt  NOTICE.txt  README.txt  bin  config  data  logs  node  node_modules  package.json  packages  plugins  src  x-pack
kibana@fce2ab8aec1e:~$ bin/kibana-verification-code 
Your verification code is:  042 943 
```

## 搭建search-ui

- 创建search-ui项目

```shell
npm install -g  create-react-app
# 创建名为doc_index的项目
create-react-app doc_index --use-npm
cd doc_index
npm install --save @elastic/react-search-ui @elastic/search-ui-app-search-connector @elastic/search-ui-elasticsearch-connector
```
- 启动search-ui项目

```shell
npm start
```

- 创建api_key

登录kibana，进入到/app/management/security/api_keys/，创建一个api_key并记录api_key.

- 创建索引

- 导入数据


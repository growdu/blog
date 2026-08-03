# docker搭建Postgresql主备集群

## 搭建主库

docker-compose.yaml配置文件如下：

```yaml
version: "3.1"
services:
  postgres:
    image: postgres:12.8
    container_name: pg_master
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - ~/pg_data:/var/lib/postgresql/data
    ports:
      - 5432:5432
networks: {}
```text
将Postgresql主库的数据文件保存到~/pg_data目录下并映射到容器内部,然后启动容器：

```shell
docker-compose up -d
```text
在主库数据目录下执行如下命令：

```shell
echo "host    replication     all             0.0.0.0/0                 trust" >> ~/pg_data/pg_hba.conf
```text
同时修改postgresql.conf文件的如下内容：

```shell
wal_level= replica
```text
修改完成后重启主库容器：

```shell
docker-compose restart
```text
## 备库配置

先使用pg_basebackup命令备份主库的数据，请注意pg_basebackup的版本应该与主库容器内的版本一致，不然会备份失败。比如主库的版本是12.8，备份时也需要使用12.8的pg_basebackup。

```shell
pg_basebackup -h 192.168.80.20 -p 5432 -U postgres -w -Fp -Xs -Pv -R -D ~/pg_data_slave
```text
备份完成后新建docker-compose-slave.yaml文件，填入如下内容：

```yaml
version: "3.1"
services:
  postgres:
    image: postgres:12.8
    container_name: pg_slave
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - ~/pg_data_slave:/var/lib/postgresql/data
    ports:
      - 54322:5432
networks: {}
```text
修改完成后，启动备库容器。

```shell
docker-compose up -d -f docker-compose-slave.yaml
```text
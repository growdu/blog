# repmgr搭建集群

## 编译

```shell
git clone git@github.com:EnterpriseDB/repmgr.git
```

检查pg是否安装，主要看pg_config在不在$PATH下面。

```shell
pg_config --help
```

然后使用如下命令编译

```shell
./configure
make
make install
```

repmgr5.3与pg15对应，使用其他对应关系有可能会编译报错，编译完成后repmgr会放在pg的二进制目录下。

## 运行

### 主库

- 创建数据库

  ```shell
  initdb -D data -A trust -U system
  ```

- 运行数据库

  ```shell
  pg_ctl -D data -l data/pg.log start
  ```

- 连接数据库

  ```shell
  psql -U system -d postgres -p 5432
  ```

- 创建repmgr用户

  ```shell
  ```

  

### 备库


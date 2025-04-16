# code-server调试postgresql

## 搭建环境

1. 搭建code-server

```shell
docker pull ghcr.io/growdu/oh-my-code/coder:v1.4
```

2. 启动code-server

```shell
git clone https://github.com/growdu/oh-my-code.git
cd oh-my-code
docker-compose up -d
```
3. 登录code-server

4. 下载postgresql源码

```shell
git clone git://git.postgresql.org/git/postgresql.git
```

5. 安装c语言插件

从[这里](https://github.com/microsoft/vscode-cpptools/releases)下载插件安装。

## 编译postgresql

```shell
./configure --prefix=`pwd`/debug --enable-debug CFLAGS='-O0 -g'
make world -j 8
make install-world
```

编译完成后如下：

```shell
➜  postgresql git:(REL_12_STABLE) ✗ ls debug 
bin  include  lib  share
```

## 运行postgresql

```shell
./initdb -A trust data
./pg_ctl -D data -l logfile start
```

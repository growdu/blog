# pg编译运行

## 源码获取

```shell
 git clone http://git.postgresql.org/git/postgresql.git
```

## 编译

```shell
sudo apt install bison yacc 
sudo apt install flex
sudo apt install zlib1g-dev
sudo apt install libreadline6-dev
```

```shell
make clean
./configure --prefix=/usr/local/postgresql
make
make install
```

若要编译调试版本的话，先执行如下命令：

```shell
#!/bin/bash
make clean
./configure --prefix=/usr/local/postgresql --enable-debug CFLAGS='-O0 -g'
make
sudo make install
```

## 运行






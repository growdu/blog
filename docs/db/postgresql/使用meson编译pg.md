# 使用meson编译pg

一般在build目录下进行编译，先生成编译需要文件：

```shell

meson setup build \
  -Dssl=openssl \
  -Dlibxml=enabled \
  -Dlibxslt=enabled \
  -Dzlib=enabled \
  --prefix=`pwd`/debug 

```text
执行生成：

```shell
meson compile -C build
```text
编译完成后安装：

```shell
meson install -C build
```text
# qemu-busybox调试linux

## 下载busybox

```shell
wget https://busybox.net/downloads/busybox-1.36.1.tar.bz2
tar -xvf busybox-1.36.1.tar.bz2
```

配置busybox,你可以使用 make menuconfig命令。这里，有几点是需要我们注意的。

因为Linux运行环境当中是不带动态库的，所以必须以静态方式来编译BusyBox。修改如下内容：

- Busybox Settings —> Build Options —> [*] Build BusyBox as a static binary(no shared libs)

- CONFIG_DESKTOP=n

不需要配置DESKTOP。

```shell
make menuconfig
make 
make install
```
# qemu-busybox调试linux

## 编译内核

### 下载内核代码

```shell
wget https://mirrors.edge.kernel.org/pub/linux/kernel/v6.x/linux-6.9.tar.xz
```

### 安装依赖

```shell
sudo apt-get update
sudo apt-get install bison
sudo apt-get install flex
sudo apt-get install git fakeroot build-essential ncurses-dev xz-utils libssl-dev bc
sudo apt install libelf-dev
```

执行如下命令进行编译：

```shell
make menuconfig
make bzImage
```

在ubuntu下编译会certs相关错误，执行如下脚本临时规避问题（仅用于调试）：

```shell
#!/bin/bash

set -e

echo "[*] 修复 certs/Makefile 中的 Canonical PEM 依赖..."

MAKEFILE="certs/Makefile"
CONFIG=".config"

# 注释掉 canonical certs 的依赖
if grep -q "debian/canonical-certs.pem" "$MAKEFILE"; then
    sed -i 's/^certs\/x509_certificate_list: debian\/canonical-certs.pem/# &/' "$MAKEFILE"
    echo "  ✅ 注释 certs/x509_certificate_list: debian/canonical-certs.pem"
fi

if grep -q "debian/canonical-revoked-certs.pem" "$MAKEFILE"; then
    sed -i 's/^certs\/x509_revocation_list: debian\/canonical-revoked-certs.pem/# &/' "$MAKEFILE"
    echo "  ✅ 注释 certs/x509_revocation_list: debian/canonical-revoked-certs.pem"
fi

# 创建空的 pem 文件以防止其他 Makefile 依赖触发错误
mkdir -p debian
touch debian/canonical-certs.pem
touch debian/canonical-revoked-certs.pem
touch certs/x509_revocation_list
echo "  ✅ 创建空的 debian/canonical-certs.pem 和 canonical-revoked-certs.pem"

# 清理 .config 中的相关项
if [ -f "$CONFIG" ]; then
    echo "[*] 清理 .config 中的 CONFIG_SYSTEM_TRUSTED_KEYS 和 CONFIG_SYSTEM_REVOCATION_KEYS"
    sed -i '/CONFIG_SYSTEM_TRUSTED_KEYS/d' "$CONFIG"
    sed -i '/CONFIG_SYSTEM_REVOCATION_KEYS/d' "$CONFIG"
    echo 'CONFIG_SYSTEM_TRUSTED_KEYS=""' >> "$CONFIG"
    echo 'CONFIG_SYSTEM_REVOCATION_KEYS=""' >> "$CONFIG"
    make olddefconfig
    echo "  ✅ 更新 .config 配置"
fi

echo "[✔] 修复完成，可继续 make 编译内核。"
```

编译完成后可以看到如下输出：

```shell
Kernel: arch/x86/boot/bzImage is ready  (#1)
```


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
make defconfig
make menuconfig
make 
make install
```

:::note
从 Linux 内核 5.9+ 开始，CBQ 被判定为 legacy，不再在 include/uapi/linux/pkt_sched.h 中默认提供这些宏,在高版本中的操作系统下编译，需要关闭tc功能编译，否则编译会报错。

```
make menuconfig
```
进入配置后路径为：

```
Networking Utilities  --->
    [ ] tc
```
取消勾选 tc，保存并退出。然后重新编译：

:::


编译完成后会在_install目录下生成相关的二进制，然后执行如下命令将_install里的内容打包成一个文件系统。

```shell
find . | cpio -o --format=newc | gzip > ./rootfs.img
```

使用如下命令构建文件系统：

```shell
mkdir -p rootfs/{proc,sys,dev,bin,sbin,etc,tmp,var,mnt}
cp -r _install/* rootfs/
```

创建 rootfs/init，内容如下：

```shell
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
echo -e "\nWelcome to QEMU BusyBox shell\n"
/bin/sh
```

添加执行权限：

```shell
chmod +x rootfs/init
```

创建设备文件：

```shell
sudo mknod -m 622 rootfs/dev/console c 5 1
sudo mknod -m 666 rootfs/dev/null c 1 3
```

打包initramfs，

```shell
cd rootfs
find . | cpio -o --format=newc | gzip > ../initramfs.cpio.gz
```


## 安装qemu

```shell
sudo apt-get install libncurses5-dev
sudo apt-get install git libglib2.0-dev libfdt-dev libpixman-1-dev zlib1g-dev
sudo apt-get install qemu-system-x86
```

## qemu启动kernel

将编译出的内核bzImage和rootfs.img复制到一个新目录下，新建启动脚本：

```shell
#!/bin/sh
qemu-system-x86_64 \
  -kernel /root/linux-6.9/arch/x86/boot/bzImage \
  -initrd initramfs.cpio.gz \
  -append "nokaslr console=ttyS0 root=/dev/ram0 rdinit=/init" \
  -nographic
```

然后添加可执行权限并启动：

```shell
chmod +x start.sh
./start.sh
```

- -nographic：避免 GTK/X11 报错（特别是在没有 GUI 的系统中）；

- -cpu host：使用宿主 CPU 能力（推荐），你也可以尝试 kvm64；

- console=ttyS0：让内核输出走串口，以便你看到启动日志；

##  调试内核

使用gdb的方式启动内核：

```shell
qemu-system-x86_64 \
  -s -S \
  -kernel /root/linux-6.9/arch/x86/boot/bzImage \
  -initrd /root/busybox-1.37.0/initramfs.cpio.gz \
  -append "nokaslr console=ttyS0 root=/dev/ram0 rdinit=/init" \
  -nographic
```

- -s = 启用 GDB server，监听 1234

- -S = 启动后暂停 CPU

在另一个终端使用 GDB 连接：

```shell
gdb vmlinux
(gdb) target remote :1234
(gdb) b start_kernel
(gdb) c
```

```shell
#0  start_kernel () at init/main.c:1049
#1  0xffffffff832d6de8 in x86_64_start_reservations (real_mode_data=real_mode_data@entry=0x147b0 <exception_stacks+34736> <error: Cannot access memory at address 0x147b0>)
    at arch/x86/kernel/head64.c:507
#2  0xffffffff832d6f2f in x86_64_start_kernel (real_mode_data=0x147b0 <exception_stacks+34736> <error: Cannot access memory at address 0x147b0>) at arch/x86/kernel/head64.c:488
#3  0xffffffff81051b1d in secondary_startup_64 () at arch/x86/kernel/head_64.S:420
#4  0x0000000000000000 in ?? ()
```

调试过程中，会遇到断点无法命中的问题，是因为linux默认会开启地址随机化。nokaslr 是 Linux 内核启动参数之一，作用是关闭内核地址空间布局随机化（KASLR）。

KASLR（Kernel Address Space Layout Randomization）是内核的一种安全机制，启动时会随机化内核的加载地址，防止攻击者预测内核关键代码和数据的位置。

在调试内核时，如果开启 KASLR，每次启动内核的加载地址都不同，GDB 加载符号表时地址会对不上，导致断点无法命中。因此，加上 nokaslr 参数可以让内核每次都加载到固定地址，方便调试和符号表匹配。

泪目啊。
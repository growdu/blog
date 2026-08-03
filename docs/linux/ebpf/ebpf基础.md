# ebpf基础

## ebpf环境搭建

- ubuntu

```shell
# For Ubuntu20.10+
sudo apt-get install -y  make clang llvm libelf-dev libbpf-dev bpfcc-tools libbpfcc-dev linux-tools-$(uname -r) linux-headers-$(uname -r)
sudo apt-get install libcap-dev
sudo apt-get install binutils-dev
```
- centos

```shell
# For RHEL8.2+
sudo yum install libbpf-devel make clang llvm elfutils-libelf-devel bpftool bcc-tools bcc-devel
sudo yum install libcap-devel
sudo yum install binutils-devel
```
## 编写第一个ebpf程序

### 编写代码

```c
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("tracepoint/syscalls/sys_enter_execve")
int hello_world(void *ctx)
{
    // 带参数的版本
    char message[] = "Hello, World!";
    bpf_trace_printk("Message: %s\\n", 13, message);
    return 0;
}

char _license[] SEC("license") = "GPL";
```
### 编译ebpf程序

使用下面的makefile进行编译：

```makefile
CLANG ?= clang
LLVM_STRIP ?= llvm-strip
ARCH := $(shell uname -m | sed 's/x86_64/x86/')

BPF_TARGET := hello_world.bpf.o
BPF_CFLAGS := -O2 -g -target bpf -D__TARGET_ARCH_$(ARCH)

$(BPF_TARGET): hello_world.c
        $(CLANG) $(BPF_CFLAGS) -c $< -o $@
        $(LLVM_STRIP) -g $@

clean:
        rm -f $(BPF_TARGET)

.PHONY: clean
```
可能会报错`asm/types.h`找不到，使用如下方式解决：

```shell
ln -sf /usr/include/asm-generic/ /usr/include/asm
```
执行`make`命令生成`hello_world.bpf.o`.

### 运行ebpf程序

运行ebpf程序，需要使用加载器。一般使用bpftool加载C语言编写的ebpf程序。

#### 编译bpftool

#### 加载ebpf程序

```c
bpftool prog load hello_world.bpf.o /sys/fs/bpf/hello_world
```
加载成功后查看ebpf程序：

```shell
bpftool prog list
bpftool prog list | grep hello
```
```shell
bpftool prog list --json | jq '.[] | {id, name, type}'

bpftool prog list --json | jq '.[] | {id, name, type}' | grep hello
```
```shell
bpftool prog attach 366 tracepoint syscalls/sys_enter_execve
```
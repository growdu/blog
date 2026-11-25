---
description: "Linux 内核是所有系统级知识的交汇点：进程怎么被调度、内存怎么被管住、文件怎么落到盘上、系统调用怎么进内核 —— 这四件事在同一个代码树里。这篇是这条源码线的总入口：一张全景图、一份代码地图、一条 12 章的路线，以及怎么在几千万行 C 里读懂一个函数。"
---

# Linux 源码学习之路：一张全景图 + 12 章路线

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿：给出内核的分层全景、顶层代码地图、12 章阅读路线，以及编译、QEMU 启动、GDB、rg/ctags/cscope 的上手方法。 | 2026-11-25 |

> 本文是「Linux 源码主线」的总入口。同系列后续：
>
> - [01 整体架构与一次系统调用的完整链路](../architecture/learning-path/01-整体架构与一次系统调用的完整链路.md)

## 为什么先读 Linux 内核

几乎所有系统级知识都能在内核里找到落点：

- **进程与线程**：`fork` 到底复制了什么，线程和不带地址空间的进程差在哪，
  上下文切换时到底换了哪些寄存器。
- **虚拟内存**：每个进程为什么能看见一整块 4TB 地址空间，缺页是怎么被处理的，
  物理内存又是怎么分配出去的。
- **文件与 I/O**：`open`/`read`/`write` 走的是同一条 VFS 路径吗，
  页缓存和回写（writeback）为什么能让「写完了」不等于「落盘了」。
- **同步与并发**：内核里的锁有几十种，`spin_lock` 和 `mutex` 的区别不是「一个自旋一个睡眠」这么简单。
- **调度**：CFS 是怎么算优先级的，负载均衡在什么时机发生。

内核还有一个别的项目没有的性质：**它必须同时满足性能和可维护性**。
所以你能在里面看到几乎所有软件工程 trade-off 的实物 —— 热路径上为了性能
把检查去掉，为了可维护性又把日志加上。

> 读内核的收益不是「学会写驱动」，而是：**把「系统卡了」「IO 慢」「内存涨了」
> 这类模糊的抱怨，落到一个具体的函数、一行具体的代码上。**

## 0. 先建立四个概念

读源码之前，这四个词必须先立住 —— 内核后面所有的命名都从它们派生。

### 0.1 用户态与内核态

x86_64 用**特权级（ring）**区分：用户态跑在 ring 3，内核态跑在 ring 0。
进程不能直接碰硬件，也不能直接读别的进程内存 —— 想干这些事，
只能**请求内核代劳**，这就是系统调用。

```text
用户态（ring 3）                内核态（ring 0）
┌──────────────────┐            ┌──────────────────┐
│ 你的程序         │  syscall   │ 系统调用处理     │
│ libc: write()    │ ─────────► │ → VFS → 块层     │
└──────────────────┘            └──────────────────┘
        │                                  ▲
        │  返回值（errno 也在这条路上）    │
        └──────────────────────────────────┘
```

### 0.2 系统调用、异常、中断

这三样东西**都**能让控制流从用户态掉进内核态，但触发者不同：

| 类型 | 触发者 | 例子 | 是不是「异步」 |
| --- | --- | --- | --- |
| **系统调用** | 用户态主动执行 `syscall` 指令 | `write()` | 否，同步 |
| **异常（fault）** | 当前指令出错 | 缺页、除零、非法指令 | 否，同步处理 |
| **中断（IRQ）** | 外部设备 | 磁盘完成、时钟滴答、定时器 | 是 |

内核靠**中断描述符表（IDT）**和每种入口不同的「栈布局」把这三者区分开。
读 x86_64 的入口汇编时，这是第一件要看清楚的事。

### 0.3 进程、线程、任务

Linux 内核里**没有「线程」这个独立概念**：
线程就是**共享地址空间、文件描述符表和信号处理方式**的另一个任务（task）。
内核里只有一个 `struct task_struct`，一个任务要么是线程组的领线程，要么是普通线程。

```text
一个线程组（进程）            另一个线程组（另一个进程）
┌───────────────────┐        ┌───────────────────┐
│ task A (tgid=100) │        │ task C (tgid=200) │
│  ├─ 共享 mm/files │        │  └─ 自己的 mm/files│
│ task B (tgid=100) │        │                   │
└───────────────────┘        └───────────────────┘
```

### 0.4 内核模块

内核不是一个单体程序：**大部分功能编译成 `.ko` 模块**，按需加载
（`insmod`/`modprobe`）或编译进内核（built-in）。
`lsmod` 看到的一行就是一组模块。

这一点对读代码有直接影响：**你在源码里搜到的函数，可能根本不在你正在跑的那个内核里**。
所以读代码前先确认：`/boot/config-$(uname -r)` 里的 `CONFIG_XXX` 是 `y`（编进去了）
还是 `m`（编成模块了）。

## 1. 代码地图

内核的顶层目录就是一张职责表。下表里的数字是本树（`v7.4.0-rc3`）
里 `.c` + `.h` 的文件数 —— 看完你就知道哪个目录值得先翻。

| 目录 | 干什么 | 文件数 |
| --- | --- | --- |
| `arch/` | **架构相关**：x86 的中断向量表、页表、上下文切换汇编都在这 | 9214 |
| `include/` | **头文件**：`include/linux/` 是内核 API，`include/uapi/` 是给用户空间的 | 6773 |
| `kernel/` | **内核核心**：进程（fork/signal）、调度（sched/）、锁、time、rcu、trace | 670 |
| `mm/` | **内存管理**：虚拟内存、缺页、页缓存、页分配器、swap | 197 |
| `fs/` | **文件系统**：VFS（open/namei/inotify/…）+ ext4、btrfs、nfs、overlayfs… | 2184 |
| `net/` | **网络协议栈**：socket、TCP/IP、netfilter、无线 | 1733 |
| `block/` | **块层**：bio、请求队列、blk-mq 调度器 | 98 |
| `drivers/` | **设备驱动**：字符/网络/块/图形/USB…（最大的一个目录） | 34423 |
| `lib/` | **通用库**：字符串、校验和、排序、CRC、klist… | 748 |
| `crypto/` | **加密算法**：AES、sha256… 以及 AF_ALG | 166 |
| `security/` | **安全**：SELinux、LSM、integrity | 273 |
| `sound/` | **音频**：ALSA | 2752 |
| `ipc/` | **进程间通信**：System V IPC、消息队列、共享内存 | 12 |
| `io_uring/` | **现代异步 I/O**：`io_uring` 与 `IORING_OP_*` | 89 |
| `rust/` | **Rust 驱动框架**：Rust for Linux 基础设施 | 73 |
| `init/` | **启动**：`start_kernel`、init 进程 | 13 |
| `usr/` | **initramfs**：用户空间工具的源码（`/bin/busybox` 等） | 13 |
| `virt/` | **虚拟化**：KVM guest 侧的 guest 代码 | 16 |
| `scripts/` | **构建与检查工具**：kconfig、kallsyms、checkpatch、coccinelle、tags | 118 |
| `Documentation/` | **文档**：`.rst` 源码，**每个子系统都有** | （不是 C 代码） |
| `samples/` | **示例代码**：kprobes、ftrace、BPF… | 174 |
| `tools/` | **用户态工具**：perf、bpftool、selftests、libbpf | 5332 |

几个必须知道的地标文件（**不是**「入口」，而是「地图」）：

| 文件 | 干什么 |
| --- | --- |
| `include/linux/sched.h` | `struct task_struct`（`:836`）—— 进程的全貌 |
| `include/linux/mm_types.h` | `struct mm_struct`（`:1214`）、`struct vm_area_struct` —— 内存的全貌 |
| `include/linux/fs.h` | `struct file`（`:1258`）、`struct file_operations`（`:1923`）—— 文件的全貌 |
| `include/linux/blk_types.h` | `struct bio`（`:210`）—— 块 I/O 的全貌 |
| `init/main.c` | `start_kernel` → `rest_init` → `kernel_init`，启动的骨架 |
| `kernel/sched/core.c` | 调度器的核心，1 万多行 |
| `mm/memory.c` | 缺页处理、fork 的内存复制，核心中的核心 |

> **读内核的通用技巧**：先读 `include/` 里的**结构体**，再读 `kernel/`、`mm/`、`fs/`
> 里的**函数**。结构体是名词，函数是动词 —— 先把名词认全，动词就好找了。

## 2. 12 章路线

| # | 章节 | 放在哪一站 |
| --- | --- | --- |
| 01 | 整体架构与一次系统调用的完整链路 | 架构与数据路径 |
| 02 | 编译与启动：从 `start_kernel` 到第一个用户态进程 | 架构与数据路径 |
| 03 | 进程与线程：`fork`、`clone`、`exec` 到底做了什么 | 进程与内存 |
| 04 | 内存管理：地址空间、缺页、页分配器 | 进程与内存 |
| 05 | 调度器：CFS、负载均衡与上下文切换 | 进程与内存 |
| 06 | VFS：一次 `open` 的完整链路与 inode/dentry | 文件与 I/O |
| 07 | 页缓存与回写：为什么「写完了」不等于「落盘了」 | 文件与 I/O |
| 08 | 块层与 I/O 调度：bio、request、blk-mq | 文件与 I/O |
| 09 | 网络协议栈：一次 `sendto` 的完整链路 | 文件与 I/O |
| 10 | 并发与锁：内核里的几十种锁怎么选 | 内核工程实践 |
| 11 | 观测与调试：perf、ftrace、bpftrace、crash、eBPF | 内核工程实践 |
| 12 | 现代内核的变化：Rust、io_uring、RISC-V 与多架构 | 内核工程实践 |

> 01 是现在这一篇；后面的章节会陆续补上。

## 3. 在 65000 个 C 文件里怎么找到你要的函数

这棵树有 65080 个 `.c`/`.h` 文件。光核心就不少：
`fs/` 335 万行、`include/linux/` 138 万行、`kernel/` 118 万行、`mm/` 47 万行。
所以**定位工具比记忆力重要**。

### 3.1 ripgrep：默认用这个

```bash
# 在内核树里找函数定义（比 grep 准，不会把声明和调用一起捞出来）
rg -n --type c '^\w[\w \*]*do_user_addr_fault\('

# 找调用点
rg -n 'handle_mm_fault\(' --type c

# 在某个目录里找所有提到某个符号的地方
rg -n 'maple_tree' mm/ include/linux/maple_tree.h
```

`rg` 默认会跳过 `.gitignore` 里的东西，但**内核树没有 `.gitignore` 陷阱**，
所以直接用就行。唯一要注意的是 `include/generated/` 和 `include/config/` 是编译产物，
不在源码树里（要先 `make` 过）。

### 3.2 ctags / cscope：跟着调用关系走

```bash
# 生成 ctags 索引（内核自带脚本）
make tags          # 等价于 scripts/tags.sh

# 生成 cscope 索引
make cscope

# 然后在 vim 里：
#   Ctrl-]      跳到定义
#   Ctrl-t      跳回
#   :cs find s  列出调用这个符号的地方
```

### 3.3 gdb 的 Python 扩展：读内核运行时状态

内核自带一批 gdb 脚本，装上以后能直接查运行中内核的数据结构：

```bash
# 编译内核时带上调试信息
make defconfig
./scripts/config --enable DEBUG_INFO --enable DEBUG_KERNEL
make -j$(nproc)

# 用内核自带的 gdb 脚本
gdb vmlinux
(gdb) source scripts/gdb/linux/proc.py
(gdb) source scripts/gdb/linux/mm.py
(gdb) info threads
```

`scripts/gdb/linux/` 下有几十个脚本（`proc.py`、`mm.py`、`lists.py`、`mapletree.py`…），
能省掉大量「手工读 `task_struct` 偏移」的体力活。

### 3.4 `/proc/kallsyms` 和 `/proc/modules`

模块化和符号表这两件事，运行时都能查：

```bash
cat /proc/kallsyms | grep do_user_addr_fault   # 内核符号表
cat /proc/modules                               # 装了哪些模块
zcat /proc/config.gz | grep CONFIG_            # 当前内核的编译配置
```

## 4. 编译、跑起来、连上去

### 4.1 编译

```bash
cd /work/cwork/linux

# 最小配置（编译快，适合第一次）
make tinyconfig

# 或者 x86_64 的常规配置
make ARCH=x86_64 defconfig       # Makefile 会把 ARCH=x86_64 映射成 SRCARCH=x86

# 打开调试信息（读源码必须）
./scripts/config --enable DEBUG_INFO
./scripts/config --enable DEBUG_KERNEL
./scripts/config --enable KALLSYMS_ALL

make -j$(nproc)                  # 内核本体
make -j$(nproc) modules          # 模块
```

产物在 `arch/x86/boot/bzImage`（可引导的内核）和 `vmlinux`（带符号的 ELF，**GDB 要连的是它**）。

### 4.2 用 QEMU 跑起来并连 GDB

内核树本身不带 busybox（那是 Buildroot 的活儿），所以最省事的办法是
**做一个只含 busybox 的 initramfs**：

```bash
# 1) 编 busybox（静态）
wget https://busybox.net/downloads/busybox-1.37.0.tar.bz2
tar xf busybox-1.37.0.tar.bz2 && cd busybox-1.37.0
make defconfig
sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/' .config
make -j$(nproc)
cd ..

# 2) 拼一个最小 rootfs
ROOT=/tmp/rootfs
mkdir -p $ROOT/{bin,dev,proc,sys,lib,usr/bin}
cp busybox/busybox $ROOT/bin/
for a in sh ls cat mount echo dmesg; do ln -sf busybox $ROOT/bin/$a; done
cp -a busybox/lib/libc.so.6 $ROOT/lib/ 2>/dev/null || true
find $ROOT | cpio -o -H newc | gzip > /tmp/rootfs.cpio.gz
```

```bash
# 3) 起 QEMU：-s 开 gdbserver（TCP 1234），-S 停在第一条指令等 GDB
qemu-system-x86_64 \
  -kernel /work/cwork/linux/arch/x86/boot/bzImage \
  -initrd /tmp/rootfs.cpio.gz \
  -append "console=ttyS0 root=/dev/ram0 rdinit=/bin/sh" \
  -nographic -s -S
```

另开一个终端：

```bash
gdb /work/cwork/linux/vmlinux
(gdb) target remote :1234
(gdb) break start_kernel
(gdb) c
```

> 想省掉拼 rootfs 的麻烦，也可以把 initramfs 直接编进内核：
> `CONFIG_INITRAMFS_SOURCE` 指向一个目录，`make` 会把它打成 cpio 塞进
> `initramfs_data.S`。内核树里 `usr/default_cpio_list` 就是这套机制的入口。

### 4.3 在真机上抓一次系统调用

不想编内核也能读：

```bash
# 看某个进程在干什么
strace -f -tt -T ./your_program

# 看内核函数被调用了多少次
perf list | grep -i sched
perf record -g -- ./your_program
perf report
```

## 5. GDB 断点表

跟一次 `write` 的断点顺序（从用户态进内核到盘上）：

| 断点 | 位置 | 看什么 |
| --- | --- | --- |
| `do_syscall_64` | `arch/x86/entry/syscall_64.c:84` | 系统调用分派点 |
| `vfs_write` | `fs/read_write.c:647` | 进 VFS |
| `ksys_write` | `fs/read_write.c:708` | fd 解析成 `struct file` |
| `ext4_file_write_iter` | `fs/ext4/file.c` | 进具体文件系统 |
| `iomap_write_iter` | `fs/iomap/buffered-io.c` | 拷进页缓存、标脏 |
| `submit_bio` | `block/blk-core.c` | 交给块层 |
| `blk_mq_dispatch_rq_list` | `block/blk-mq.c` | 派发给驱动 |
| `struct task_struct` | `include/linux/sched.h:836` | 想看「当前是谁在跑」时 |

```text
(gdb) set pagination off
(gdb) set print pretty on
(gdb) b vfs_write
(gdb) c
(gdb) bt
(gdb) p *file
```

## 6. 老文章会踩空的地方

网上大量讲内核的中文材料写的是 **4.x / 5.x** 那一代。它们和今天这棵树
差别很大 —— 下面这些是最容易「照着敲但敲不通」的地方（逐条对着本树 grep 过）：

| 老文章里通常这么写 | 现在（本树 `v7.4.0-rc3`）实际是 |
| --- | --- |
| `system_call` / `system_call_fastpath` 宏 | **没有了**。入口是 `arch/x86/entry/entry_64.S` 的 `entry_SYSCALL_64`（`:87`） |
| `sys_call_table` 数组 | **还在，但不管分发**（`arch/x86/entry/syscall_64.c:29`），只剩 `kernel/trace/trace_syscalls.c:1346` 一处引用；真正的分发是 `x64_sys_call`（`:37`）那个 `switch` |
| `vfs_iter_write` 在 `write()` 路径上 | **不是**。`write()` 走 `vfs_write`（`fs/read_write.c:647`）→ `new_sync_write`（`:565`）→ `f_op->write_iter`；`vfs_iter_write`（`:940`）只服务 `writev` 那类带迭代器的路径 |
| `do_syscall_64` 自己读 `regs->orig_ax` 取号 | 取号挪到了**通用代码**里（`include/linux/entry-common.h:151` 的 `syscall_get_nr`），`do_syscall_64` 现在把 `nr` 当参数收 |
| `handle_mm_fault` 一把梭 | 现在拆成 `handle_mm_fault`（`mm/memory.c:6949`）/ `__handle_mm_fault`（`:6714`） |
| `mm->map` 是红黑树 `rb_root` | 现在是 **maple tree**：`mm->mm_mt`（`include/linux/mm_types.h:1231`） |
| `do_signal` | 改名 `get_signal`（`kernel/signal.c:2877`） |
| `send_signal` | 改名 `send_signal_locked`（`kernel/signal.c:1207`） |
| `copy_process` 在 `fs/fork.c` | 搬到 `kernel/fork.c:2029`；入口是 `kernel_clone`（`:2744`），`do_fork` **已删除** |
| `struct task_struct` 在 `include/linux/sched/task.h` | 实际在 `include/linux/sched.h:836` |
| `load_balance` / `find_busiest_cgroup` / `migrate_tasks` | **全没了**。`kernel/sched/balance.c` 不存在，改成 `sched_balance_domains`（`kernel/sched/fair.c:14261`） |
| `kernel/sched/switch.c` 里的 `context_switch` | 合并进 `kernel/sched/core.c:5525` |
| `tick_sched_handle_tick`（`kernel/sched/time.c`） | 改名 `tick_sched_handle`（`kernel/time/tick-sched.c:275`）；`kernel/sched/time.c` **不存在** |
| `__alloc_pages` / `___alloc_pages` | 改名 `__alloc_pages_noprof`（`mm/page_alloc.c:5527`）/ `__alloc_frozen_pages_noprof`（`:5437`） |
| per-CPU 分配在 `mm/page_alloc.c` | 拆到了 `mm/percpu.c`（3392 行） |
| `__vm_area_allocate` | 改名 `vm_area_alloc`（`mm/vma_init.c:32`）；`mm/vma.c`、`mm/vma_exec.c` 是新拆出来的文件 |
| `do_mmap_pgo` | 现在是 `do_mmap`（`mm/mmap.c:338`）→ `mmap_region`（`mm/vma.c:3147`） |
| `load_elf_binary` 在 `fs/exec.c` | 在 `fs/binfmt_elf.c:829` |
| `copy_thread` 在 `arch/x86/kernel/process_64.c` | 搬到了 `arch/x86/kernel/process.c:170`（`process_64.c` 还在，只是换了内容） |
| `blk_mq` 之前的 `generic_make_request` | 早就是 `submit_bio` 一条路了 |
| `->write` / `->read` 文件操作接口 | **还在**（`include/linux/fs.h:1928`），但只是兼容路径；VFS 优先走 `->write_iter`（`fs/read_write.c:664`） |
| `mm_init()` / `init/mm.c` | **没了**。现在是 `mm_core_init_early()`（`mm/mm_init.c:2681`）→ `mm_core_init()`（`:2698`） |
| `mem_map_init` | 改名 `memmap_init`（`mm/mm_init.c:996`） |
| `setup_boot_cpu_data()` | 改名 `early_identify_cpu(&boot_cpu_data)`（`arch/x86/kernel/cpu/common.c:1930`） |
| `page_alloc_init` | 改名 `page_alloc_init_late`（`mm/mm_init.c:2295`）/ `page_alloc_init_cpuhp`（`mm/page_alloc.c:6558`） |
| `setup_per_cpu_pages` | 改名 `setup_per_cpu_pageset`（`mm/page_alloc.c:6429`） |
| `calibrate_delay()` 在 `arch/x86/kernel/tsc.c` | **通用化**了，在 `init/calibrate.c:277`（x86 用 `GENERIC_CALIBRATE_DELAY`） |
| `apic_init()` | 改名 `apic_setup_apic_calls`（`arch/x86/kernel/apic/init.c:83`） |
| `enable_sched_clock_irq()` | 改名 `enable_sched_clock_irqtime`（`kernel/sched/cputime.c:31`） |
| `kernel_execve` 在 `init/main.c` | 在 **`fs/exec.c:1966`** |

> 这张表只是开头。**每章末尾都会带一张本章相关的对照表** ——
> 读内核最费时间的往往不是「看不懂」，而是「看懂了老文章，敲了半天发现
> 那函数早就不在了」。

## 7. 站内已有的几篇

这条线讲「读源码」，站里另有一批讲「怎么用」的文章，配合着看更省力：

| 文章 | 讲什么 | 对应本线第几章 |
| --- | --- | --- |
| [kconfig 和 kbuild 指北](../../linux/kernel-internals/kconfig和kbuild指北.md) | 内核的配置与编译体系 | 02 |
| [Linux 内核模块指北](../../linux/kernel-internals/linux内核模块指北.md) | 模块怎么加载、怎么用 | 02 / 12 |
| [Linux 字符设备指北](../../linux/kernel-internals/linux字符设备指北.md) | 驱动模型的一个最小例子 | 12 |
| [Linux 锁指北](../../linux/kernel-internals/linux锁指北.md) | 锁的基本用法与选择 | 10 |
| [Linux 内存管理指北](../../linux/memory-and-linking/linux内存管理指北.md) | 内存管理工具与概念 | 04 |
| [Linux 系统接口](../../linux/kernel-internals/linux系统接口.md) | 常用的系统调用面 | 01 |

## 8. 版本与参考

本文基于 Linux `v7.4.0-rc3`（`git describe` = `v7.4-rc3-149-g666539eecdf4`）。
内核半年一个大版本（`-rcN` 是候选版），内部 API 半年就可能大改。
**引用具体文件时，请以你手上那棵树的 `git describe` 为准。**

内核自带最好的文档，别舍近求远：

| 想知道 | 看哪 |
| --- | --- |
| 某个子系统怎么用 | `Documentation/<subsystem>/` |
| 内核 coding style | `Documentation/process/coding-style.rst` |
| 提交补丁的流程 | `Documentation/process/submitting-patches.rst` |
| 编译要装什么 | `Documentation/process/changes.rst` |
| 快速裁剪内核 | `Documentation/admin-guide/quickly-build-trimmed-linux.rst` |
| GDB / perf / bpf 工具 | `Documentation/dev-tools/` |

## 下一章

[01 整体架构与一次系统调用的完整链路](../architecture/learning-path/01-整体架构与一次系统调用的完整链路.md)

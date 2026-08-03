# rust ebpf编程

rust中有一个ebpf编程框架aya，其地址为https://github.com/aya-rs/aya。

## 下载依赖

```shell
export RUSTUP_DIST_SERVER=https://rsproxy.cn
export RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

export PATH="/root/.cargo/bin:${PATH}
```text
```shell
rustup install stable
rustup toolchain install nightly --component rust-src
cargo install bpf-linker
cargo install cargo-generate
```text
```shell
cargo generate --git https://github.com/aya-rs/aya-template
```text
```shell
root@linux-kernel-test:~/ebpf_dev# cargo generate --git https://github.com/aya-rs/aya-template
🤷   Project Name: aya_test
🔧   Destination: /root/ebpf_dev/aya_test ...
🔧   project-name: aya_test ...
🔧   Generating template ...
✔ 🤷   Which type of eBPF program? · uprobe
🤷   Target to attach the (u|uret)probe? (e.g libc): libc
🤷   Function name to attach the (u|uret)probe? (e.g getaddrinfo): getaddrinfo
[ 1/25]   Done: .cargo/config.toml                                                                                                                                                              [ 2/25]   Done: .cargo                                                                                                                                                                          [ 3/25]   Done: .gitignore                                                                                                                                                                      [ 4/25]   Done: Cargo.toml                                                                                                                                                                      [ 5/25]   Done: LICENSE-APACHE                                                                                                                                                                  [ 6/25]   Done: LICENSE-GPL2                                                                                                                                                                    [ 7/25]   Done: LICENSE-MIT                                                                                                                                                                     [ 8/25]   Done: README.md                                                                                                                                                                       [ 9/25]   Ignored: pre-script.rhai                                                                                                                                                              [10/25]   Done: rustfmt.toml                                                                                                                                                                    [11/25]   Done: aya_test/Cargo.toml                                                                                                                                                             [12/25]   Done: aya_test/build.rs                                                                                                                                                               [13/25]   Done: aya_test/src/main.rs                                                                                                                                                            [14/25]   Done: aya_test/src                                                                                                                                                                    [15/25]   Done: aya_test                                                                                                                                                                        [16/25]   Done: aya_test-common/Cargo.toml                                                                                                                                                      [17/25]   Done: aya_test-common/src/lib.rs                                                                                                                                                      [18/25]   Done: aya_test-common/src                                                                                                                                                             [19/25]   Done: aya_test-common                                                                                                                                                                 [20/25]   Done: aya_test-ebpf/Cargo.toml                                                                                                                                                        [21/25]   Done: aya_test-ebpf/build.rs                                                                                                                                                          [22/25]   Done: aya_test-ebpf/src/lib.rs                                                                                                                                                        [23/25]   Done: aya_test-ebpf/src/main.rs                                                                                                                                                       [24/25]   Done: aya_test-ebpf/src                                                                                                                                                               [25/25]   Done: aya_test-ebpf                                                                                                                                                                   🔧   Moving generated files into: `/root/ebpf_dev/aya_test`...
🔧   Initializing a fresh Git repository
✨   Done! New project created /root/ebpf_dev/aya_test
```text
## ebpf程序分类

ebpf按照attach point分为多种类型：

- kprobe/kretprobe
- uprobe/uretprobe:用户态进程的函数入口/返回
- tracepoint
- socket filter
- tc
- xdp

### uprobe (function entry)

当用户态程序执行到目标函数的入口时，内核会出发uprobe，并执行对应的ebpf程序。

uprobe可以获取：

- 函数入口参数（寄存器或者栈上）
- 当前进程PID、TGID（线程组）
- 寄存器上下文
- 用户空间内存
- 时间戳

uprobe典型使用场景：

- 记录函数输入参数
- 保存入口时间戳，用于计算耗时
- 当前进程/线程id
- 读取用户态memory

### uretprobe(function probe)

当目标函数执行到return指令时，内核将会触发uretprobe。

uretprobe可以获取如下信息：

- 函数返回值
- 函数耗时
- 当前进程/线程id
- 读取用户态memory

uretprobe用途如下：

- 获取返回值
- 计算函数耗时
- 分析错误代码
- 分析一次调用的完整生命周期

```rust
#[uprobe]
pub fn exec_simple_query_entry(ctx: ProbeContext) -> u32 {
    let query = query_text(&ctx); // 读取用户态 SQL
    let thread_id = ctx.tgid();   // 进程ID
    let pid = ctx.pid();          // 线程ID
    let event = PostgresEntry::ExecSimpleQuery(query, thread_id, pid);
    submit_entry(ctx, event)
}

```text
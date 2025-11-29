# rust ebpf编程

rust中有一个ebpf编程框架aya，其地址为https://github.com/aya-rs/aya。

## 下载依赖

```shell
export RUSTUP_DIST_SERVER=https://rsproxy.cn
export RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup

curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

export PATH="/root/.cargo/bin:${PATH}
```

```shell
rustup install stable
rustup toolchain install nightly --component rust-src
cargo install bpf-linker
cargo install cargo-generate
```

```shell
cargo generate --git https://github.com/aya-rs/aya-template
```
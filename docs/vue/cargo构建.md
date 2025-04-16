# cargo教程

## 替换国内源

- 找到当前用户目录下 **/Users/用户名/.cargo/** 的**.cargo** 文件夹
- 进入**.cargo** 当前目录，在当前目下创建 **config** 文件
- 见下图，打开 **config** 文件，编写以下内容：

```rust
[source.crates-io]
registry = "https://github.com/rust-lang/crates.io-index"
replace-with = 'ustc'
[source.ustc]
registry = "git://mirrors.ustc.edu.cn/crates.io-index"
```

## rust升级

```shell
rustup update
```


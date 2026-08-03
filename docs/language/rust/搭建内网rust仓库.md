# 搭建内网rust仓库

## 进入到本地项目，将依赖下载到本地

```shell
cd project
cargo vendor --respect-source-config
```
此时会在项目目录下生成vendor目录，里面存放了相关依赖。

## 修改包获取路径

在当前项目下创建`.cargo`目录和config.toml文件，写入如下内容：

```shell
mkdir -p .cargo
```
```shell
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"
```
将vendor目录拷贝过来解压。然后编译:

```shell
cargo build
```
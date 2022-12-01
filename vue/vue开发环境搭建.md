# vue开发环境搭建

## 安装node.js

下载node.js安装包安装。

- 配置缓存

  ```shell
  npm config --global get cache # 查看cache路径
  mkdir ~/node_cache
  mkdir ~/node_global
  npm config --global set cache “~/node_cache”
  npm config --global set prefix “~/node_global"
  ```

- 报错的【npm WARN config global `--global`, `--local` are deprecated. Use `--location=global` instead.】，您可以使用 –location=global Command 而不是 global –global，–local 已被弃用

  找到npm脚本文件里面的`prefix -g`替换为`prefix --location=global`

- 修改镜像

  ```shell
  npm config get registry
  npm config set registry=http://registry.npm.taobao.org
  ```

- 查看vue信息

  ```shell
  npm info vue
  ```

- 更新npm

  ```shell
  npm install npm -g
  ```

- 将~/node_global/node_moudle添加到环境变量NODE_PATH

  ```shell
  echo "export NODE_PATH=~/node_global/node_moudle" >> ~/.bashrc
  ```

- 将~/node_global添加到环境变量

  ```shell
  echo "export PATH=$PATH:~/node_global/node_moudle" >> ~/.bashrc
  ```

  

## 安装vue

- 安装vue

```shell
npm install vue -g
```

- 安装vue-router

```shell
npm install vue-router -g
```

- 安装vue-cli

```shell
npm install vue-cli -g
```

## 项目创建

```js
vue init webpack myvue
```


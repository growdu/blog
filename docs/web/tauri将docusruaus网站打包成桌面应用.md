# tauri将docusruaus网站打包成桌面应用

## tauri

tauri可以将vue、react等打包成桌面应用

下载tauri：

```shell
cargo install create-tauri-app
```

下载之前需要安装rust。

安装完成后在docusruaus目录下创建tauri项目。

```shell
cargo-create-tauri-app
✔ Project name · blog
✔ Identifier · com.growd.blog
✔ Choose which language to use for your frontend · TypeScript / JavaScript - (pnpm, yarn, npm, deno, bun)
✔ Choose your package manager · yarn
✔ Choose your UI template · React - (https://react.dev/)
✔ Choose your UI flavor · JavaScript

Template created! To get started run:
  cd blog
  yarn
  yarn tauri android init    

For Desktop development, run:
  yarn tauri dev

For Android development, run:
  yarn tauri android dev
```

先编译docusruaus框架代码

```shell
yarn build
```

编译完成后进入tauri的目录，编辑tauri.conf.json,修改build的内容：

```json
 "build": {
    "beforeDevCommand": "",
    "beforeBuildCommand": "",
    "frontendDist": "../../build"
  },
```

修改完成后在tauri项目下执行如下命令：

```shell
yarn install

```
# react app教程

## 环境准备

- 下载node

- 下载npx

```shell
npm install npx
```

- 创建app

```shell
npx create-react-app automedia
cd automedia
npm start
```

- 构建发布版本

```shell
npm run build
```
- 安装调试工具

```shell
# .vscode/launch.json
{
    // 使用 IntelliSense 了解相关属性。 
    // 悬停以查看现有属性的描述。
    // 欲了解更多信息，请访问: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "type": "chrome",
            "request": "launch",
            "name": "针对 localhost 启动 Chrome",
            "url": "http://localhost:8080",
            "webRoot": "${workspaceFolder}",
            "sourceMapPathOverrides": {
                "webpack:///src/*": "${webRoot}/*"
              }
            }
    ]
}
```

安装chrome dev tools插件，然后npm start，再按f5或者运行中开始调试。

- 安装自动格式化代码工具

```shell
npm install --save husky lint-staged prettier
```

然后在package.json文件中添加如下内容：

```shell
+  "husky": {
+    "hooks": {
+      "pre-commit": "lint-staged"
+    }
+  }
```

- 分析包大小

```shell
npm install --save source-map-explorer
```

在package.json中的scripts里添加如下内容：

```shell
"analyze": "source-map-explorer 'build/static/js/*.js'",
```
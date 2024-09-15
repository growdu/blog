# 搭建npm离线仓库

要在离线环境下使用 Docker 和 Verdaccio 搭建私有的 npm 镜像仓库，你可以按照以下步骤进行操作：

### 1. 安装 Docker
确保你的系统上已经安装了 Docker。如果没有安装，请参考 Docker 的官方文档进行安装。

### 2. 拉取 Verdaccio 镜像
由于是离线环境，首先在有网络的环境下拉取 Verdaccio 的 Docker 镜像，并导出为一个文件：

```bash
docker pull verdaccio/verdaccio
docker save -o verdaccio.tar verdaccio/verdaccio
```

### 3. 在离线环境下加载 Docker 镜像
将导出的 `verdaccio.tar` 文件拷贝到离线环境的机器上，然后使用以下命令加载镜像：

```bash
docker load -i verdaccio.tar
```

### 4. 启动 Verdaccio 容器
在离线环境下启动 Verdaccio 容器，可以使用以下命令：

```bash
docker run -d --name verdaccio -p 4873:4873 verdaccio/verdaccio
```

此命令会在后台启动 Verdaccio，并将其服务暴露在主机的 4873 端口。

### 5. 配置离线 npm 镜像
你可以通过 Verdaccio 的配置文件来控制缓存的包数量和清理策略。通常情况下，默认的配置已经足够使用。

默认的配置文件路径在容器内为 `/verdaccio/conf/config.yaml`。如果需要进行自定义配置，可以先将配置文件拷贝出来进行修改：

```bash
docker cp verdaccio:/verdaccio/conf/config.yaml ./config.yaml
```

修改完成后，将其复制回容器中：

```bash
docker cp ./config.yaml verdaccio:/verdaccio/conf/config.yaml
```

然后重启容器以应用新配置：

```bash
docker restart verdaccio
```

### 6. 配置 npm 使用私有仓库
在客户端机器上，通过以下命令将 npm 的 registry 设置为你的 Verdaccio 私有仓库：

```bash
npm set registry http://<your-server-ip>:4873/
```

现在，你可以正常使用 npm 安装和发布包了。

### 7. 离线环境下的包管理
- **下载依赖包：** 你可以在有网络的环境下预先下载所需的 npm 包，并将它们传输到离线环境中。例如，使用 `npm pack` 下载所需的包。
- **上传包到 Verdaccio：** 使用 `npm publish` 命令将包发布到 Verdaccio 私有仓库中。这样，离线环境中的其他机器也可以从你的私有仓库中安装这些包。

至此，你已经在离线环境中成功搭建了 Verdaccio npm 镜像仓库。

## npm pack下载离线包

`npm pack` 通常用于将某个 npm 包打包成 `.tgz` 文件，而不是直接用于下载项目的依赖包。如果你想要在离线环境中使用某个项目的所有依赖包，可以按照以下步骤操作：

### 1. 在有网络的环境中安装依赖
首先，在有网络的环境中，进入你的项目目录并安装所有依赖包：

```bash
npm install
```

这会根据项目中的 `package.json` 文件安装所有依赖，并将它们下载到 `node_modules` 文件夹中。

### 2. 使用 `npm pack` 打包依赖包
接下来，你需要将 `node_modules` 中的每个依赖包打包成 `.tgz` 文件。你可以使用 `npm pack` 逐个包打包，但手动操作会比较繁琐。为此，可以编写一个脚本来自动打包所有依赖。

下面是一个 Bash 脚本示例，能够打包 `node_modules` 中的每个包：

```bash
#!/bin/bash

# 创建一个目录来存放打包的文件
mkdir -p npm-packages

# 遍历 node_modules 目录并打包每个依赖包
for package in $(ls node_modules); do
  # 忽略 bin 和 .bin 目录
  if [[ "$package" != ".bin" && "$package" != "bin" ]]; then
    # 进入包目录
    cd "node_modules/$package"

    # 打包包并将结果放入上一级的 npm-packages 目录中
    npm pack --pack-destination=../../npm-packages

    # 回到项目根目录
    cd ../../
  fi
done
```

这个脚本会遍历 `node_modules` 目录下的所有依赖包，并使用 `npm pack` 将它们打包到 `npm-packages` 文件夹中。

### 3. 传输依赖包到离线环境
将 `npm-packages` 文件夹传输到离线环境中。在离线环境中，进入该文件夹并逐个安装 `.tgz` 文件：

```bash
npm install ./package-name-version.tgz
```

你也可以将这些 `.tgz` 文件发布到 Verdaccio 私有仓库中，供其他项目使用。

### 4. 安装依赖包
在离线环境中，执行以下命令安装本地 `.tgz` 包或从 Verdaccio 仓库中拉取依赖：

```bash
npm install
```

这样就可以在离线环境中正确安装所需的依赖包了。

通过以上方法，你可以在有网络的环境中准备好项目所需的依赖包，然后将它们传输到离线环境中进行安装和使用。

要将 `node_modules` 目录下的所有包发布到 Verdaccio 私有仓库，可以按照以下步骤进行操作。由于 `node_modules` 目录中包含大量依赖包，这些包可能已经在公共 npm 仓库中存在，因此手动逐个发布效率较低。为了简化操作，可以编写脚本来自动化发布流程。

### 1. 设置 npm Registry 指向 Verdaccio

首先，确保 npm 指向你的 Verdaccio 私有仓库：

```bash
npm set registry http://<your-verdaccio-server>:4873/
```

### 2. 登录到 Verdaccio

使用 `npm adduser` 登录到 Verdaccio 仓库：

```bash
npm adduser --registry http://<your-verdaccio-server>:4873/
```

输入用户名、密码和电子邮件地址。

### 3. 编写脚本发布 `node_modules` 中的包

你可以编写一个脚本，自动遍历 `node_modules` 目录，并将每个包发布到 Verdaccio 仓库中。

以下是一个简单的 Bash 脚本示例，能够发布 `node_modules` 中的包：

```bash
#!/bin/bash

# 设置 Verdaccio 仓库地址
VERDACCIO_REGISTRY="http://<your-verdaccio-server>:4873/"

# 遍历 node_modules 目录中的包
for package in $(ls node_modules); do
  # 忽略 .bin 目录和 scoped packages
  if [[ "$package" != ".bin" && "$package" != "@"* ]]; then
    # 进入包目录
    cd "node_modules/$package"
    
    # 创建 package.json 文件的副本
    cp package.json package.json.bak
    
    # 确保 version 字段存在且唯一
    npm version patch --no-git-tag-version

    # 发布包到 Verdaccio
    npm publish --registry $VERDACCIO_REGISTRY

    # 恢复原始的 package.json 文件
    mv package.json.bak package.json

    # 返回项目根目录
    cd ../../
  fi
done
```

**注意事项：**
- 该脚本仅发布顶级依赖（非嵌套依赖包），如果你需要发布嵌套依赖包，也可以调整脚本递归遍历。
- 使用 `npm version patch --no-git-tag-version` 确保每次发布时包的版本号都递增，避免重复发布相同版本的包。

### 4. 发布 Scoped Packages （如果有）

如果你的项目使用了 Scoped Packages（如 `@scope/package-name`），它们会存储在 `node_modules/@scope/` 目录下。可以通过修改脚本来处理这部分包：

```bash
# 遍历 Scoped Packages
for scope in $(ls node_modules | grep "^@"); do
  for package in $(ls node_modules/$scope); do
    cd "node_modules/$scope/$package"
    
    cp package.json package.json.bak
    npm version patch --no-git-tag-version
    npm publish --registry $VERDACCIO_REGISTRY
    mv package.json.bak package.json
    
    cd ../../../
  done
done
```

这个部分脚本会处理 `node_modules` 目录中的 Scoped Packages。

### 5. 检查发布结果

完成后，你可以通过访问 Verdaccio Web 界面或使用 `npm view` 命令来验证发布的包：

```bash
npm view <package-name> --registry http://<your-verdaccio-server>:4873/
```

### 6. 使用发布的包

在项目中，通过配置 npm 指向 Verdaccio 仓库来使用刚发布的包：

```bash
npm install <package-name>
```

### 注意事项

- **重复发布：** 避免重复发布同一版本的包。确保每个包的版本号在发布前递增。
- **发布顺序：** 如果依赖包之间存在依赖关系，确保先发布底层依赖再发布上层依赖。

通过这些步骤，你可以批量发布 `node_modules` 目录下的所有包到 Verdaccio 私有仓库。
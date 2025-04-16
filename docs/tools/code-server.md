# code-server安装

code-server是C/S架构，一般将服务端部署在linux机器上，然后我们就可以在windows端通过浏览器来访问linux机器上的代码。

## 服务端

```shell
wget https://github.com/coder/code-server/releases/download/v4.5.1/code-server-4.5.1-linux-amd64.tar.gz
tar -xvf code-server-4.5.1-linux-amd64.tar.gz
cd code-server-4.5.1-linux-amd64
./code-server --host ip --port port
```

## 客户端

客户端可以使用chrome的app模式来启动，具体执行脚本如下：

```shell
# 1.bat
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app=http://host:port/
```

服务端启动后，双击1.bat文件即可以访问linux服务器代码。
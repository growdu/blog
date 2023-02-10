# leanote使用教程

## leanote

leanote的特点就是简约、免费、开源、支持 Markdown 语法，支持程序代码高亮、笔记历史记录、支持笔记分享协作、将笔记发布成博客等功能。

## leanote安装

leanote使用mongodb存储数据，因而在安装部署之前需要先安装mongodb。

需要特别注意的是，当前最新版本leanote2.6.1与最新的mongodb6.0.4不兼容，使用mongodb6.0.4时，leanote在连接mongodb时会报错“panic: no reachable server”,因而建议选择mongodb4.0.28。

### mongodb安装

```shell
wget https://fastdl.mongodb.org/win32/mongodb-win32-x86_64-2008plus-ssl-4.0.28.zip
```

解压缩后将mongodb的bin目录添加的环境变量。然后输入如下命令检测mongodb是否已正常安装：

```shell
mongod --version
```

如在windows上输出如下命令，则表明mongodb安装成功：

```shell
$ mongod --version
db version v6.0.4
Build Info: {
    "version": "6.0.4",
    "gitVersion": "44ff59461c1353638a71e710f385a566bcd2f547",
    "modules": [],
    "allocator": "tcmalloc",
    "environment": {
        "distmod": "windows",
        "distarch": "x86_64",
        "target_arch": "x86_64"
    }
}
```

安装成功后需要部署启动mongodb，一般将mongodb部署为一个服务，以windows部署为例。

- 首先先创建一个mongodb.conf的文件，在文件中写入如下内容

  ```shell
  dbpath=F:\mongodb\data            # 数据库文件
  logpath=F:\mongodb\logs\mongodb.log    # 日志文件
  logappend=true                        # 日志采用追加模式，配置后mongodb日志会追加到现有的日志文件，不会重新创建一个新文件
  journal=true                        # 启用日志文件，默认启用
  quiet=true                            # 这个选项可以过滤掉一些无用的日志信息，调试模式下设置为 false
  port=27017                            # 端口号 默认为 27017
  # 设置绑定ip
  bind_ip = 127.0.0.1
  # 设置端口
  port = 27017
  ```

- 然后使用如下命令注册mongodb为服务(需要以管理员身份运行)

  ```shell
  mongod --config "F:\mongodb.conf" --install
  # 移除服务
  mongod --remove
  ```

- 注册成功后启动mongodb

  ```shell
  net start mongodb
  # 停止服务
  net stop mongodb 
  ```

### 安装leanote

使用如下命令下载leanote最新安装包，或者也可以直接到[github](https://github.com/leanote/leanote)上去下载.

```shell
wget https://phoenixnap.dl.sourceforge.net/project/leanote-bin/2.6.1/leanote-linux-amd64-v2.6.1.bin.tar.gz
```

下载完成后进行解压，然后进入到conf目录，修改如下内容：

```shell
site.url=http://localhost:9000 # localhost一定要换成自己的ip，否则客户端无法连接
db.host=127.0.0.1 # mongodb的ip
db.port=27017
```

### 导入数据

在运行前需要导入备份数据，使用mongorestore导入，如果找不到mongorestore，需使用如下命令手动下载：

```shell
wget https://fastdl.mongodb.org/tools/db/mongodb-database-tools-windows-x86_64-100.6.1.zip
```

下载解压后将bin目录下文件复制到mongodb的bin目录下。然后使用如下命令将备份数据导入到mongodb：

```shell
mongorestore -h localhost -d leanote --dir C:\user1\leanote\mongodb_backup\leanote_install_data
```

导入成功数据后将包含两个默认用户：

```shell
user1 username: admin, password: abc123 (管理员, 只有该用户可以管理后台)  
user2 username: demo@leanote.com, password: demo@leanote.com (仅供体验使用)
```

然后进入到bin目录下面，双击运行run.dat。

若运行失败，切换到管理员身份运行。

若运行失败查不到原因，可在命令行中运行run.bat或者在run.bat末尾加上pause。

运行成功后，cmd窗口会显示监听的端口，使用ip:port的方式访问leanote。如http://localhost:9000.


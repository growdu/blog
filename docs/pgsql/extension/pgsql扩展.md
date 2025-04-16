# pg扩展开发

pg提供了扩展机制可以在不动[postgresql](https://so.csdn.net/so/search?q=postgresql&spm=1001.2101.3001.7020)源代码的情况下，增强postgresql的一些功能。

在数据库shell里面，使用如下命令可以加载一个插件：

```sql
create extension extension_name;
```

在数据库内执行上述命令之前，需要有两个重要的文件放在共享目录/install_directory/share/extension之下，分别是：

1. 控制文件，以control为后缀名

   文件的格式必须是extension_name.control，它用于告诉PostgreSQL此扩展的一些基础信息

2. sql脚本文件，以sql为后缀名

   格式为extension–version.sql，包含了你想要添加的函数。如果想要通过SQL修改命令更新扩展，新版本的文件应该是extension–old_version–new_version.sql。


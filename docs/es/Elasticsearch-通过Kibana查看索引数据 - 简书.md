## Elasticsearch-通过Kibana查看索引数据

[![](https://cdn2.jianshu.io/assets/default_avatar/14-0651acff782e7a18653d7530d6b27661.jpg)](https://www.jianshu.com/u/512430c09ee3)

0.9152018.10.10 19:15:10字数 1,500阅读 70,733

#### 引言

___

  当数据存储到Elasticsearch后，我们希望能方便的通过界面进行查询，有两个工具能够满足我们的需要，一个是Elasticsearch-head插件，另一个是Kibana，笔者认为两个工具各有千秋，大家可以自行体会，不过就安装步骤来说，Elasticsearch-head真心麻烦，本文主要介绍如何部署Kibana，并使用Kibana来查看Elasticsearch中的索引数据。

#### 部署Kibana

___

1.  ###### 下载Kibana
    

  在[Kibana官方网站](https://www.elastic.co/products/kibana)找到[下载链接](https://www.elastic.co/products/kibana)，找到和Elasticsearch适配的版本，我之前Elasticsearch安装的是6.4.2版本，所以我下载的是6.4.2的Linux 64位版本。

![](https://upload-images.jianshu.io/upload_images/12975960-2cde347eefa9efd5.png?imageMogr2/auto-orient/strip|imageView2/2/w/808/format/webp)

download kibana

2.  ###### 解压压缩文件
    

运行如下命令解压

```
tar zxvf kibana-6.4.2-linux-x86_64.tar.gz
```

3.  ###### 修改配置
    

运行如下命令修改Kibana配置文件【kibana.yml】

```
vi kibana-6.4.2-linux-x86_64/config/kibana.yml
```

这个配置文件里面包含了Kibana和访问Elasticsearch的一些配置

-   server.port: Kibana服务的访问端口
-   server.host: Kibana服务绑定的地址（Kibana部署所在的服务器），可以是IP也可以是机器名，如果设置成localhost，则只能在本机访问
-   server.basePath: 如果Kibana服务是通过代理访问的，需要设置成代理的路径，Kibana会根据此项判断是否需要从收到的请求中删除basePath，结尾不要添加斜杠【/】
-   server.rewriteBasePath: 定义Kibana是否需要重写以server.basePath为前缀的请求路径，或者要求它们由反向代理重写。在Kibana 6.3之前始终为false，从Kibana 7.0开始将默认为true
-   server.maxPayloadBytes: 请求的最大字节数
-   server.name: Kibana服务的名称，用于标识Kibana服务使用的目的
-   elasticsearch.url: Elasticsearch服务的URL
-   elasticsearch.preserveHost: 设置为true时，Kibana使用server.host设置中指定的主机名；设置为false时，Kibana使用连接到此Kibana实例的主机的主机名，即Elastic
-   kibana.index: Kibana在Elasticsearch中创建的索引，用于存储保存的搜索、可视化和仪表板数据。
-   kibana.defaultAppId: 默认加载的应用程序
-   elasticsearch.username: 访问Elasticsearch的用户名，Elasticsearch启用基本的身份认证时使用
-   elasticsearch.password: 访问Elasticsearch的密码，Elasticsearch启用基本的身份认证时使用
-   server.ssl.enabled: Kibana服务是否启用SSL
-   server.ssl.certificate: Kibana服务SSL证书文件路径
-   server.ssl.key: Kibana服务SSL秘钥文件路径
-   elasticsearch.ssl.certificate: Elasticsearch PEM格式的SSL证书文件路径
-   elasticsearch.ssl.key: Elasticsearch PEM格式的SSL秘钥文件路径
-   elasticsearch.ssl.certificateAuthorities: 为Elasticsearch实例指定证书颁发机构的PEM文件的路径
-   elasticsearch.ssl.verificationMode: Elasticsearch提供的证书验证，默认值为full，如果要忽略，可设置为none
-   elasticsearch.pingTimeout: Elasticsearch响应PING的超时时间，单位是毫秒
-   elasticsearch.requestTimeout: Elasticsearch后端响应请求的超时时间，单位是毫秒
-   elasticsearch.requestHeadersWhitelist: 通过Kibana客户端请求Elasticsearch时需要发送的请求头列表
-   elasticsearch.customHeaders: 要发送到Elasticsearch的请求头名称和值，无论elasticsearch.requestHeadersWhitelist配置如何，客户端请求头都不能覆盖任何自定义请求头
-   elasticsearch.shardTimeout: Elasticsearch等待分片响应的超时时间，单位是毫秒，设置为0可以禁用
-   elasticsearch.startupTimeout: 在重试之前Kibana启动时等待Elasticsearch的超时时间，单位是毫秒
-   elasticsearch.logQueries: 记录发送到Elasticsearch的查询，如果要启用还需要将logging.verbose设置为true
-   pid.file: Kibana的进程ID文件路径
-   logging.dest: 指定Kibana保存日志输出文件的位置
-   logging.silent: 设置是否输出日志，设置为true时禁止所有日志输出
-   logging.quiet: 设置为true时禁止除错误消息之外的所有日志输出
-   logging.verbose: 设置为true以记录所有事件，包括系统使用信息和所有请求
-   ops.interval: 设置获取系统和进程性能指标的时间间隔，单位是毫秒，最小值是100，默认为5000
-   i18n.defaultLocale: 默认区域设置，可用于国际化，国际化文件存储位置kibana-6.4.2-linux-x86\_64/src/core\_plugins/kibana/translations/

  我修改了【server.host】，将这个从localhost修改为Kibana部署服务器的IP地址

![](https://upload-images.jianshu.io/upload_images/12975960-966b713980c8cba6.png?imageMogr2/auto-orient/strip|imageView2/2/w/1055/format/webp)

server host

  同时还修改了【elasticsearch url】，因为Elasticsearch服务部署在另外的服务器，将其修改为Elasticsearch服务部署的地址

![](https://upload-images.jianshu.io/upload_images/12975960-b4981535b3d6572b.png?imageMogr2/auto-orient/strip|imageView2/2/w/672/format/webp)

elasticsearch url

3.  ###### 启动Kibana
    

运行如下命令后台启动

```
nohup kibana-6.4.2-linux-x86_64/bin/kibana &
```

启动后可以看到进程ID

![](https://upload-images.jianshu.io/upload_images/12975960-aa775f7ec71a088a.png?imageMogr2/auto-orient/strip|imageView2/2/w/756/format/webp)

start kibana

#### 使用Kibana查看Elasticsearch索引数据

___

安装成功之后使用浏览器通过访问【http://{IP}:5601】打开Kibana界面，找到Management菜单

![](https://upload-images.jianshu.io/upload_images/12975960-8300f85296349b89.png?imageMogr2/auto-orient/strip|imageView2/2/w/1200/format/webp)

menu

这里能够查看Elasticsearch的索引，不得不说这是Kibana的一个改进，曾记得在5.6.3版本的时候是无法在Kibana中看到Elasticsearch的索引列表的，对于低版本的Kibana，我们可以在浏览器中输入如下地址来查看Elasticsearch的索引列表。

```
http://{Elasticsearch IP}:9200/_cat/indices?v
```

![](https://upload-images.jianshu.io/upload_images/12975960-9e7a916d41b2d5bc.png)

index list

然后点击Kibana的【Management】菜单，创建Index Patterns

![](https://upload-images.jianshu.io/upload_images/12975960-dc49e43c8f930213.png)

create index patterns

添加完成后就可以点击【Discover】菜单进行查看了，还可以添加各种查询条件进行过滤

![](https://upload-images.jianshu.io/upload_images/12975960-f7cb3a622c21ded5.png)

query index

#### 避坑指南

___

1.  ###### UnhandledPromiseRejectionWarning: Error: listen EADDRNOTAVAIL xxx.xx.xx.xx:5601
    

如果你用的是云主机，并且碰到了启动Kibana出现了上面的错误

![](https://upload-images.jianshu.io/upload_images/12975960-949dc5917ea4b4b3.png)

error

这是因为云主机一般有双IP，即内外网，**`切记：这个时候server.host一定要设置为内网IP`**

BTW，简书能不能支持一下标准的markdown变字体颜色的语法啊，要设置个红色，只能用\`xxx\`，但是这样字体又变小了
    

### 推荐阅读[更多精彩内容](https://www.jianshu.com/)

-   Spring Cloud为开发人员提供了快速构建分布式系统中一些常见模式的工具（例如配置管理，服务发现，断路器，智...
    
-   原文链接：https://docs.spring.io/spring-boot/docs/1.4.x/refere...
    
-   Spring Boot 参考指南 介绍 转载自:https://www.gitbook.com/book/qbgb...
    
    [![](https://upload.jianshu.io/users/upload_avatars/1687958/9b5b9b6de8b7.jpg?imageMogr2/auto-orient/strip|imageView2/1/w/48/h/48/format/webp)毛宇鹏](https://www.jianshu.com/u/d3ea915e1e0f)阅读 45,372评论 6赞 345
    
-   要加“m”说明是MB，否则就是KB了. -Xms：初始值 -Xmx：最大值 -Xmn：最小值 java -Xms1...
    
-   Elastic+logstash+head简单介绍 一. 概述 ElasticSearch是一个基于Lucene的...
    
    [![](https://cdn2.jianshu.io/assets/default_avatar/6-fd30f34c8641f6f32f5494df5d6b8f3c.jpg)柒月失凄](https://www.jianshu.com/u/a62227da9a51)阅读 3,949评论 0赞 4
以《刑法》文本.txt为例。

## 一、格式化数据

1，首先，ElasticSearch只能接收格式化的数据，所以，我们需要将文本文件转换为格式化的数据---json。

下图为未处理的文本文件。

![](https://ask.qcloudimg.com/http-save/7774611/wvw7ux1h70.png)

2，这里，使用python文件操作，将文本格式化为ElasticSearch可识别的json格式。

```
#python 3.6
#!/usr/bin/env python

# -*- coding:utf-8 -*-
__author__ = 'BH8ANK'
'''
最终将输出格式改为
{"index":{"_index":"xingfa","_id":1}}
{"text_entry":"犯罪的行为或者结果有一项发生在中华人民共和国领域内的，就认为是在中华人民共和国领域内犯罪。"}

'''


'''读取文件
'''
a = open(r"D:\xingfa.txt", "r",encoding='utf-8')
out = a.read()
#print(out)
TypeList = out.split('\n')
#print(TypeList)

lenth = len(TypeList)
print(lenth)

number = 1
ju_1 = '{"index":{"_index":"xingfa","_id":'
ju_2 = '{"text_entry":"'

# print(ju_1)
for x in TypeList:

    res_1 = ju_1 + str(number) + '}}'+'\n'
    print(res_1)
    a = open(r"D:\out.json", "a", encoding='UTF-8')
    a.write(res_1)


    res_2 = ju_2 + x + '"}'+'\n'
    print(res_2)
    a = open(r"D:\out.json", "a", encoding='UTF-8')
    a.write(res_2)


    a.close()
    number+=1
```

3，执行后，输出的json内容为：

![](https://ask.qcloudimg.com/http-save/7774611/cstnnelanl.png)

## 1，我们要为即将导入的数据，建立映射。此操作可以在kibana或命令行完成。

```
PUT /xingfa
{
 "mappings": {
  "doc": {
       "properties": {
          "text_entry":{"type":"keyword"}
       }  
  }
 }
}
```

## 2，登录虚拟机，将之前生成的out.json文件，导入到对应ElasticSearch集群中。

![](https://ask.qcloudimg.com/http-save/7774611/5zhzisdhjz.png)

我们的ES组网情况如上图。

操作如下：

![](https://ask.qcloudimg.com/http-save/7774611/w7yhnkvnxy.png)

命令如下：

```
curl -H 'Content-Type: application/x-ndjson' -XPOST '10.0.0.19:9200/xingfa/doc/_bulk?pretty' --data-binary @out.json
```

等待命令执行完成后，即可登录kibana去查询对应的数据了。

![](https://ask.qcloudimg.com/http-save/7774611/fxneg9sl3a.png)

使用查询语句：

```
GET /xingfa/_search/
{
  "query": { "match_all": {} },
  "size":"9999"                         //此处设置为9999，主要原因是，不加参数的话，默认搜索结果仅显示部分，一般是5.
}
```

也可以直接在虚拟机命令行里，查询这个索引，确认数据是否已经完成上传。

![](https://ask.qcloudimg.com/http-save/7774611/wy2t4hkfx4.png)

使用查询语句：

```
curl -XGET "http://10.0.0.19:9200/xingfa/_search/" -H 'Content-Type: application/json' -d'
{
  "query": {
    "match_all": {}
  },
  "size": "9999"
}'
```

至此，完成数据导入。

本文参与

[腾讯云自媒体分享计划](https://cloud.tencent.com/developer/support-plan)，分享自作者个人站点/博客。

原始发表：2019-03-08 ，

如有侵权请联系 [cloudcommunity@tencent.com](mailto:cloudcommunity@tencent.com) 删除

推荐

[【机器学习实战】第15章 大数据与MapReduce](https://cloud.tencent.com/developer/article/1014843)

第15章 大数据与MapReduce ? 大数据 概述 大数据: 收集到的数据已经远远超出了我们的处理能力。 大数据 场景 假如你为一家网络购物商店工作，很多用户访问该网站，其中有些人会购买商品，有些人则随意浏览后就离开。 对于你来说，可能很想识别那些有购物意愿的用户。 那么问题就来了，数据集可能会非常大，在单机上训练要运行好几天。 接下来：我们讲讲 MapRedece 如何来解决这样的问题 MapRedece Hadoop 概述 Hadoop 是 MapRedece 框架的一个免费开源实

![【机器学习实战】第15章 大数据与MapReduce](https://ask.qcloudimg.com/http-save/yehe-1148651/kw7uy1uz83.jpeg)

[R中的数据导入与导出](https://cloud.tencent.com/developer/article/1016857)

1、数据的导入 导入文本文件 使用read.table函数导入普通文本文件 read.table(file,header=FALSE,sep="",...) ? #导入csv文件 data1 <- read.table("1.csv", header=TRUE, sep=",", fileEncoding="UTF-8", stringsAsFactors=FALSE); data2 <- read.csv("2.txt", header=TRUE, sep=","); #不带表头 data2 <- r

![R中的数据导入与导出](https://ask.qcloudimg.com/http-save/yehe-1165572/85ngco30go.png)

[部署和使用kibana](https://cloud.tencent.com/developer/article/1032302)

背景 本文将主要介绍ELK的可视化工具Kibana的部署和使用。主要分为三个步骤来实现最终呈现： 　　1.导入数据到ES； 　　2.部署kibana并完成配置； 　　3.使用kibana生成可视化数据。 　　废话不多说下面直接上步骤了。 部署 　　1.下载配置kibana --下载kibana  　　2.导入数据到ES这里写一个版本注意jdbc的版本 --下载 elasticsearch-jdbc 这里测试 wget http://xbib.org/repository/org/xbib

![部署和使用kibana](https://ask.qcloudimg.com/http-save/yehe-1217611/prmnhx9loh.png)

[个人情报收集系统浅谈](https://cloud.tencent.com/developer/article/1040951)

\*文章原创作者： ArthurKiller，转载请注明来自FreeBuf（FreeBuf.COM） 前言 IT的全称为information technology，即为信息科技。可以说在这个网络世界中，信息即为这个世界中的根本，而掌握了信息也就掌握了IT世界，这个理论同样适用于网络安全行业。 任何网络攻击，前期最重要的部分即是信息收集。个人如果要对一家大企业做全面的信息收集是很痛苦的，只有APT组织或者政府才有那个能力。 虽然我是一个菜鸟，但是我还是想尝试看看搭建一个个人情报收集系统是否可行。小菜一枚，不喜

![个人情报收集系统浅谈](https://ask.qcloudimg.com/http-save/yehe-1268449/70xaa2ma7c.jpeg)

[MapReduce编程模型](https://cloud.tencent.com/developer/article/1042373)

通过WordCount程序理解MapReduce编程模型 WordCount，名为单词统计，功能是统计文本文件中每个单词出现的次数。例如下图中，有两个文本（蓝色），其中一个含有两个单词（Hadoop和HDFS），另一个含有两个单词（Hadoop和MapReduce），通过统计计算，最终结果（橙色）中显示Hadoop单词出现2次，HDFS单词出现1次，MapReduce单词出现1次。 📷 WordCount是最简单也是最体现MapReduce思想的程序之一，被成为MapReduce版的HelloWorld。

![MapReduce编程模型](https://ask.qcloudimg.com/http-save/yehe-1008345/9skzwqvbic.jpeg)

[Elasticsearch分片、副本与路由(shard replica routing)](https://cloud.tencent.com/developer/article/1050441)

本文讲述，如何理解Elasticsearch的分片、副本和路由策略。 1、预备知识 1）分片（shard） Elasticsearch集群允许系统存储的数据量超过单机容量，实现这一目标引入分片策略shard。在一个索引index中，数据（document）被分片处理（sharding）到多个分片上。Elasticsearch屏蔽了管理分片的复杂性，使得多个分片呈现出一个大索引的样子。 2）副本（replica） 为了提升访问压力过大是单机无法处理所有请求的问题，Elasticsearch集群引入了副本策略r

![Elasticsearch分片、副本与路由(shard replica routing)](https://ask.qcloudimg.com/http-save/yehe-1225216/anw013f4po.png)

[python分布式环境下的限流器](https://cloud.tencent.com/developer/article/1050465)

项目中用到了限流，受限于一些实现方式上的东西，手撕了一个简单的服务端限流器。 服务端限流和客户端限流的区别，简单来说就是： 1）服务端限流 对接口请求进行限流，限制的是单位时间内请求的数量，目的是通过有损来换取高可用。 例如我们的场景是，有一个服务接收请求，处理之后，将数据bulk到Elasticsearch中进行索引存储，bulk索引是一个很耗费资源的操作，如果遭遇到请求流量激增，可能会压垮Elasticsearch（队列阻塞，内存激增），所以需要对流量的峰值做一个限制。 2）客户端限流 限制的是客户端进

[【科技】谷歌将人工智能带入数据透视表 表单功能立刻升级！](https://cloud.tencent.com/developer/article/1051359)

现在，谷歌的电子表格（Spreadsheet）应用获得了许多新功能，目的是让数据透视表（一种强大的数据分析工具）变得更容易访问。 ? 用户将能够从表格的“Explore”选项卡中获得建议，该选项卡的目的是通过吐出数据透视表来回答有关馈送到程序中的数据的问题，该数据表可以吸收多个数据，并输出相关的答案。此外，当用户在电子表格中创建一个应用时，该应用会自动显示不同的数据透视表设置。 数据透视表是电子表格用户使用的关键工具之一。他们可以快速地对数据进行切片和切块，从而获得重要的见解。例如，有人可以创建一个数据

![【科技】谷歌将人工智能带入数据透视表 表单功能立刻升级！](https://ask.qcloudimg.com/http-save/yehe-1308977/pt43hjhmoi.jpeg)

[ElasticSearch + Logstash + Kibana 日志采集](https://cloud.tencent.com/developer/article/1051430)

本文节选自《Netkiller Monitoring 手札》 ElasticSearch + Logstash + Kibana 一键安装 配置 logstash 将本地日志导入到 elasticsearch input { file { type => "syslog" path => \[ "/var/log/maillog", "/var/log/messages", "/var/log/secure" \] start\_position => "beginning"

![ElasticSearch + Logstash + Kibana 日志采集](https://ask.qcloudimg.com/http-save/yehe-1313619/lu04fldx55.png)

[怎样将 MySQL 数据表导入到 Elasticsearch](https://cloud.tencent.com/developer/article/1051451)

本文节选自《Netkiller Database 手札》 MySQL 导入 Elasticsearch 的方法有很多，通常是使用ETL工具，但我觉得太麻烦。于是想到 logstash 。 23.8. Migrating MySQL Data into Elasticsearch using logstash 23.8.1. 安装 logstash 安装 JDBC 驱动 和 Logstash curl -s https://raw.githubusercontent.com/oscm/shell/maste

[sqoop数据导入总结](https://cloud.tencent.com/developer/article/1055063)

这是黄文辉同学处女作，大家支持！ 其他相关文章：元数据概念 Sqoop主要用来在Hadoop(HDFS)和关系数据库中传递数据,使用Sqoop,我们可以方便地将数据从关系型数据库导入HDFS,或者将数据从关系型数据库导入HDFS,或者将从HDFS导出到关系型数据库. 从数据库导入数据 import命令参数说明 参数说明--append将数据追加到HDFS上一个已存在的数据集上--as-avrodatafile将数据导入到Avro数据文件--as-sequencefile将数据导入到SequenceFile

[Elasticsearch大文件检索性能提升20倍实践（干货）](https://cloud.tencent.com/developer/article/1066368)

少废话，直接开始。 1、大文件是多大？ ES建立索引完成全文检索的前提是将待检索的信息导入Elaticsearch。 项目中，有时候需要将一些扫描件、PDF文档、Word、Excel、PPT等文档内容导入Elasticsearch。 比如：将《深入理解Elasticsearch》这边书导入ES，而这边书的全文内容被识别后的大小可能为3MB——5MB以上的字节。 存入ES后是一个content字段，对这个content执行全文检索&高亮显示，就存在检索效率低的问题，会耗时30S以上的时间。 这点，作为习惯了搜

![Elasticsearch大文件检索性能提升20倍实践（干货）](https://ask.qcloudimg.com/http-save/yehe-1390885/r0460w7blk.jpeg)

[实战 | Elasticsearch打造知识库检索系统](https://cloud.tencent.com/developer/article/1066380)

题记 源自“死磕Elasticsearch”技术群里的讨论问题： ——我想用es做个类似于知识库的东西,所以需要索引一些pdf、word之类的文件，这个你之前有试过吗？能给个方向吗？ 我的思考如下： 1、pdf、Office类的文档如何被ES索引？ 更确切的说，pdf、Office类文档（word，ppt，excel等）如何导入ES中。 如图所示： ? 问题转嫁为：如何将Office类文档、PDF文档导入ES建立索引，并提供全文检索服务？ 2、Elasticsearch支持的最大待检索字段的

![实战 | Elasticsearch打造知识库检索系统](https://ask.qcloudimg.com/http-save/yehe-1390885/l7gspxh7oj.jpeg)

[企业该如何构建大数据平台【技术角度】](https://cloud.tencent.com/developer/article/1074424)

问题导读 1.作为一个技术人员，你认为该如何搭建大数据平台？ 2.构建大数据平台，你认为包括哪些步骤？ 3.本文是如何构建大数据平台的？ 亲身参与，作为主力完成了一个信息大数据分析平台。中间经历了很多问题，算是有些经验，因而作答。 整体而言，大数据平台从平台部署和数据分析过程可分为如下几步： 1、linux系统安装 一般使用开源版的Redhat系统–CentOS作为底层平台。为了提供稳定的硬件基础，在给硬盘做RAID和挂载数据存储节点的时，需要按情况配置。例如，可以选择给HDFS的namenode

[从零开始写项目第四篇【搭建Linux环境】](https://cloud.tencent.com/developer/article/1080723)

使用SSH连接Linux环境 经过十多天的时间，我的网站备案终于完成了…接下来我就收到了阿里云的邮件。它让我在网站首页的尾部添加备案号，貌似还需要去公安网站中再备案什么资料的。 2017年11月20日19:06:26在图书馆并没有带身份证、于是就得放一下了。 接下来，我就是要把我写的东西放在Linux下了。首先，我得连接Linux系统，通过阿里云的远程服务可以连接得到。 密码可以在阿里云中设置，用户名是root，开始的时候我并不知道用户名是root，看了一下子文档才知道… 然后阿里云文档中还说了可是使用ss

![从零开始写项目第四篇【搭建Linux环境】](https://ask.qcloudimg.com/http-save/yehe-1287328/trzntv7g7e.jpeg)

[AI知识搜索利器：基于ElasticSearch构建专知实时高性能搜索系统](https://cloud.tencent.com/developer/article/1086992)

【导读】今天向大家介绍下ElasticSearch在专知搜索中的使用。ElasticSearch是一个基于Lucene的搜索服务器，是当前流行的企业级搜索引擎。设计用于云计算中，能够达到实时搜索，稳定，可靠，快速，安装使用方便。我们利用ES对专知的AI内容库进行了索引，用户可以快速找到所需AI知识资源。下面由我们专知团队后台支柱李泳锡同学向大家分享下。 ElasticSearch简介 Elasticsearch（以下简称ES）是一个基于Apache Lucene的实时分布式搜索分析引擎，它能够让你以极低的

![AI知识搜索利器：基于ElasticSearch构建专知实时高性能搜索系统](https://ask.qcloudimg.com/http-save/yehe-1565119/qynfecvlh6.jpeg)

[python数据分析笔记——数据加载与整理](https://cloud.tencent.com/developer/article/1092111)

Python数据分析——数据加载与整理 总第47篇 ▼ ? （本文框架） 数据加载 导入文本数据 ? 1、导入文本格式数据（CSV）的方法： 方法一：使用pd.read\_csv()，默认打开csv文件。 ? 9、10、11行三种方式均可以导入文本格式的数据。 特殊说明：第9行使用的条件是运行文件.py需要与目标文件CSV在一个文件夹中的时候可以只写文件名。第10和11行中文件名ex1.CSV前面的部分均为文件的路径。 方法二：使用pd.read.table(),需要指定是什么样分隔符的文本文件。用sep=”

![python数据分析笔记——数据加载与整理](https://ask.qcloudimg.com/http-save/yehe-1608153/v0r1pjyy1w.png)

[用Kibana和logstash快速搭建实时日志查询、收集与分析系统](https://cloud.tencent.com/developer/article/1114755)

日志的分析和监控在系统开发中占非常重要的地位，系统越复杂，日志的分析和监控就越重要，常见的需求有: 根据关键字查询日志详情 监控系统的运行状况 统计分析，比如接口的调用次数、执行时间、成功率等 异常数据自动触发消息通知 基于日志的数据挖掘 很多团队在日志方面可能遇到的一些问题有: 开发人员不能登录线上服务器查看详细日志，经过运维周转费时费力 日志数据分散在多个系统，难以查找 日志数据量大，查询速度慢 一个调用会涉及多个系统，难以在这些系统的日志中快速定位数据 数据不够实时 常见的一些重量级的开源Trace系

![用Kibana和logstash快速搭建实时日志查询、收集与分析系统](https://ask.qcloudimg.com/http-save/yehe-1751832/2nitmlor85.jpeg)

[原创投稿 | 如何为Django添加中文搜索服务](https://cloud.tencent.com/developer/article/1114886)

云豆贴心提醒，本文阅读时间7分钟 在使用python的过程中，必然会设计到如何创建web应用，而搜索功能却最为常见，该文档包含了如何整合haystack，elasticsearch、ik中文分词到django应用中。 测试应用版本 安装 python包安装 elasticsearch安装 elasticsearch基于java，所以需要先安装java。 elasticsearch-analysis-ik安装 安装maven 注意安装必须使用对应的版本，测试也是如此，比如此处使用1.9.

![原创投稿 | 如何为Django添加中文搜索服务](https://ask.qcloudimg.com/http-save/yehe-1751832/e0rwiuozzb.jpeg)

[win10 spark+scala+eclipse+sbt 安装配置](https://cloud.tencent.com/developer/article/1120457)

转载请务必注明原创地址为：http://dongkelun.com/2018/03/15/winSparkConf/
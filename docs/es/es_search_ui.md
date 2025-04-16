### 手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎

©著作权归作者所有：来自51CTO博客作者zhuhuix的原创作品，请联系作者获取转载授权，否则将追究法律责任

#### 文章目录

-    [一、需求分析](https://blog.51cto.com/u_208751/5637991#_1)
-    [二、ElasticSearch](https://blog.51cto.com/u_208751/5637991#ElasticSearch_6)
-    [三、FSCrawle](https://blog.51cto.com/u_208751/5637991#FSCrawle_20)
-    [三、SearchUI](https://blog.51cto.com/u_208751/5637991#SearchUI_87)
-    [五、运行测试](https://blog.51cto.com/u_208751/5637991#_109)

## 一、需求分析

-   公司内部存在大量的设备维修保养office文档，设备人员在检索特定的维修保养知识的时候，需要根据目录的索引文件，在服务器上先找出有可能相关的文件列表，再一一打开进行检索，效率低下且体验性差。
-   用户希望利用现有文档系统（编制，发布，升版等文控管理有专人负责）不变，搭建一个可以根据关键词条进行检索的文件搜索引擎，提高效率及提升体验度。

-   本文将通过ElasticSearch(开源搜索引擎),FSCrawler（文件爬虫，将文档“上传”到 elasticsearch）, SearchUI(使用elasticsearch搜索 API 的前端页面)，搭建一个文件搜索引擎系统。

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot](https://s2.51cto.com/images/blog/202208/31171754_630f274236cbe61599.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

## 二、ElasticSearch

-   我们首先从 [(https://www.elastic.co/cn/downloads/elasticsearch](https://www.elastic.co/cn/downloads/elasticsearch)下载文件（本文以windows版本为例）。

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_02](https://s2.51cto.com/images/blog/202208/31171754_630f2742445f027025.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   解压文件

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_搜索_03](https://s2.51cto.com/images/blog/202208/31171754_630f274250dc271857.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-     
    

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_04](https://s2.51cto.com/images/blog/202208/31171754_630f274260fba34146.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   下载安装jdk并设置java环境变量

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_05](https://s2.51cto.com/images/blog/202208/31171754_630f27427b40f74295.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   进入到解压后的bin目录，双击elasticsearch.bat文件运行

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_06](https://s2.51cto.com/images/blog/202208/31171754_630f27428b69e39059.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-     
    

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_搜索_07](https://s2.51cto.com/images/blog/202208/31171754_630f2742957f958048.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   验证ElasticSearch是否启动成功：使用浏览器访问_ [http://localhost:9200](http://localhost:9200/)_，看到以下页面就代表安装成功了

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_08](https://s2.51cto.com/images/blog/202208/31171754_630f2742a03ef4714.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

## 三、FSCrawle

-   我们再从 [https://fscrawler.readthedocs.io/en/fscrawler-2.7/installation.html](https://fscrawler.readthedocs.io/en/fscrawler-2.7/installation.html)下载文件（本文以windows版本为例）。

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_09](https://s2.51cto.com/images/blog/202208/31171754_630f2742b460b97773.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   解压文件

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_10](https://s2.51cto.com/images/blog/202208/31171754_630f2742c32bc29773.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-     
    

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_11](https://s2.51cto.com/images/blog/202208/31171754_630f2742ce75859967.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   创建文件爬取job

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_12](https://s2.51cto.com/images/blog/202208/31171754_630f2742d9d3324216.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   运行以上命令后，程序提示是否创建该job

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_搜索_13](https://s2.51cto.com/images/blog/202208/31171754_630f2742ea5c822251.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   选择y,程序会在用户目录下创建以下配置文件，我们需要对该任务进行配置

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_14](https://s2.51cto.com/images/blog/202208/31171755_630f27430371212551.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

```
---name: "test"fs:  url: "d:\\test" # 监控windows下的D盘test目录  update_rate: "15m" # 间隔15分进行扫描  excludes:  - "*/~*"  #排除以~开头的文件  json_support: false  filename_as_id: false  add_filesize: true  remove_deleted: true  add_as_inner_object: false  store_source: false  index_content: true  attributes_support: false  raw_metadata: false  xml_support: false  index_folders: true  lang_detect: false  continue_on_error: false  ocr:    language: "eng"    enabled: true    pdf_strategy: "ocr_and_text"  follow_symlinks: falseelasticsearch:  nodes:  - url: "http://127.0.0.1:9200"  bulk_size: 100  flush_interval: "5s"  byte_size: "10mb"  ssl_verification: true1.2.3.4.5.6.7.8.9.10.11.12.13.14.15.16.17.18.19.20.21.22.23.24.25.26.27.28.29.30.31.32.
```

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_15](https://s2.51cto.com/images/blog/202208/31171755_630f27430ff4253814.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   保存配置后，我们就可启动FSCrawle爬虫程序了：

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_16](https://s2.51cto.com/images/blog/202208/31171755_630f27431f33c53686.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_elasticsearch_17](https://s2.51cto.com/images/blog/202208/31171755_630f27432f8e05824.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   启动成功后，我们在原有的配置目录会发现多出一个状态文件，该文件会记录文件爬虫程序的定时运行记录：

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_18](https://s2.51cto.com/images/blog/202208/31171755_630f27433e5c464880.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

```
{  "name" : "test",  "lastrun" : "2021-11-27T09:00:16.2043064",  "indexed" : 0,  "deleted" : 0}1.2.3.4.5.6.
```

## 三、SearchUI

-   我们最后从 [https://github.com/elastic/search-ui](https://github.com/elastic/search-ui)下载前端页面：

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_19](https://s2.51cto.com/images/blog/202208/31171755_630f27435564780964.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   文件解压后，用vscode打开examples\\elasticsearch目录：

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_20](https://s2.51cto.com/images/blog/202208/31171755_630f2743622a492850.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   并依次修改search.js、buildRequest.js、buildState.js文件

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_21](https://s2.51cto.com/images/blog/202208/31171755_630f27436c88e31593.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

2.  修改search.js：设定job路径

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_程序人生_22](https://s2.51cto.com/images/blog/202208/31171755_630f2743965cc54100.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

5.  修改buildRequest.js

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_搜索_23](https://s2.51cto.com/images/blog/202208/31171755_630f2743acc2c43278.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

7.    
    

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_elasticsearch_24](https://s2.51cto.com/images/blog/202208/31171755_630f2743c7d5f32266.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

10.  修改buildState.js

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_25](https://s2.51cto.com/images/blog/202208/31171755_630f2743d911f38386.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   注意：为了让用户在搜索页面上可以直接通过文件链接下载文件，我们通过IIS搭建文件下载服务：

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_26](https://s2.51cto.com/images/blog/202208/31171755_630f2743eaa1b3704.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-     
    

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_elasticsearch_27](https://s2.51cto.com/images/blog/202208/31171756_630f27440effe49502.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   该地址反映在在buildState.js中

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_28](https://s2.51cto.com/images/blog/202208/31171756_630f2744208e645260.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

9.  最后我们修改一下app.js，将搜索返回的页面与搜索字段名称进行对应

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_29](https://s2.51cto.com/images/blog/202208/31171756_630f2744385ce25763.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

## 五、运行测试

-   安装依赖包，运行程序

```
# 安装- npm install# 运行- npm1.2.3.4.
```

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_spring boot_30](https://s2.51cto.com/images/blog/202208/31171756_630f2744474f617136.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   放置文件到FSCrawler监控的目录下

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_搜索_31](https://s2.51cto.com/images/blog/202208/31171756_630f274454f8677018.png?x-oss-process=image/watermark,size_16,text_QDUxQ1RP5Y2a5a6i,color_FFFFFF,t_30,g_se,x_10,y_10,shadow_20,type_ZmFuZ3poZW5naGVpdGk=/format,webp/resize,m_fixed,w_1184 "在这里插入图片描述")

-   测试搜索效果

![手把手教你通过ElasticSearch、FSCrawler及 SearchUI搭建文件搜索引擎_java_32](https://s2.51cto.com/images/blog/202208/31171756_630f27446b87e45125.gif "在这里插入图片描述")

-   **赞**
-   ****1**收藏**
-   **评论**
-   **举报**

**相关文章**
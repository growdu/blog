# docusaurus文档编译为pdf

docusaurus是一个基于markdown的现代化文档框架，可以基于makrdown编写产品的手册并发布。

但docusaurus编写的文档只能通过web服务器托管，通过浏览器进行访问。对于产品手册来说，一般需要提供离线的文档给用户访问，一般是pdf。
docusaurus官方没有提供将手册转为pdf的方式，因而需要寻找一种方式来将markdown转为pdf。

以下是可行的两种方案：

1. pandoc使用pdf解析引擎将markdown直接转换为pdf；
2. 使用sphinx将markdown转换为tex，再将其渲染为pdf；

无论采用哪种方式，由于docusaurus框架的灵活性，尤其是mdx的扩展格式支持，除非不使用特殊格式，只使用标准的markdown语法，不然不可避免的就会涉及到不同语法格式的转换。典型的格式如下：

- 告警
- 表格
- 链接
- 目录树
- 选项卡

## pandoc

## sphinx

sphinx使用插件和texlive来进行转换。

sphinx转成pdf时无法识别docusaurus的sidebar.js，因而无法从sidebar.js中直接生成目录树。
因而需要编写脚本根据sidebar.js生成目录树。

```shell
pip install --no-index --find-links=. sphinx sphinx-rtd-theme myst-parser sphinx-copybutton sphinxcontrib-mermaid sphinx_material
```

## 如何将sidebar.js转换为index.rst

sidebar.js是一个嵌套递归的数组，内部指定了文档的显示顺序。

数组有三种元素：

1. 文档id - 字符类型
2. 自动生成目录 - 字典类型
3. 目录数组 - 字典类型

解析时，解析到文档id，将该文件id写入到pdf_index.rst内；解析到自动生成目录或者目录数组时在该目录下生成对应目录的pdf_index.rst，并添加到上层目录里面。

sidebar.js按照json数组组织，每一个json数组对应一个目录。

而每一个目录下又有两种组织方式：

- 手动列出要展示的文件
- 自动列出要展示的文件

转换时遵循如下原则：

1. 每一个category都要对应一个实际的目录，同时目录下都需要有一个对应的index.rst文件
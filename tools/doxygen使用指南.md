# 不得不会的代码注释工具——doxygen

## 下载

官网下载二进制或者直接用yum或apt工具下载。

## 使用流程

- 进入项目目录生成doxygen配置文件

  ```shell
  doxygen -g
  ```

- 修改doxygen配置文件

  ```shell
  # 程序文档输出目录
  
  OUTPUT_DIRECTORY    =  doc/
  
  # 程序文档语言环境
  
  OUTPUT_LANGUAGE    = Chinese
  
  # 如果是制作 C 程序文档，该选项必须设为 YES，否则默认生成 C++ 文档格式
  
  OPTIMIZE_OUTPUT_FOR_C  = YES
  
  # 对于使用 typedef 定义的结构体、枚举、联合等数据类型，只按照 typedef 定义的类型名进行文档化
  
  TYPEDEF_HIDES_STRUCT   = YES
  
  # 在 C++ 程序文档中，该值可以设置为 NO，而在 C 程序文档中，由于 C 语言没有所谓的域/名字空间这样的概念，所以此处设置为 YES
  
  HIDE_SCOPE_NAMES        = YES
  
  # 让 doxygen 静悄悄地为你生成文档，只有出现警告或错误时，才在终端输出提示信息
  
  QUIET   = YES
  
  # 只对头文件中的文档化信息生成程序文档
  
  FILE_PATTERNS          = *.h
  
  # 递归遍历当前目录的子目录，寻找被文档化的程序源文件
  
  RECURSIVE              = YES
  
  # 示例程序目录
  
  EXAMPLE_PATH           = example/
  
  # 示例程序的头文档 (.h 文件) 与实现文档 (.c 文件) 都作为程序文档化对象
  
  EXAMPLE_PATTERNS       = *.c \
  
                                 *.h
  
  # 递归遍历示例程序目录的子目录，寻找被文档化的程序源文件
  
  EXAMPLE_RECURSIVE      = YES
  
  # 允许程序文档中显示本文档化的函数相互调用关系
  REFERENCED_BY_RELATION = YES
  
  REFERENCES_RELATION    = YES
  
  REFERENCES_LINK_SOURCE = YES
  
  # 不生成 latex 格式的程序文档
  
  GENERATE_LATEX         = NO
  
  # 在程序文档中允许以图例形式显示函数调用关系，前提是你已经安装了 graphviz 软件包
  
  HAVE_DOT               = YES
  
  CALL_GRAPH            = YES
  
  CALLER_GRAPH        = YES
  
  #让doxygen从配置文件所在的文件夹开始，递归地搜索所有的子目录及源文件
  
  RECURSIVE = YES  
  
  #在最后生成的文档中，把所有的源代码包含在其中
  
  SOURCE BROWSER = YES
  
  $这会在HTML文档中，添加一个侧边栏，并以树状结构显示包、类、接口等的关系
  
  GENERATE TREEVIEW ＝ ALL
  
  
  EXTRACT_ALL：这个标记告诉 doxygen，即使各个类或函数没有文档，也要提取信息。必须把这个标记设置为 Yes。
  
  EXTRACT_PRIVATE：把这个标记设置为 Yes。否则，文档不包含类的私有数据成员。
  
  EXTRACT_STATIC：把这个标记设置为 Yes。否则，文档不包含文件的静态成员（函数和变量）。
  ```

- 生成文档

  ```shell
  doxygen ./Doxyfile
  ```

## 注释规则

### 项目注释

> - 项目注释块用于对项目进行描述，每个项目只出现一次，一般可以放在main.c主函数文件头部。对于其它类型的项目，置于定义项目入口函数的文件中。对于无入口函数的项目，比如静态库项目，置于较关键且不会被外部项目引用的文件中。
> - 项目注释块以“/** @mainpage”开头，以“*/”结束。包含项目描述、及功能描述、用法描述、注意事项4个描述章节。
> - 项目描述章节描述项目名称、作者、代码库目录、项目详细描述4项内容，建议采用HTML的表格语法进行对齐描述。
> - 功能描述章节列举该项目的主要功能。
> - 用法描述章节列举该项目的主要使用方法，主要针对动态库、静态库等会被其它项目使用的项目。对于其它类型的项目，该章节可省略。
> - 注意事项章节描述该项目的注意事项、依赖项目等相关信息

```c
/**@mainpage  
* @section   项目详细描述
*
* @section   功能描述  
* 
* @section   用法描述 
* 

**********************************************************************************
*/
```

项目注释也可以使用markdown文件作为主页，通过指定md文件路径来配置。

```shell
USE_MDFILE_AS_MAINPAGE = doc/readme.md
```

### 文件注释

```c
/**
 * @file 文件名
 * @brief 简介
 * @details 细节
 * @mainpage 工程概览
 * @author 作者
 * @version 版本号
 * @date 年-月-日
 */
```

#### 全局常量/变量/宏定义/结构体定义/类定义的注释

```c
/// 缓存大小
#define BUFSIZ 1024*4
#define BUFSIZ 1024*4 ///< 缓存大小
```

#### 函数注释

```c
/**
 * @brief 函数简介
 *
 * @param 形参 参数说明
 * @param 形参 参数说明
 * @return 返回值说明
*/
```

## reference

1. https://blog.srefan.com/2020/05/doxygen-generate-docs/
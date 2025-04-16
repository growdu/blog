# autoconf使用

## 简介

> Autoconf是一个用于生成shell脚本的工具，可自动配置源码包以适应多种类Posix的系统,产生的配置脚本通常叫做configure。Autoconf的目标是为每个用户提供可移植的配置。
>
> Autoconf解决了一个重要的问题 - 可靠地发现系统特定的构建和运行时信息。为此，GNU项目开发了一套集成实用程序来完成Autoconf的工作：GNU构建系统，其最重要的组件是Autoconf，Automake和Libtool。
>
> 使用以下命令来安装我们需要的组件：
>
> ```shell
> sudo apt-get install autoconf automake libtool
> ```

> 使用automake,程序开发人员只需要写一些简单的 含有预定义宏的 文件,由autoconf根据一个宏文件生成configure,由automake根据另一个宏文件生成Makefile.in,再使用configure依据Makefile.in来生成一个符合惯例的 Makefile.
>
> automake 读取 Makefile.am 来产生 Makefile.in。
>
> configure 读取 Makefile.in 来产生 Makefile。

使用autoconf的最终目的是生成能够根据不同系统生成Makefile的configure文件，一般情况下我们需要准备如下内容：

1. 源码
2. configure.ac
3. Makefile.am

然后通过如下一系列命令可以生成configure文件：

```shell
aclocal; autoheader;autoconf; automake --add-missing;
```

## 使用

在test目录下有一个main.c文件，其内容如下：

```shell
ha@ha-virtual-machine:~/test$ ls
main.c
ha@ha-virtual-machine:~/test$ cat main.c
#include <stdio.h>

int main(){
        printf("This is src\n");
        return 0;
}
```

我们使用autoconf来对其进行编译构建。

1. 使用autoscan扫描当前目录，生成configure.scan文件；可以看到当前目录结构如下：

   ```shell
   ha@ha-virtual-machine:~/test$ autoscan
   ha@ha-virtual-machine:~/test$ ls
   autoscan.log  configure.scan  main.c
   ha@ha-virtual-machine:~/test$ cat configure.scan
   #                                               -*- Autoconf -*-
   # Process this file with autoconf to produce a configure script.
   
   AC_PREREQ([2.71])
   AC_INIT([FULL-PACKAGE-NAME], [VERSION], [BUG-REPORT-ADDRESS])
   AC_CONFIG_SRCDIR([main.c])
   AC_CONFIG_HEADERS([config.h])
   
   # Checks for programs.
   AC_PROG_CC
   
   # Checks for libraries.
   
   # Checks for header files.
   
   # Checks for typedefs, structures, and compiler characteristics.
   
   # Checks for library functions.
   
   AC_OUTPUT
   ```

   - AC_PREREQ声明本文件要求的 autoconf 版本。
   - AC_INIT 宏用来定义软件的名称和版本等信息，本例写成:AC_INIT(Hello, 1.0)
   - 这里省略了 BUG-REPORT-ADDRESS 参数，它是可选项，一般写成作者的邮件地址
   - AC_CONFIG_SRCDIR 宏通过侦测所指定的源码文件是否存在，来确定源码目录的有效性。可以选择源码目录中的任何一个文件作为代表, 宏参数中使用 `[ ]’，是为了表明其中的字符串是一个整体。

   - AC_CONFIG_HEADER 宏用于生成 config.h 文件，里面存放 configure 脚本侦测到的信息如果程序需要使用其中的定义，就在源码中加入`#include <config.h>`
   - 其他的一些宏是标准的侦测过程，可以保留不动修改configure.scan为configure.ac，同时修改项目编译相关内容；

2. 将configure.scan重命名为configure.ac，然后修改其内容，仅需添加`AM_INIT_AUTOMAKE(1.0)`；

   ```shell
   #                                               -*- Autoconf -*-
   # Process this file with autoconf to produce a configure script.
   
   AC_PREREQ([2.71])
   AC_INIT([FULL-PACKAGE-NAME], [VERSION], [BUG-REPORT-ADDRESS])
   AM_INIT_AUTOMAKE(1.0)
   AC_CONFIG_SRCDIR([main.c])
   AC_CONFIG_HEADERS([config.h])
   
   # Checks for programs.
   AC_PROG_CC
   
   # Checks for libraries.
   
   # Checks for header files.
   
   # Checks for typedefs, structures, and compiler characteristics.
   
   # Checks for library functions.
   ```

   

3. 执行aclocal；

   > autoconf 是 用来生成自动配置软件源代码脚本（configure）的 工具.configure脚本能独立于autoconf运行,且在 运行的 过程中,不需要用户的 干预.
   > 要生成configure文件,你必须告诉autoconf如何找到你所用的 宏.方式是 使用aclocal程序来生成你的 aclocal.m4.
   >
   > aclocal根据configure.in文件的 内容,自动生成aclocal.m4文件.aclocal是 一个perl 脚本程序,它的 定义是 ："aclocal - create aclocal.m4 by scanning configure.ac".

4. 执行autoconf生成configure；

   > autoconf从configure.in这个列举编译软件时所需要各种参数的 模板文件中创建configure.
   > autoconf需要GNU m4宏处理器来处理aclocal.m4,生成configure脚本.
   > m4是 一个宏处理器.将输入拷贝到输出,同时将宏展开.宏可以是 内嵌的 ,也可以是 用户定义的 .除了可以展开宏,m4还有一些内建的 函数,用来引用文件,执行命令,整数运算,文本操作,循环等.m4既可以作为编译器的 前端,也可以单独作为一个宏处理器.

5. 执行autoheader生成config.h.in；

6. 将编译规则写入Makfile.am；

   ```shell
   AUTOMAKE_OPTIONS=foreign
   bin_PROGRAMS=test
   test_SOURCES=main.c
   ```

   

7. 执行automake生成Makefile.in;

   ```shell
   automake --add-missing
   ```

   > automake会根据你写的 Makefile.am来自动生成Makefile.in.
   > Makefile.am中定义的 宏和目标,会指导automake生成指定的 代码.例如,宏bin_PROGRAMS将导致编译和连接的 目标被生成.

8. 最终当你执行configure时会根据Makefile.in生成Makefile；

# reference

1. https://blog.csdn.net/qq_22660775/article/details/88975529
2. https://www.laruence.com/2009/11/18/1154.htmls
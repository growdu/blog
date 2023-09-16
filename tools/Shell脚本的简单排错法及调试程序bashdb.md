# Shell脚本的简单排错法及调试程序bashdb

与众多脚本语言一样，Shell 脚本在执行时出错是很常见的，最简单的原因无外乎脚本在编写的过程中出现了语法错误或者不小心输错了命令等。找出脚本中的错误是很重要的能力。比如，我经常不小心会把 echo 命令写成了 ehco，那么执行就会出现下面这种情况：

```
[root@localhost ~]test: line 2: ehco: command not found
```

从报错信息很容易判断出错的原因是“命令不存在”。重新编辑这个文件修改成 echo 就可以解决。如果只是语法或命令上的错误还是比较容易辨别的，但往往一些逻辑或算法错误就不容易发现，因为语法正确且本身不会造成程序运行错误。比如说下面的脚本，本来想连续 10 次做某些操作的，结果却迟迟没输出。仔细观察一下就知道是陷入了死循环。

```
[root@localhost ~]#!/bin/bash
for ((i=10;i>0;i=i+1))
do
done
```

如果在上面的循环中加入 echo 语句，就容易发现问题了。而如果是单次循环过快，根本来不及看就进入了下一次循环，那这时就可以加入 sleep 命令降低单次循环的速度，比如使用 sleep 2，单次循环就将延时 2s，给我们带来足够的观察时间：

```
[root@localhost ~]#!/bin/bash
for ((i=10;i>0;i=i+1))
do
    echo "i=$i";
done
```

为了更清晰的看到脚本运行的过程，我们还可以借助-x 参数来观察脚本的运行情况。比如上面的脚本，我们使用-x 参数执行就可以发现，变量 i 的值一直在增加，且一直满足 x>0 的条件，所以这是一个死循环。所以，我们只要将 i=i+1 修改成 i=i-1 即可。

```
[root@localhost ~]# sh -x test
+ (( i=10 ))
+ (( i>0 ))
+ echo i=10i=10
+ sleep 2
+ (( i=i+1 ))
+ (( i>0 ))
+ echo i=11i=11+ sleep 2
+ (( i=i+1 ))
+ (( i>0 ))
+ echo i=12i=12
+ sleep 2
[Ctrl +c]终止脚本
```

Shell 本身并没有提供更好的排错工具，为了更加精细地调试 Shell 脚本，我们可以借助第三方工具 [bashdb](https://zhang.ge/tag/bashdb/ "View all posts in bashdb")。这是一个类似于 GDB 的脚本调试软件，小巧而强大，具有这只断点、单步执行、观察变量等功能。下载时请根据所使用的 bash 版本选择相应的 bashdb，否则会提示因为版本不符合而无法安装。

如下查看 bash 版本：

```
[root@localhost ~]# bash --version
GNU bash, version 3.1.25(1)-release (x86_64-redhat-linux-gnu)Copyright (C) 2005 Free Software Foundation, Inc.
```

如下安装：

```
wget  http://ftp.jaist.ac.jp/pub/sourceforge/b/ba/bashdb/bashdb/3.1-0.09/bashdb-3.1-0.09.tar.gz
tar -zxvf  bashdb-3.1-0.09.tar.gz
cd  bashdb-3.1-0.09
./configure
make && make install
```

安装完成后，我们便可以在终端使用 bashdb 命令了，改命令典型用法如下：

常用参数：

```
l  列出当前行以下的 10 行
-  列出正在执行的代码行的前面 10 行
.  回到正在执行的代码行
w  列出正在执行的代码行前后的代码
/pat/ 向后搜索 
pat？pat？向前搜索 pat
#Debug 控制类：
h     帮助
help  命令 得到命令的具体信息
q     退出 
bashdbx     算数表达式 计算算数表达式的值，并显示出来使用 
bashdb 进行 debug 的常用命令(cont.)

#控制脚本执行类：
n   执行下一条语句，遇到函数，不进入函数里面执行，将函数当作黑盒
s n 单步执行 n 次，遇到函数进入函数里面
b   行号 n 在行号 n 处设置断点
del 行号 n 撤销行号 n 处的断点
c   行号 n 一直执行到行号 n 处
R   重新启动当前调试脚本
Finish 执行到程序最后
cond n expr 条件断点
```

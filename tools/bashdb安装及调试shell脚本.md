# bashdb 安装调试
[bashdb下载地址](https://bashdb.sourceforge.net/)

解压安装 bashdb是在linux环境下使用的，将资源下载下来后，解压上传到linux系统，再执行以下指令完成安装。

```
bzip2 -d bashdb-4.2-0.8.tar.bz2
tar -xvf bashdb-4.2-0.8.tar
./configure
make && make install
```

使用方式 bashdb -debug 脚本名 执行脚本后会进入到脚本内部，通过bashdb的一些列指令在执行过程中对脚本进行调试。bashdb常用指令如下：

**1.列出代码和查询代码指令**

```
l  列出当前行以下的10行
-  列出正在执行的代码行的前面10行
.  回到正在执行的代码行
w  列出正在执行的代码行前后的代码
/pat/ 向后搜索pat
？pat？向前搜索pat
```

**2.debug空值指令**

```
h 帮助
help 命令 得到命令的具体信息
q 退出bashdb
x 算数表达式  计算算数表达式的值，并显示出来
!! Shell命令  执行shell命令
```

**3.控制脚本执行指令**

```
n 执行下一条语句，遇到函数，不进入函数里面执行，将函数当作黑盒
s n 单步执行n次，遇到函数进入函数里面
b 行号n  在行号n处设置断点
del 行号n   撤销行号n处的断点
c 行号n   一直执行到行号n处
R 重新启动当前调试脚本
Finish 执行到程序最后
cond n expr 条件断点
```
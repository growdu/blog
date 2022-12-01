# linux内核模块指北

linux内核提供在运行时可进行扩展的特性，这意味着当系统启动并运行时，我们可以向内核添加或移除部分功能。我们在运行时添加到内核中的代码就被成为动态可加载内核模块，我们简称为内核模块。可以将内核模块模块简单理解为linux内核的插件。

## 内核模块基本操作

内核模块编译后会生成.ko的文件，在linux系统中可以执行如下命令查看模块相关信息。

```shell
<<<<<<< HEAD

#加载内核模块

insmod

#卸载内核模块

rmmod

#列出内核模块

lsmod

#查看模块信息

modinfo modname

=======
#加载内核模块
insmod
#卸载内核模块
rmmod
#列出内核模块
lsmod
#查看模块信息
modinfo modname
>>>>>>> 805efff96212946933afaddb75d65e85df96dac0
```

## 编写内核模块

### 模块声明

-  MODULE_LICENSE  （“  GPL  ”）： 内核可以识别的许可证有GPL（任意版本GNU通用公共许可证）、GPL v2等

-  MODULE_AUTHOR  （“作者”）： 声明作者信息可以不用

-  MODULE_VERSION  （“版本”）： 声明版本信息也可以不用

-  MODULE_DESCRIPTION  （“功能描述”）： 声明模块功能，可不用

### 模块参数

我们可以在加载内核模块的时候向其传递参数，以让同一代码达到不同的效果。当然我们的参数必须用module_param宏来声明具体如下：

```c
<<<<<<< HEAD

module_param（name，type，perm）

=======
module_param（name，type，perm） 
>>>>>>> 805efff96212946933afaddb75d65e85df96dac0
```

-  name  ： 变量名

-  type  ： 数据类型内核支持模块参数类型有：bool、invbool（bool的发转，true变为false，false变为true）、charp（char类型指针值）、int、long、short、uint、ulong、ushort、

-  perm  ： 常见的访问许可值通常为S_IRUGO和S_IWUSR。通常情况下将他们按位或

同时我们也可以用下面的宏声明数组：

```c

Module_param_array（name，type，num，perm）
```

### 模块符号导出

当一个模块要使用另一个模块的函数（变量）的时候，要使用EXPORT_SYMBOL（符号名）或者EXPORT_SYMBOL_GPL（符号名）来申明。

注：EXPORT_SYMBOL_GPL（）只适用于遵循GPL协议的模块

### 模块实例

- hello.mod

```shell

#include<linux/init.h>

#include<linux/module.h>

MODULE_LICENSE("GPL");

staticint hello_init(void)

{

printk("<0> hello!\n");

return0;

}

staticvoid hello_exit(void)

{

printk("<0> goodbye\n");

}

module_init(hello_init);//该宏在模块的目标代码中增加一个特殊的段，用于说明内核初始化函数所在的位置

module_exit(hello_exit);//跟上面的宏对立

```

- makefile

```makefile


obj-m := hello.o

DIRS :=/home/linux

all:

make -C $(DIRS) M=$(PWD) modules

clean:

rm -Rf*.o *.ko *.mod.c *.order *.symvers
```

- printk

printk函数为内核打印函数，其和printf函数功能类似，不过比printf多了打印权限一共有8个级别，printk的日志级别定义如下（在include/linux/kernel.h中）

```c


#define KERN_EMERG 0 //紧急事件消息，系统崩溃之前提示，表示系统不可用

#define KERN_ALERT  1 //报告消息，表示必须立即采取措施

#define KERN_CRIT    2 //临界条件，通常涉及严重的硬件或软件操作失败

#define KERN_ERR    3 //错误条件，驱动程序常用KERN_ERR来报告硬件的错误

#define KERN_WARNING  4 //警告条件，对可能出现问题的情况进行警告

#define KERN_NOTICE 5 //正常但又重要的条件，用于提醒

#define KERN_INFO 6    //提示信息，如驱动程序启动时，打印硬件信息

#define KERN_DEBUG 7 //调试级别的消息

```

# reference

1. https://blog.csdn.net/qq_33406883/article/details/100071183

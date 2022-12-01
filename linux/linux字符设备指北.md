# linux字符设备指北

## 混杂设备

在Linux系统中，存在一类字符设备，它们拥有相同的主设备号（10），但次设备号不同，我们称这类设备为混杂设备(miscdevice)。所有的混杂设备形成一个链表，对设备访问时内核根据次设备号查找到相应的混杂设备。

### 设备描述

Linux中使用struct miscdevice来描述一个混杂设备。

```c
struct miscdevice {
	int minor; /* 次设备号*/
	const char *name; /* 设备名*/
	const struct file_operations *fops; /*文件操作*/
	struct list_head list;
	struct device *parent;
	struct device *this_device;
};
```

### 设备注册

Linux中使用misc_register函数来注册一个混杂设备驱动。

```c
int misc_register(struct miscdevice * misc)
```

### 样例

- test_misc.c

```c
#include <linux/init.h>
#include <linux/module.h>
#include <linux/fs.h>       // struct file_operations
#include <linux/cdev.h>     // struct cdev
#include <linux/uaccess.h>
#include <linux/device.h>
#include <linux/semaphore.h>
#include <linux/string.h>
#include <linux/miscdevice.h>
 
 
static int hello_open(struct inode *inode,
                      struct file *file)
{
    printk("===[growdu]===[%s]===[%s]===\n",__FILE__, __func__);
    return 0;
}
 
static int hello_close(struct inode *inode,
                        struct file *file)
{
    printk("===[growdu]===[%s]===[%s]===\n",__FILE__, __func__);
    return 0;
}

static ssize_t hello_read(struct file *file,
                        char __user *buf,
                        size_t count,
                        loff_t *ppos)
{
    printk("Read my_read sucess!\n");
    int param = 500;
    copy_to_user(buf, &param, 4);
    return 0;
}


 
// 定义初始化LED的硬件操作对象
// open,release一旦加载内存中，静静等待着应用程序来调用
static struct file_operations hello_fops =
{
    .owner = THIS_MODULE,
    .open = hello_open,     // 打开设备
    .read = hello_read,
    .release = hello_close  // 关闭设备
};
 
static const char name[] = "test_misc";
 
// 定义初始化混杂设备对象
static struct miscdevice hello_misc =
{
    .minor = MISC_DYNAMIC_MINOR,
    .name = name,
    .fops = &hello_fops
};
 
static int __init hello_init(void)
{
    int rc = -1;
	
    printk("===[growdu]===[%s]===[%s]===[Hello !]===\n",__FILE__, __func__);
 
    rc = misc_register(&hello_misc); // 注册
    
    if (rc != 0)
    {
        printk("===[growdu]===[%s]===[%s]===[misc_register error with %d]===\n",__FILE__, __func__, rc);
        return -1;
    }
	
    printk("===[growdu]===[%s]===[%s]===[name=%s, nodename = %s]===\n",
        __FILE__, __func__, name, hello_misc.nodename);
 
    return 0;
}
 
static void __exit hello_exit(void)
{
    misc_deregister(&hello_misc); // 卸载
    printk("===[growdu]===[%s]===[%s]===[Bye bye...]===\n",__FILE__, __func__);
}
 
 
module_init(hello_init);
module_exit(hello_exit);
 
MODULE_DESCRIPTION("growdu: Driver for DEMO!");
MODULE_AUTHOR("growdu");
MODULE_LICENSE("GPL");
MODULE_VERSION("V0.0.1");
```

- makefile

```makefile
obj-m := test_misc.o
CURRENT_PATH := $(shell pwd)
LINUX_KERNEL := $(shell uname -r)
LINUX_KERNEL_PATH := /usr/src/kernels/$(LINUX_KERNEL)
CONFIG_MODULE_SIG=n
all:
        $(MAKE) -C $(LINUX_KERNEL_PATH) M=$(CURRENT_PATH) modules
clean:
        rm *.ko
        rm *.o
```

<font color="red">注意：若不添加CONFIG_MODULE_SIG=n，有可能会出现加载内核模块后签名错误，然后创建设备失败。</font>

- test.c

```c
#include <stdio.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/ioctl.h>
#include <fcntl.h>

int main(char argc,char *argv[])
{
    int fd;
    int cmd;
    int param = 0;
    if(argc < 2)
    {
        printf("please enter the second param!\n");
        return 0;   
    }
    cmd = atoi(argv[1]);
    fd = open("/dev/test_misc",O_RDWR);
    if(fd < 0)
    {
        printf("Open /dev/test_misc fail.\n");
    }

    switch(cmd)
    {
        case 1:
            printf("Second param is %c\n",*argv[1]);
            read(fd, &param, 4);
            printf("Read Param is %d.\n",param);
            break;
        default :
            break;
    }
    close(fd);
    return 0;
}
```

- makefile


```makefile
gcc test.c
```

在代码目录下面执行如下脚本：

```shell
# 生成test_misc.ko
make
# 生成a.out进行测试
gcc test.c
# 加载模块
insmod test_misc.ko
# 使用dmesg查看内核是否有错误打印
dmesg
# 若正常创建会在/dev下创建对应的test_misc设备
ls /dev/test_misc
# 测试
./a.out
# 卸载模块
 rmmod test_misc
```

# reference

1. https://www.linuxidc.com/Linux/2016-02/128598.htm
1. https://blog.csdn.net/frodocheng/article/details/106846997
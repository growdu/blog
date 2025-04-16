# C语言内存血与泪教训——内存使用重要原则

## malloc

- malloc函数使用时一定要包含stdlib.h头文件
  
  malloc函数原型返回值为void*，
  
  ```c
   void *malloc (size_t size);
  ```
  
  如果没有包含头文件，函数没有声明就直接使用，那么C语言默认函数的返回值是int型，即如果没有包含头文件，那么malloc函数的原型为：
  
  ```c
  int malloc（size_t size);
  ```
  
  >  如果编译成64位的应用程序，那么sizeof(int) = 4并且sizeof(void *) = 8, 比如malloc本来返回的地址为0xFFFFFFFFFFFF1111, 由于没有函数声明，系统默认malloc返回的类型为int，将上面的地址高32位截取后就得到0xFFFF11111，即对malloc返回值的任何操作都是在地址0xFFFF11111上做的。如果0xFFFF1111这个地址不可写，那么就会导致coredump的情况。
  > 
  > 如果编译成32位的应用程序，那么sizeof(int) = sizeof(void*) = 4,所以不会出现coredump问题。

- malloc函数调用时一定要判断size是否大于0

- malloc函数调用后一定要判断返回值是否为NULL

## free

- free必须与malloc一一对应，最好的原则就是谁申请的内存由谁释放；在做代码走读时，所有的malloc次数与free次数必须是相等的

- free结束后一定要将对象设置成NULL，在调用free释放前可以判断对象非NULL才进行释放

## memcpy

- memcpy时一定要比较判断目标内存的长度是否大于源内存的长度，否则将过长的内存拷贝到较小内存区域时就会发生踩栈



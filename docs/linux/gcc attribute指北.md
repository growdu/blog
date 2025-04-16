# gcc attribute指北

>
>
>GNU C的一大特色（却不被初学者所知）就是__attribute__机制。__attribute__可以设置函数属性（Function Attribute）、变量属性（Variable Attribute）和类型属性（Type Attribute）。
>
>\_\_attribute\_\_语法格式为：
>　　\_\_attribute\_\_ ((attribute-list))
>
>其位置约束为：
>　　放于声明的尾部“；”之前。

### align

align属性不仅可以修饰变量，类型， 还可以修饰函数，用于地址对齐。

```c
// 编译器会把变量a生成在8字节对齐的内存地址上
int a __attribute__((aligned(8))) = 0;

struct test {
        int a;
} __attribute__((aligned(8))); // struct test数据结构定义的所有变量都会出现在8字节对齐的内存上
```

### always_inline

将函数定义为内联函数。

inline函数是否会展开，编译器会进一步判断，即inline只是建议，并不一定就没有函数调用。而使用always_inline则一定会将函数展开，消去函数调用。

```c
static inline void test2(void) __attribute__((always_inline)); 
```

### constructor

构造属性，在main函数执行前执行。vpp里面使用了该种属性。

### destructor

析构函数，在main函数执行完后执行。vpp里面使用了该种属性。

```c
#include<stdio.h>

void __attribute__((constructor)) before(void)
{
        printf("before main func.\n");
}

void __attribute__((destructor)) after(void)
{
        printf("after main func.\n");
}

int main(void)
{
    printf("main is execute now\n");
    return 0;
}
```

### packed

```c
#include<stdio.h>
struct test {
        char a;
        int b;
};

struct test1 {
        char a;
        int b;
}__attribute__((packed));

int main(void)
{
        printf("%d, %d\n", sizeof(struct test), sizeof(struct test1));
}
```

struct test结构， 理论来说一共有1+4=5字节的大小， 但是gcc默认编译出来的大小是8， 也就是说char是按照4字节来分配空间的。加上packed修饰后， 就会按照实际的类型大小来计算。 

### section

gcc编译后的二进制文件为elf格式，代码中的函数部分会默认的链接到elf文件的text section中，变量则会链接到bss和data section中。如果想把代码或变量放到特定的section中， 就可以使用section属性来修饰。

```c
#include<stdio.h>
int __attribute__((section("TEST"))) test1(int a, int b)
{
        return a + b;
}

int test2(int a, int b)
{
        return a + b;
}

int main(void)
{
        test1(1, 2);
        test2(1, 2);
}
```

# reference

1. https://dude6.com/article/314203.html

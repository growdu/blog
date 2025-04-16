

# C语言变长数组（柔性数组）

C99支持变长数组，定义时可以不指定数组长度，分配时再根据实际长度进行分配。

- 变长数组一般只能放在结构体的最后一个成员，
- 在变长数组之前至少得有一个结构体成员
- 且一个结构体只能有一个变长数组

变长数组实际是利用结构体的地址作为起始地址往后面分配内存，这样就可以在实际申请内存的时候按需要的元素个数来进行申请。

- 定义1

```c
struct test {
	int len;
    int data[];
};
```

- 定义2

```c
struct test {
	int len;
    int data[0];
};
```

- 定义3

```c
# define FLEXIBLE_ARRAY_MEMBER
struct test {
	int len;
    int data[FLEXIBLE_ARRAY_MEMBER];
};
```

一般定义2使用的最多，定义3在postgresql中使用，定义1很少用。

**note：变长数组前面的成员不能省略，当然不一定是长度，可以其他没有意义的成员。**。

使用的时候可以使用如下的方式来申请内存：

```c
struct test *t = (struct test *)malloc(sizeof(struct test) + 10 * sizeof(int)); // 10个元素
```


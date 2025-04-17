

# <font color="red">数据结构</font>

## 1 基本概念

**数据：**描述客观事物的符号；能输入到计算机中，能被计算机程序处理；比如声音，图像，视频...

**数据元素：**是组成数据的有一定意义的基本单位；也被称为记录；（比如学生，老师）

**数据项：**一个数据元素可以有若干个数据项组成；是数据项不可分割的最小单位；（比如学生的姓名，学号,性别...）

**数据对象：**数据元素具有相同数量和类型的数据项；（比如学生有姓名，学号，性别等相同的数据项）

**数据结构：**相互之间存在一种或者多种特定关系的数据元素集合。

数据结构按照视点不同可分为：逻辑结构和物理结构

### 1.1 逻辑结构

逻辑结构是指数据对象中数据元素之间的关系，具体分为以下几类：

* 集合结构：数据元素除了同属于一个集合外，没有其他关系
* 线性结构：数据元素之间一对一关系
* 树形结构：数据元素之间存在一对一或一对多的层级关系
* 图形结构：数据元素之间是多对多的关系
* 没有关系

### 1.2 物理结构

物理结构(存储结构)是指数据的逻辑结构在计算机中的存储形式。

* 集合结构：数据元素除了同属于一个集合外，没有其他关系（数据元素随机存放在内存里）
* 顺序结构：把数据元素存放在地址连续的存储单元里；（数组）（或者说按内存编号顺序存放）
* 链式结构：把数据元素存放在任意的存储单元里，这组存储单元可以是连续的，也可以是不连续的

逻辑结构是面向问题的，物理结构是面向计算机的；我们应该注重的就是物理结构，将数据及其逻辑关系存储到计算机内存中去 线性,树形,图形,链式是数据结构的重点和难点。

数据结构解决的是如何高效的将面向问题的逻辑结构存储在计算机中，同时在需要用到这些逻辑关系时将其高效的转换回来。

数据的存储结构只有两种，线性存储和链式存储，因而数组也好，链表，树，图也罢，最终都要转换为线性存储或链式存储。另外值得注意的是，数组天生就是线性存储，链表天生就是链式存储。因而问题更进一步，就是将树与图转换为数组或者链表的存储方式存储。

而数组和链表天生与内存挂钩。内存呢从本质上来说就是一个数组，连续的内存单元编号，内存单元直接和数组对应。所以更进一步，就转换为链表如何存储在数组里。

数组是这样的一个东西，它由两部分组成：编号，和编号对应的空间（可以放东西，可以放东西这一性质最神奇的地方在于你可以把一个编号放进去，这就形成了链表）。

现在假设有一个编号为0-14的数组，需要放进去1,2,3,4,5个数，请问怎么放？

* 1,2,3,4,5
* (5,1),(3,2),(1,3)(2,4)

放进去好放，关键是怎么读出来，即放进去一定要有规则，而且这个规则还要可逆，这样才能讲数据完整的读出来。

## 2 线性表

线性表是一种线性结构，它是具有相同类型的n(n≥0)个数据元素组成的有限序列。具体分为：

* 数组
* 单向链表
* 双向链表

### 2.1 数组

数组从逻辑上来说是 **相同变量的有序集合**。

数组从物理结构上来说是 **一片连续内存空间中的存储元素**。

数组有上界和下界，数组的元素在上下界内是连续的。

数组的特点是：数据是连续的；随机访问速度快。

数组中稍微复杂一点的是多维数组和动态数组。对于C语言而言，多维数组本质上也是通过一维数组实现的。
在C语言中，对于数组名与数组地址，以int a[5]为例，有如下关系：

* 数组名a代表数组首元素的地址(即 &a[0] == a)
* 数组的地址需要取地址符&才能得到(即数组的地址为 &a)
* 数组首元素的地址与数组地址值相同，但是表示的概念不同(即a与&a在数值上相同，但是a代表a[0]的地址，但是&a代表数组在内存中的地址

对于数组的使用，需要注意如下几点：

* 数组名可以看做一个常量指针，即决定了在表达式中数组名只能作为右值使用
* 数组名 "指向" 的是内存中数组首元素的起始地址
* 数组名不包含数组的长度信息
* 数组名作为 sizeof 操作符的参数(sizeof(array)得到的是整个数组在内存中占用的空间
* 数组名作为 & 运算符的参数得到时数组在内存中的地址，得到的是一个数组指针

### 2.2 linux内核中链表的实现

#### 2.2.1 offsetof

```C
//获得结构体（TYPE）的变量成员（MEMBER）在此结构体中的偏移量
#define offsetof(TYPE,MEMBER) ((size_t)&((TYPE*)0)->MEMER)
//( (TYPE *)0 )将零转型为TYPE类型指针，即TYPE类型的指针的地址是0
//((TYPE *)0)->MEMBER访问结构中的数据成员
//&( ( (TYPE *)0 )->MEMBER )取出数据成员的地址
//由于TYPE的地址是0，这里获取到的地址就是相对MEMBER在TYPE中的偏移
// (size_t)(&(((TYPE*)0)->MEMBER))结果转换类型
//对于32位系统而言，size_t是unsigned int类型
//对于64位系统而言，size_t是unsigned long类型
```

#### 2.2.2 container_of

```C
//根据"结构体(type)变量"中的"域成员变量(member)的指针(ptr)"来获取指向整个结构体变量的指针
#define container_of(ptr, type, member) ({          \
    const typeof( ((type *)0)->member ) *__mptr = (ptr);    \
    (type *)( (char *)__mptr - offsetof(type,member) );})
//typeof( ( (type *)0)->member )取出member成员的变量类型。
//const typeof( ((type *)0)->member ) *__mptr = (ptr)定义变量__mptr指针,并将ptr赋值给__mptr
//经过这一步，__mptr为member数据类型的常量指针，其指向ptr所指向的地址
//(char *)__mptr 将__mptr转换为字符型指针
//offsetof(type,member))就是获取"member成员"在"结构体type"中的位置偏移
//(char *)__mptr - offsetof(type,member))就是用来获取"结构体type"的指针的起始地址（为char *型指针）
//(type *)( (char *)__mptr - offsetof(type,member) )
//就是将"char *类型的结构体type的指针"转换为"type *类型的结构体type的指针
```

#### 2.2.3 链表实现

将双向链表节点嵌套在其它的结构体中；在遍历链表的时候，根据双链表节点的指针获取"它所在结构体的指针"，从而再获取数据。

* 初始化链表

```C
//链表结构
struct list_head{
    struct list_head *next,*prev;
};
//初始化链表
//设置name节点的前继节点和后继节点都是指向name本身
#define LIST_HEAD_INIT(name) {&(name),&(name)}
//新建双向链表表头name，并设置name的前继节点和后继节点都是指向name本身
#define LIST_HEAD(name) struct list_head name=LIST_HEAD_INIT(name)
//将list节点的前继节点和后继节点都是指向list本身
static inline void INIT_LIST_HEAD(struct list_head *list){
    list->next=list;
    list->pre=list;
}
```

* 添加节点

```C
//将new插入到prev和next之间
//以"__"开头的函数意味着是内核的内部接口，外部不应该调用该接口
static inline void __list_add(struct list_head *new,
                  struct list_head *prev,
                  struct list_head *next)
{
    next->prev = new;
    new->next = next;
    new->prev = prev;
    prev->next = new;
}
//将new添加到head之后，是new称为head的后继节点(尾插法)
static inline void list_add(struct list_head *new, struct list_head *head)
{
    __list_add(new, head, head->next);
}
//将new添加到head之前，即将new添加到双链表的末尾（头插法）
static inline void list_add_tail(struct list_head *new, struct list_head *head)
{
    __list_add(new, head->prev, head);
}
```

* 删除节点

```C
//从双链表中删除prev和next之间的节点
static inline void __list_del(struct list_head * prev, struct list_head * next)
{
    next->prev = prev;
    prev->next = next;
}
//从双链表中删除entry节点
static inline void list_del(struct list_head *entry)
{
    __list_del(entry->prev, entry->next);
}
//从双链表中删除entry节点
static inline void __list_del_entry(struct list_head *entry)
{
    __list_del(entry->prev, entry->next);
}
//从双链表中删除entry节点，并将entry节点的前继节点和后继节点都指向entry本身
static inline void list_del_init(struct list_head *entry)
{
    __list_del_entry(entry);
    INIT_LIST_HEAD(entry);
}
```

* 替换节点

```C
//用new节点替换old节点
static inline void list_replace(struct list_head *old,
                struct list_head *new)
{
    new->next = old->next;
    new->next->prev = new;
    new->prev = old->prev;
    new->prev->next = new;
}
```

* 判断链表是否为空

```C
//通过区分"表头的后继节点"是不是"表头本身"来进行判断
static inline int list_empty(const struct list_head *head)
{
    return head->next == head;
}
```

* 获取节点

```C
//获取指向节点的指针
#define list_entry(ptr, type, member) \
    container_of(ptr, type, member)
```

* 遍历节点

```C
//通常用于获取节点，而不能用到删除节点的场景
#define list_for_each(pos, head) \
    for (pos = (head)->next; pos != (head); pos = pos->next)

//通常用于删除节点的场景
#define list_for_each_safe(pos, n, head) \
    for (pos = (head)->next, n = pos->next; pos != (head); \
        pos = n, n = pos->next)
```

## 3 二叉树

### 3.1 基本概念

树是一种数据结构，它是由n（n>=1）个有限节点组成一个具有层次关系的集合。

* 结点的度：结点拥有的子树的数目
* 叶子：度为零的结点
* 分支结点：度不为零的结点
* 树的度：树中结点的最大的度
* 层次：根结点的层次为1，其余结点的层次等于该结点的双亲结点的层次加1
* 树的高度：树中结点的最大层次
* 无序树：如果树中结点的各子树之间的次序是不重要的，可以交换位置
* 有序树：如果树中结点的各子树之间的次序是重要的, 不可以交换位置
* 森林：0个或多个不相交的树组成。对森林加上一个根，森林即成为树；删去根，树即成为森林

一个具有n个节点的二叉树，一共有2n个指针域，其中只有n-1个用来指向节点的左右孩子，其余的n+1个指针为空。二叉树是每个节点最多有两个子树的树结构。它有五种基本形态：

* 空集
* 根和空的左右子树
* 根和左子树
* 根和右子树
* 根和左右子树

### 3.2 二叉树的性质

* 第i层上的节点数目最多为2^i-1(i>0)
* 深度为k的二叉树至多有2^k-1个节点
* 包含n个结点的二叉树的高度至少为log2 (n+1)
* 在任意一棵二叉树中，若终端结点的个数为n0，度为2的结点数为n2，则n0=n2+1




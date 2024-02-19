# 0 Postgresql存储、索引及系统优化、主备切换

<font color="red">基于pg12描述。</font>

## 1 Postgresql存储

### 1.1 物理存储结构

Postgresql当前不支持使用裸设备或者块设备，必须基于文件系统来存储。

#### 1.1.1 关键概念

- Realation：表示表或索引。
- Tuple：表示表中的行。
- Page：表示在磁盘中的数据块。
- Buffer：表示在内存中的数据块

#### 1.1.2 数据块结构

数据块是多行数据的存储结构。

数据块的大小默认是8KB,最大是32KB，一个数据块里存储了多行数据，其数据存储方式采用两头向中间靠拢的方式。
最前面是块头，块头后面记录了各个数据行的指针，数据行从块尾向中间排列，直到和行指针相遇（即没有空间存放新的行数据）。
行数据指针与行数据之间的部分就是空闲空间。数据块存储结构如下图所示：

![](../pgsql_image/block_structure.png)

##### 1.1.2.1 块头
块头主要记录了如下信息：
  - 块的checksum
  - 空闲空间的起始位置和结束位置
  - 特殊数据的起始位置
块头的代码结构如下所示：

```c
typedef struct PageHeaderData
{
	PageXLogRecPtr pd_lsn;		/*本页最后一次更改所写入的XLOG记录的LSN(即当前WAL位置)*/
	uint16		pd_checksum;	/* 本页数据的checksum */
	uint16		pd_flags;		/*标志位*/
	LocationIndex pd_lower;		/* 空闲空间的起始偏移位置 */
	LocationIndex pd_upper;		/* 空闲空间的结束偏移位置 */
	LocationIndex pd_special;	/* 指向特殊空间的起始偏移量 */
	uint16		pd_pagesize_version; /* 页面大小及页面版本号 */
	TransactionId pd_prune_xid; /* 可删除的旧XID，如果没有则为零 */
	ItemIdData	pd_linp[FLEXIBLE_ARRAY_MEMBER]; /* 行指针数组(变长数组),它指向该页中的元组(也就是表记录) */
} PageHeaderData;
```

pd_flags可取值如下：

```c
//是否有未使用的行指针?
#define PD_HAS_FREE_LINES 0x0001 

//没有足够的空间容纳新元组?
#define PD_PAGE_FULL  0x0002

//页面上的所有元组对每个人都可见?
#define PD_ALL_VISIBLE  0x0004

//所有有效pd_flags位的OR操作
#define PD_VALID_FLAG_BITS 0x0007
```

当向表中插入数据时，postgres会分配8KB(BLCKSZ)的内存空间。
除了页的头部数据占用的空间外，其余的空间都是可用于存储元组的(当然行指针也有占用空间)。
当没有行数据时，pd_upper指向可用空间（空闲空间）的末尾，而pd_lower指向页头(PageHeaderData)之后的第一个空闲空间的起始位置。
pd_upper - pd_lower是该页中剩余可用的空闲空间，随着元素的不断插入，pd_upper和pd_lower变量会不断地随着更新。

![](../pgsql_image/page_header.png)

##### 1.1.2.2 行指针

行指针是一个32bit的数字，具体结构如下：

```c
typedef struct ItemIdData
{
	unsigned	lp_off:15,		/* 行内容的偏移量 */
				lp_flags:2,		/* 指针的标记位 */
				lp_len:15;		/* 行内容的长度 */
} ItemIdData;
```

行指针中表示行内容在业内（块中）的偏移量是15bit，能表示的最大偏移量是2^15=32768，因此在Postgresql中的最大大小是32KB。

行指针的长度为4个字节，它形成一个简单的(ItemId，行指针)数组，该数组起着元组索引的作用。每个索引编号从1开始，称为“偏移数”。

当将一个新的元组添加到页的时候，新的行指针也被添加到pd_linp数组中，以指向其对应的元组。

当不断向页中插入数据时候，其元组、行指针以及可用空间的变化如下图所示：

![](../pgsql_image/row_item.png)

当向页中插入一行数据时，需要做如下几件事情：
 
1. 更新行指针的页偏移位置和行长度；
2. 将行数据插入到指定位置；
3. 更新页空闲空间的起始位置和结束位置；
4. 重新计算checksum；

如何读取存储的行数据呢？

页头大小是固定的，同时pd_lower记录了空闲空间的起始位置，且行指针的长度是固定的32bit（4字节），根据这三个数据就可以计算有多少行数据。

```shell
n = (pd_lower - sizeof(PageHeaderData))/4
```

访问的时候先从页头的尾部开始依次访问行指针，根据lp_off确定行的起始位置，根据lp_off+lp_len确定行的结束位置。

#### 1.1.3 tuple结构

这里的tuple指的是数据行，就是前面提到的块（页）结构中行指针所指向的数据。

tuple的物理结构同样是先有一个行头，后面跟了各项数据。

tuple的结构如下图：

![](../pgsql_image/tuple_structure.png)


##### 1.1.3.1 行头

行头的结构体定义如下：

```c
struct HeapTupleHeaderData
{
	union
	{
		HeapTupleFields t_heap;
		DatumTupleFields t_datum;
	}			t_choice;

	ItemPointerData t_ctid;		/* 一个行版本在它所处的表内的物理位置 */

	/* Fields below here must match MinimalTupleData! */

#define FIELDNO_HEAPTUPLEHEADERDATA_INFOMASK2 2
	uint16		t_infomask2;	/* 字段数，其中低11位表示这行有多少个列。其他的位则是HOT（Heap Only Touples）技术及行可见性的标志位。 */

#define FIELDNO_HEAPTUPLEHEADERDATA_INFOMASK 3
	uint16		t_infomask;		/* 用于标识行当前的状态，比如行是否具有OID，是否有空属性，共有16位
，每位都代表不同的含义 */

#define FIELDNO_HEAPTUPLEHEADERDATA_HOFF 4
	uint8		t_hoff;			/* 表示行头的长度 */

	/* ^ - 23 bytes - ^ */

#define FIELDNO_HEAPTUPLEHEADERDATA_BITS 5
	bits8		t_bits[FLEXIBLE_ARRAY_MEMBER];	/* 是一个数组，用于标识该行上哪些字段（列）为空 */

	/* MORE DATA FOLLOWS AT END OF STRUCT */
};
```

其中t_choice成员变量是一个共用体数据类型。对于t_choice中的t_heap成员，它描述了当前元组的事务id、事务id等信息，如下：

```c
typedef struct HeapTupleFields
{
	TransactionId t_xmin;		/* 插入该行版本的事务ID，对应用户看到的xmin */
	TransactionId t_xmax;		/* 删除此行时的事务ID，第一次插入时，此字段为0。如果查询出来此字段不为0，则可能是删除这行的事务还未提交，或者是删除此行的事务回滚了，对应用户看到的xmax */

	union
	{
		CommandId	t_cid;		/* inserting or deleting command ID, or both */
		TransactionId t_xvac;	/* old-style VACUUM FULL xact ID */
	}			t_field3;
} HeapTupleFields;
```

##### 1.1.3.2 行头关键字段

- xmin
插入数据行的事务ID。
- xmax
删除数据行的事务ID。

xmin和xmax是如何更新的？

1. 新插入一行时，将新插入行的xmin设置为当前的事务ID，xmax为0，因为没有删除；
2. 修改一行时，因为MVCC机制，实际上是新插入一行。原数据行上的xmin不变，xmax更新为当前的事务ID（因为修改时，原数据行相当于删除了，即标记删除）。而新插入的数据行的xmin设置为当前的事务ID，xmax设置为0，因为没有删除；
3. 删除一行时，把被删除行上的xmax填写为当前的事务ID。

如何根据xmin和xmax确定访问哪个tuple？

- cmin
- cmax



## 2 Postgresql索引

## 3 Postgresql系统优化

## 4 Postgresql主备切换
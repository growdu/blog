> 还剩下VM，抽时间也一起看了

由于PostgreSQL使用的MVCC机制，导致对同一张表的不断更新会产生大量空闲空间（free space），在插入tuple之前优先现在之前的空闲空间是个较好的选择。

因此PostgreSQL就为每张表添加了一个FSM文件来记录和管理其空闲空间。FSM文件的名为 `oid_fsm`。

> 注意，如无特别描述，默认页面大小 `BLCKSZ` 为8192

为了减小FSM文件的大小，每个表页面使用1个字节来记录空闲空间，具体映射关系如下，例如0就表示剩余空间小于32字节。

```
<span><span> * </span></span>Range     Category
<span><span> * </span></span>0    - 31   0
<span><span> * </span></span>32   - 63   1
<span><span> * </span></span>...    ...  ...
<span><span> * </span></span>8096 - 8127 253
<span><span> * </span></span>8128 - 8163 254
<span><span> * </span></span>8164 - 8192 255
```

FSM的页面结构其实很简单，只有一个`fp_next_slot`和`fp_nodes`数组，此数组中存储的就是页面的free space信息。

```c
typedef struct { /* * fsm_search_avail() tries to spread the load of multiple backends by * returning different pages to different backends in a round-robin * fashion. fp_next_slot points to the next slot to be returned (assuming * there's enough space on it for the request). It's defined as an int, * because it's updated without an exclusive lock. uint16 would be more * appropriate, but int is more likely to be atomically * fetchable/storable. */ int fp_next_slot; /* * fp_nodes contains the binary tree, stored in array. The first * NonLeafNodesPerPage elements are upper nodes, and the following * LeafNodesPerPage elements are leaf nodes. Unused nodes are zero. */ uint8 fp_nodes[FLEXIBLE_ARRAY_MEMBER]; } FSMPageData;
```

对于每个页面，下面的宏用于计算实际的数组大小。

```c
#define NodesPerPage (BLCKSZ - MAXALIGN(SizeOfPageHeaderData) - \ offsetof(FSMPageData, fp_nodes))
```

而数组的使用方式需要结合FSM文件格式来一起介绍。

有了记录空闲空间的文件，最简单的方式是像下图这样，将空闲空间依次记录在每个FSM页面的 `fp_nodes` 中，然后查询时顺序遍历FSM文件检查剩余空间。

![](http://www.eggtart.icu/image-20230307155135808/)

例如前 `[0, SlotsPerFSMPage)` 个表页面就记录在FSM第一个页面中，前 `[SlotsPerFSMPage, 2 * SlotsPerFSMPage)` 个表页面就记录在FSM第二页面中，以此类推。

这样做虽然简单，但是查询效率是很低的，因为每个页面内的槽数量还是挺多的（大约4000个），所以在这个基础上，有两点改进

我们将 `fp_nodes` 数组作为**最大堆二叉树**来使用，只在最下层存储每个页面的空闲信息，存储时还是按照表块顺序来记录，以方便映射回表的物理地址。

下面就是一颗最大堆二叉树的例子。

```
                 14
            /          \
       10                14
     /    \            /    \
   8       10       12        14
 /  \     /  \     /  \      /  \ 
7    8   9   10   11   12   13  14
```

我们可以使用如下宏计算出树中**叶子/非叶子节点的数量**。其中 `SlotsPerFSMPage` 就是每个页面真实可用的槽位数量。

```c
#define NonLeafNodesPerPage (BLCKSZ / 2 - 1) #define LeafNodesPerPage (NodesPerPage - NonLeafNodesPerPage) #define SlotsPerFSMPage LeafNodesPerPage
```

有了树结构，虽然单个页面存储的信息少了，但是能在 的时间内就定位到需要的表块。

一个FSM页面可以寻址约32MB的表空间，对于一个大表来说，每次仍然需要遍历很多个FSM页面。

同样的，我们依然可以用一样的思路来降低查找FSM页面的代价。

我们将上一节中的FSM Block作为最底层，在上面再增加两层辅助层，就得到了FSM文件的最终结构：

![](http://www.eggtart.icu/image-20230307211230577/)

> 实际如果 `BLCKSZ` 过小的话，上树也可能是4层。最终目标是能够定位到2^32-1个页面，即单表的最大块数量
> 
> `#define FSM_TREE_DEPTH ((SlotsPerFSMPage >= 1626) ? 3 : 4)`

辅助层就是用于快速定位。对前两层来说，`fp_nodes` 数组也是作为最大堆二叉树来使用，不过slot里存储的是每颗子树下的**最大剩余空间**。

一个FSM文件里至少有三个页面：第0层，第1层和第2层的页面。

对于FSM文件里的每个页面，使用 `FSMAddress` 来描述其位置，称为**逻辑地址**

```c
typedef struct { int level; // 所在的层数，叶子节点的层数为0 int logpageno; // 该层的第几个节点 } FSMAddress;
```

在上文中，我们是用 `FSMAddress` 逻辑地址来描述FSM节点的位置，那么怎么确定逻辑地址到物理地址的映射呢？

其实从上面的图中，我们可以发现，FSM页面的物理位置可以通过**深度优先遍历**来确定（因为新页面的创建过程其实就是一个深度优先的过程）。例如第 `(1, 1)` 块的物理地址就是 `SlotsPerFSMPage + 2`。

转换通过 `fsm_logical_to_physical` 完成：

```c
static BlockNumber fsm_logical_to_physical(FSMAddress addr) { BlockNumber pages; int leafno; int l; /* * Calculate the logical page number of the first leaf page below the * given page. */ leafno = addr.logpageno; for (l = 0; l < addr.level; l++) leafno *= SlotsPerFSMPage; /* Count upper level nodes required to address the leaf page */ pages = 0; for (l = 0; l < FSM_TREE_DEPTH; l++) { pages += leafno + 1; leafno /= SlotsPerFSMPage; } /* * If the page we were asked for wasn't at the bottom level, subtract the * additional lower level pages we counted above. */ pages -= addr.level; /* Turn the page count into 0-based block number */ return pages - 1; }
```

根据注释描述，请求的逻辑位置是这样被转换的：

1.  我们先要得到其**第一个叶子页面**在最后一层的位置，也就是 `leafno` 的值
2.  之后得到这个叶子页面在深度优先下的序号，也就是遍历每一层计算其**左上方的节点数量**
3.  最后就能根据深度得到请求节点的序号，即得到了物理地址

FSM文件最重要的一点就是如何快速的查找到指定大小的空闲空间，查询的函数为 `fsm_search`

```c
/* * Search the tree for a heap page with at least min_cat of free space */ static BlockNumber fsm_search(Relation rel, uint8 min_cat) { int restarts = 0; FSMAddress addr = FSM_ROOT_ADDRESS; for (;;) { int slot; Buffer buf; uint8 max_avail = 0; /* Read the FSM page. */ buf = fsm_readbuf(rel, addr, false); /* Search within the page */ if (BufferIsValid(buf)) { LockBuffer(buf, BUFFER_LOCK_SHARE); slot = fsm_search_avail(buf, min_cat, (addr.level == FSM_BOTTOM_LEVEL), false); if (slot == -1) max_avail = fsm_get_max_avail(BufferGetPage(buf)); UnlockReleaseBuffer(buf); } else slot = -1; if (slot != -1) { /* * Descend the tree, or return the found block if we're at the * bottom. */ if (addr.level == FSM_BOTTOM_LEVEL) return fsm_get_heap_blk(addr, slot); addr = fsm_get_child(addr, slot); } else if (addr.level == FSM_ROOT_LEVEL) { /* * At the root, failure means there's no page with enough free * space in the FSM. Give up. */ return InvalidBlockNumber; } else { uint16 parentslot; FSMAddress parent; /* * At lower level, failure can happen if the value in the upper- * level node didn't reflect the value on the lower page. Update * the upper node, to avoid falling into the same trap again, and * start over. * * There's a race condition here, if another backend updates this * page right after we release it, and gets the lock on the parent * page before us. We'll then update the parent page with the now * stale information we had. It's OK, because it should happen * rarely, and will be fixed by the next vacuum. */ parent = fsm_get_parent(addr, &parentslot); fsm_set_and_search(rel, parent, parentslot, max_avail, 0); /* * If the upper pages are badly out of date, we might need to loop * quite a few times, updating them as we go. Any inconsistencies * should eventually be corrected and the loop should end. Looping * indefinitely is nevertheless scary, so provide an emergency * valve. */ if (restarts++ > 10000) return InvalidBlockNumber; /* Start search all over from the root */ addr = FSM_ROOT_ADDRESS; } } }
```

查找过程很简单，就是自顶向下的遍历，页面中的查询流程会在下面说明，这里主要看一下异常情况的处理：

1.  如果在第0层就未查询到，直接返回空
2.  如果在后两层未查询到，那么代表着数据出错了，这时候会对当前页面的父页面通过 `fsm_set_and_search` 进行修正，即**从下向上**更新树节点的值

在对每个页面进行查询时，都并非从根节点开始查找。因为这样存在一个坏处：多个线程很有可能会获取到相同的页面，造成堵塞。

在FSM页面里，还有一个变量叫 `fp_next_slot` 没有介绍，这就是其发挥作用的时候。

实际查询遵循的规则如下，代码位于`fsm_search_avail`中：

1.  每次从 `fp_next_slot` 开始搜索
2.  如果当前点的值已经满足要求，就开始向下搜索
3.  向右移动，如果已经是最右节点，就移动到最左边。之后向父节点移动
4.  新的点如果依然不满足要求，回到步骤3

这种查询方式是在尽可能减少冲突（搜索起始点不同）的情况下，逐渐扩大搜索范围（向上移动）并找到满足需求的页面。

![](http://www.eggtart.icu/image-20230307172851618/)

以上图为例，需要查询>=6的页面，红点为该次查询的起点，**红线**就是实际的查询路径。

每个页面的每次查询结束之后就会更新 `fp_next_slot` 值

```c
// 查询开始前处理warp around target = fsmpage->fp_next_slot; if (target < 0 || target >= LeafNodesPerPage) target = 0; // 转换为数组下标 target += NonLeafNodesPerPage; // 查询结束后更新，这里的slot值是在最后一层里的位置，而非fp_nodes数组的下标 fsmpage->fp_next_slot = slot + (advancenext ? 1 : 0);
```

另外，在向下查找的过程中，如果两个孩子节点的value都不符合条件，那么一定是页面数据出现了问题，例如更新的页面未被成功写入磁盘，这时候会对该页面进行修正。

```c
/* make sure we hold an exclusive lock */ if (!exclusive_lock_held) { LockBuffer(buf, BUFFER_LOCK_UNLOCK); LockBuffer(buf, BUFFER_LOCK_EXCLUSIVE); exclusive_lock_held = true; } fsm_rebuild_page(page); MarkBufferDirtyHint(buf, false);
```

无论是查找FSM树还是查找单个FSM里面的树，查找原理都是一样的。

-   [Postgresql Free Space Map 文件解析](https://zhmin.github.io/posts/postgresql-fsm-file/)
# pg内存管理

## buffer

- 全局变量

  ```x
  int			nbufs = num_temp_buffers;
  Block	   *LocalBufferBlockPointers = NULL;
  BufferDesc *LocalBufferDescriptors = NULL;
  ```

- 初始化

  ```c
  static void InitLocalBuffers(void){
      int			nbufs = num_temp_buffers;
      LocalBufferDescriptors = (BufferDesc *) calloc(nbufs, sizeof(BufferDesc));
      LocalBufferBlockPointers = (Block *) calloc(nbufs, sizeof(Block));
      ......
  }
  ```

- Block

  ```c
  typedef void *Block;
  ```

- BufferDesc

  ```c
  typedef struct BufferDesc
  {
  	BufferTag	tag;			/* ID of page contained in buffer */
  	int			buf_id;			/* buffer's index number (from 0) */
  
  	/* state of the tag, containing flags, refcount and usagecount */
  	pg_atomic_uint32 state;
  
  	int			wait_backend_pgprocno;	/* backend of pin-count waiter */
  	int			freeNext;		/* link in freelist chain */
  	LWLock		content_lock;	/* to lock access to buffer contents */
  } BufferDesc;
  
  typedef struct buftag
  {
  	RelFileNode rnode;			/* physical relation identifier */
  	ForkNumber	forkNum;
  	BlockNumber blockNum;		/* blknum relative to begin of reln */
  } BufferTag;
  ```

  

## page

- 定义

  ```c
  typedef char *Pointer;
  typedef Pointer Page;
  ```

- pageheader

  ```c
  typedef struct PageHeaderData
  {
  	/* XXX LSN is member of *any* block, not only page-organized ones */
  	PageXLogRecPtr pd_lsn;		/* LSN: next byte after last byte of xlog
  								 * record for last change to this page */
  	uint16		pd_checksum;	/* checksum */
  	uint16		pd_flags;		/* flag bits, see below */
  	LocationIndex pd_lower;		/* offset to start of free space */
  	LocationIndex pd_upper;		/* offset to end of free space */
  	LocationIndex pd_special;	/* offset to start of special space */
  	uint16		pd_pagesize_version;
  	TransactionId pd_prune_xid; /* oldest prunable XID, or zero if none */
  	ItemIdData	pd_linp[FLEXIBLE_ARRAY_MEMBER]; /* line pointer array */
  } PageHeaderData;
  
  typedef PageHeaderData *PageHeader;
  ```

- page与pageheader的关系

  page是一段内存的指针，pageheaderData是page内存最前面的数据,pageheader是指向pageheaderData的指针。

  ```c
  PageHeader	phdr = (PageHeader) page;
  ```

  
# vpp buffer接口

## buffer

```c
/** VLIB buffer representation. */
typedef union 
{ // 使用union方便在结构体和byte（内存）之间转换
  struct
  {
    CLIB_CACHE_LINE_ALIGN_MARK (cacheline0); // 用来做cacheline对齐

    /** signed offset in data[], pre_data[] that we are currently
      * processing. If negative current header points into predata area.  */
    i16 current_data;

    /** Nbytes between current data and the end of this buffer.  */
    u16 current_length;

    /** buffer flags:
	<br> VLIB_BUFFER_FREE_LIST_INDEX_MASK: bits used to store free list index,
	<br> VLIB_BUFFER_IS_TRACED: trace this buffer.
	<br> VLIB_BUFFER_NEXT_PRESENT: this is a multi-chunk buffer.
	<br> VLIB_BUFFER_TOTAL_LENGTH_VALID: as it says
	<br> VLIB_BUFFER_EXT_HDR_VALID: buffer contains valid external buffer manager header,
	set to avoid adding it to a flow report
	<br> VLIB_BUFFER_FLAG_USER(n): user-defined bit N
     */
    u32 flags;

    /** Generic flow identifier */
    u32 flow_id;

    /** Reference count for this buffer. */
    volatile u8 ref_count;

    /** index of buffer pool this buffer belongs. */
    u8 buffer_pool_index;

    /** Error code for buffers to be enqueued to error handler.  */
    vlib_error_t error;

    /** Next buffer for this linked-list of buffers. Only valid if
      * VLIB_BUFFER_NEXT_PRESENT flag is set. */
    u32 next_buffer;

    /** The following fields can be in a union because once a packet enters
     * the punt path, it is no longer on a feature arc */
    union
    {
      /** Used by feature subgraph arcs to visit enabled feature nodes */
      u32 current_config_index;
      /* the reason the packet once punted */
      u32 punt_reason;
    };

    /** Opaque data used by sub-graphs for their own purposes. */
    u32 opaque[10];

    /** part of buffer metadata which is initialized on alloc ends here. */
      STRUCT_MARK (template_end);

    /** start of 2nd half (2nd cacheline on systems where cacheline size is 64) */
      CLIB_ALIGN_MARK (second_half, 64);

    /** Specifies trace buffer handle if VLIB_PACKET_IS_TRACED flag is
      * set. */
    u32 trace_handle;

    /** Only valid for first buffer in chain. Current length plus total length
      * given here give total number of bytes in buffer chain. */
    u32 total_length_not_including_first_buffer;

    /**< More opaque data, see ../vnet/vnet/buffer.h */
    u32 opaque2[14];

#if VLIB_BUFFER_TRACE_TRAJECTORY > 0
    /** trace trajectory data - we use a specific cacheline for that in the
     * buffer when it is compiled-in */
#define VLIB_BUFFER_TRACE_TRAJECTORY_MAX     31
#define VLIB_BUFFER_TRACE_TRAJECTORY_SZ	     64
#define VLIB_BUFFER_TRACE_TRAJECTORY_INIT(b) (b)->trajectory_nb = 0
    CLIB_ALIGN_MARK (trajectory, 64);
    u16 trajectory_nb;
    u16 trajectory_trace[VLIB_BUFFER_TRACE_TRAJECTORY_MAX];
#else /* VLIB_BUFFER_TRACE_TRAJECTORY */
#define VLIB_BUFFER_TRACE_TRAJECTORY_SZ 0
#define VLIB_BUFFER_TRACE_TRAJECTORY_INIT(b)
#endif /* VLIB_BUFFER_TRACE_TRAJECTORY */

    /** start of buffer headroom */
      CLIB_ALIGN_MARK (headroom, 64);

    /** Space for inserting data before buffer start.  Packet rewrite string
      * will be rewritten backwards and may extend back before
      * buffer->data[0].  Must come directly before packet data.  */
    u8 pre_data[VLIB_BUFFER_PRE_DATA_SIZE];

    /** Packet data */
    u8 data[]; // 变长数组，用来保存数据部分
  };
#ifdef CLIB_HAVE_VEC128
  u8x16 as_u8x16[4];
#endif
#ifdef CLIB_HAVE_VEC256
  u8x32 as_u8x32[2];
#endif
#ifdef CLIB_HAVE_VEC512
  u8x64 as_u8x64[1];
#endif
} vlib_buffer_t;
```

## 常用接口

- 增

  ```c
  // 将数据data添加到buffer里，没有空余的buffer会申请新的内存，同时会将buffer的索引赋值给buffer_index，方便后续用于访问
  int vlib_buffer_add_data (vlib_main_t * vm, vlib_buffer_free_list_index_t free_list_index, u32 * buffer_index, void *data,u32 n_data_bytes);
  ```

- 删

  ```c
  always_inline void
  vlib_buffer_free (vlib_main_t * vm,
  		  /* pointer to first buffer */
  		  u32 * buffers,
  		  /* number of buffers to free */
  		  u32 n_buffers);
  ```

- 改

  ```c
  // 通过移动buffer的current_data指针来取数据或者添加数据，并同时修改buffer的current_length值
  // 一般l为正数表示往前读取数据，当然也可以进行修改
  // 一般l为负数表示往后添加数据
  always_inline void vlib_buffer_advance (vlib_buffer_t * b, word l);
  ```

- 查

  ```c
  // vm是vpp运行时主结构体，buffer_index是buffer的索引，一般在添加buffer时可以获取到，或者遍历buffer时获取
  always_inline vlib_buffer_t *vlib_get_buffer (vlib_main_t * vm, u32 buffer_index);
  
  // 获取当前数据所在的指针位置，一般用于对buffer进行指针偏移后使用
  always_inline void *vlib_buffer_get_current (vlib_buffer_t * b);
  ```

  
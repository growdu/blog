# dcf写入机制

## 写入

dcf提供如下两个写入接口：

- ***dcf_write***
  
  ```c
  int dcf_write(unsigned int stream_id, const char* buffer, unsigned int length, unsigned long long key, unsigned long long *index);
  ```
  
  仅在leader节点调用。

- ***dcf_universal_write***
  
  ```c
  int dcf_universal_write(unsigned int stream_id, const char* buffer, unsigned int length, unsigned long long key, unsigned long long *index);
  ```
  
  可以在任意节点调用。

## 确认

- ***dcf_register_after_writer***
  
  用于注册leader节点写入成功回调函数。
  
  ```c
  int dcf_register_after_writer(usr_cb_after_writer_t cb_func)
  {
      return rep_register_after_writer(ENTRY_TYPE_LOG, cb_func);
  }
  ```
  
  最终将回调函数注册到全局变量
  
  ```c
  int rep_register_after_writer(entry_type_t type, usr_cb_after_writer_t cb_func)
  {
      g_cb_after_writer[type] = cb_func;
      return CM_SUCCESS;
  }
  ```
  
  调用流程如下：
  
  ```mermaid
  grpah TB
  rep_apply_proc-->g_cb_after_writer
  ```
  
  bbh

- ***dcf_register_consensus_notify***
  
  用于注册follower节点写入数据成功的回调函数。

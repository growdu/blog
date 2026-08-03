# pg源码对象管理

pg中对于xlog、buffer等均采用全局变量的方式进行管理。

## buffer

```c
Block	   *LocalBufferBlockPointers = NULL;
BufferDesc *LocalBufferDescriptors = NULL;
```text
## xlog

```c
static XLogCtlData *XLogCtl = NULL;
```text
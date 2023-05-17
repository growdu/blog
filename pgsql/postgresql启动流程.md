# postgresql 启动流程

## initdb

postgresql数据库在启动之前需要先初始化数据库目录，创建目录文件和模板。

## sys_ctl

sys_ctl负责拉起数据库服务。

sys_ctl通过fork一个进程，该进程会将postgres加载进来执行。

## postgres

postgres的执行从main.c的main函数开始，

```mermaid
graph TB
main-->
```

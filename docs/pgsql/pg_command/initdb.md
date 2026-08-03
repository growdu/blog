# initdb

## 启动

```shell
Breakpoint 2, bootstrap_template1 () at initdb.c:1309
1309    {
(gdb) bt
#0  bootstrap_template1 () at initdb.c:1309
#1  0x0000555555560e1f in initialize_data_directory () at initdb.c:2732
#2  0x0000555555561abd in main (argc=3, argv=0x7fffffffe318) at initdb.c:3101
(gdb) b 1378
Breakpoint 3 at 0x55555555e5a8: file initdb.c, line 1378.
(gdb) c
Continuing.
running bootstrap script ...
Breakpoint 3, bootstrap_template1 () at initdb.c:1378
1378            PG_CMD_OPEN;
(gdb) p cmd
$1 = "\"/usr/local/postgresql/bin/postgres\" --boot -X 16777216  -F -c log_checkpoints=false  \000000200214345367377177000000P374310367377177000000240321377377377177000000000000000000377177000000000000000000000000000000235v341367377177000000225v341367377177000000`\325377377377177000000247000000000000000000000D322377377377177000000026307XUUU000000200243XUUU000000=\334313000b000000000P322377377377177000000"...
(gdb)

```text
可以看到，initdb最终会调用postgres来初始化数据库。

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
$1 = "\"/usr/local/postgresql/bin/postgres\" --boot -X 16777216  -F -c log_checkpoints=false  \000\000\200\214\345\367\377\177\000\000P\374\310\367\377\177\000\000\240\321\377\377\377\177\000\000\000\000\000\000\377\177\000\000\000\000\000\000\000\000\000\000\235v\341\367\377\177\000\000\225v\341\367\377\177\000\000`\325\377\377\377\177\000\000\247\000\000\000\000\000\000\000D\322\377\377\377\177\000\000\026\307XUUU\000\000\200\243XUUU\000\000=\334\313\000\b\000\000\000P\322\377\377\377\177\000\000"...
(gdb)

```

可以看到，initdb最终会调用postgres来初始化数据库。

# pg_ctl

## 启动

```shell
(gdb) c
Continuing.
[Attaching after Thread 0x7ffff7d80740 (LWP 2093) fork to child process 2100]
[New inferior 2 (process 2100)]
[Detaching after fork from parent process 2093]
[Inferior 1 (process 2093) detached]
waiting for server to start....[Thread debugging using libthread_db enabled]
Using host libthread_db library "/lib/x86_64-linux-gnu/libthread_db.so.1".
[Switching to Thread 0x7ffff7d80740 (LWP 2100)]

Thread 2.1 "pg_ctl" hit Breakpoint 2, start_postmaster () at pg_ctl.c:503
503             (void) execl("/bin/sh", "/bin/sh", "-c", cmd, (char *) NULL);
(gdb) ......p......cmd.
Undefined command: "pcmd".  Try "help".
(gdb) .. .p .cm.d
$1 = 0x55555556e140 "exec \"/usr/local/postgresql/bin/postgres\" -D \"data\"  < \"/dev/null\" 2>&1"
(gdb) ...........................

```


# 一台主机运行多个corosync代码分析

corosync当前设计为一台机器只能运行一个corosyc实例，无法部署多个，是由如下两个部分决定的：

- 锁文件
- ipc创建

## 锁文件

corosync从设计上就只运行一台机器运行一个corosync节点，它通过每次运行将pid写入固定的pid文件来进行控制，pid的文件路径在代码中写死，无法配置。

```c
static const char *corosync_lock_file = LOCALSTATEDIR"/run/corosync.pid";
```

corosync_lock_file是一个const的常量，不允许修改，若要支持同一机器运行多个corosync实例，需要支持corosync_lock_file可配置。

## ipc创建

corosync内部各个服务之间通过ipc进行通信，而ipc创建时需要指定key，当前corosync直接使用服务名作为key来创建ipc，如cpg、cfg。因而在一台节点上只能有一个cpg的ipc，也决定了无法运行多个corosync。当第二个运行时，创建ipc失败。

```c
static const char* cs_ipcs_serv_short_name(int32_t service_id)
{
    const char *name;
    switch (service_id) {
    case CFG_SERVICE:
        name = "cfg";
        break;
    case CPG_SERVICE:
        name = "cpg";
        break;
    case QUORUM_SERVICE:
        name = "quorum";
        break;
    case PLOAD_SERVICE:
        name = "pload";
        break;
    case VOTEQUORUM_SERVICE:
        name = "votequorum";
        break;
    case MON_SERVICE:
        name = "mon";
        break;
    case WD_SERVICE:
        name = "wd";
        break;
    case CMAP_SERVICE:
        name = "cmap";
        break;
    default:
        name = NULL;
        break;
    }
    return name;
}
```

```c
    serv_short_name = cs_ipcs_serv_short_name(service->id);

    ipcs_mapper[service->id].id = service->id;
    strcpy(ipcs_mapper[service->id].name, serv_short_name);
    log_printf (LOGSYS_LEVEL_DEBUG,
        "Initializing IPC on %s [%d]",
        ipcs_mapper[service->id].name,
        ipcs_mapper[service->id].id);
// 使用服务名创建ipc
    ipcs_mapper[service->id].inst = qb_ipcs_create(ipcs_mapper[service->id].name,
        ipcs_mapper[service->id].id,
        cs_get_ipc_type(),
        &corosync_service_funcs);
```

应用在与corosync通信时，也直接使用服务名创建ipc。如cpg服务初始流程如下：

```c
    cpg_inst->c = qb_ipcc_connect ("cpg", IPC_REQUEST_SIZE);
    if (cpg_inst->c == NULL) {
        error = qb_to_cs_error(-errno);
        goto error_put_destroy;
    }
```

可以看到直接使用cpg连接ipc，这也导致应用只能连接到一个corosync。
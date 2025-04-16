# dcf投票系统详解

## 节点类型

```c
typedef enum en_dcf_role {
    DCF_ROLE_UNKNOWN = 0,
    DCF_ROLE_LEADER, 
    DCF_ROLE_FOLLOWER,
    DCF_ROLE_LOGGER,
    DCF_ROLE_PASSIVE,
    DCF_ROLE_PRE_CANDIDATE,
    DCF_ROLE_CANDIDATE,
    DCF_ROLE_CEIL,
} dcf_role_t;
```

## 投票模式

```c
typedef enum en_param_run_mode {
    ELECTION_AUTO,
    ELECTION_MANUAL,
    ELECTION_DISABLE,
    ELECTION_CEIL,
} param_run_mode_t;
```

## 投票初始化

```mermaid
graph TB
elc_init-->elc_stream_init-->register_msg_process-->cm_create_thread
cm_create_thread-->|心跳线程,定时发送心跳报文|elc_status_check_entry-->elc_stream_is_exists-->md_get_stream_nodes_count-->elc_send_status_info
cm_create_thread-->|选主线程,定时监控leader变化|elc_status_notify_entry-->elc_stream_notify_proc-->get_notify_item-->rep_try_promote_prio_leader-->rep_role_notify
```

## 消息处理函数

```c
    register_msg_process(MEC_CMD_VOTE_REQUEST_RPC_REQ, elc_vote_proc, PRIV_HIGH);
    register_msg_process(MEC_CMD_VOTE_REQUEST_RPC_ACK, elc_vote_ack_proc, PRIV_HIGH);
    register_msg_process(MEC_CMD_PROMOTE_LEADER_RPC_REQ, elc_promote_proc, PRIV_HIGH);
    register_msg_process(MEC_CMD_STATUS_CHECK_RPC_REQ, elc_status_check_req_proc, PRIV_HIGH);
    register_msg_process(MEC_CMD_STATUS_CHECK_RPC_ACK, elc_status_check_ack_proc, PRIV_HIGH);
```

- `MEC_CMD_VOTE_REQUEST_RPC_REQ`

```mermaid
graph TB
elc_vote_proc-->|获取当前节点|elc_stream_get_current_node-->|解码vote请求|elc_decode_vote_req-->|判断投票|elc_judge_vote-->|分配一个包进行相应|mec_alloc_pack-->|组装vote ack|elc_encode_vote_ack-->|发送给对端|mec_send_data-->|释放申请的包|mec_release_pack
```

- `MEC_CMD_VOTE_REQUEST_RPC_ACK`
- `MEC_CMD_PROMOTE_LEADER_RPC_REQ`
- `MEC_CMD_STATUS_CHECK_RPC_REQ`
- `MEC_CMD_STATUS_CHECK_RPC_REQ`
- `MEC_CMD_STATUS_CHECK_RPC_ACK`

## 消息流程

```mermaid
sequenceDiagram
节点1->>节点2: 发送MEC_CMD_STATUS_CHECK_RPC_REQ
节点2->>节点1: MEC_CMD_VOTE_REQUEST_RPC_ACK
```

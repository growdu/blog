# openguass dcf启动详解

- 先启动walreceiver

```mermaid
graph TB
RequestXLogStreaming-->SendPostmasterSignal
-->|PMSIGNAL_START_WALRECEIVER|CheckPostmasterSignal
-->|WALRECEIVER|initialize_util_thread
-->InternalThreadFunc
-->GetThreadEntry
-->|WALRECEIVER|GaussDbThreadMain
-->GaussDbAuxiliaryThreadMain
-->WalReceiverMain
```

- 启动walreceiver后，再启动dcf

```mermaid
graph TB
WalReceiverMain-->LaunchPaxos
-->InitPaxosModule
-->RegisterDcfCallBacks
-->InitDcfAndStart-->dcf_start
```

## openguass dcf主要处理逻辑

### 接收

dcf收到消息处理函数如下：

```c
static bool RegisterDcfCallBacks()
{
    if (dcf_register_after_writer(ConsensusLogCbFunc) != 0) {
        ereport(WARNING, (errmsg("Failed to register ConsensusLogCbFunc.")));
        return false;
    }
    if (dcf_register_consensus_notify(ReceiveLogCbFunc) != 0) {
        ereport(WARNING, (errmsg("Failed to register ReceiveLogCbFunc.")));
        return false;
    }
    if (dcf_register_status_notify(PromoteOrDemote) != 0) {
        ereport(WARNING, (errmsg("Failed to register PromoteOrDemote.")));
        return false;
    }
    if (dcf_register_exception_report(DCFExceptionCbFunc) != 0) {
        ereport(WARNING, (errmsg("Failed to register DCFExceptionCbFunc.")));
        return false;
    }
    if (dcf_register_election_notify(ElectionCbFunc) != 0) {
        ereport(WARNING, (errmsg("Failed to register ElectionCbFunc.")));
        return false;
    }
    if (dcf_register_msg_proc(ProcessMsgCbFunc) != 0) {
        ereport(WARNING, (errmsg("Failed to register ProcessMsgCbFunc.")));
        return false;
    }
    if (dcf_register_thread_memctx_init(DcfThreadShmemInit) != 0) {
        ereport(WARNING, (errmsg("Failed to register DcfThreadShmemInit.")));
        return false;
    }
    return true;
}
```

其中根据是否属于paxos消息通信又分为两类：

- 集群间消息
  
  集群信息是集群内的通信消息，某一节点发出其他节点均需要处理。
  
  - dcf_register_after_writer(ConsensusLogCbFunc)
    
    注册leader节点写入数据成功的回调函数（仅leader节点会触发该回调）

```mermaid
graph TB
ConsensusLogCbFunc-->SyncConfigFile
-->dcf_send_msg
SyncConfigFile-->dcf_broadcast_msg
dcf_send_msg-->DcfUpdateConsensusLsnAndIndex
dcf_broadcast_msg-->DcfUpdateConsensusLsnAndIndex
-->DcfUpdateAppliedRecordIndex
-->SyncPaxosReleaseWaiters
```

- dcf_register_consensus_notify(ReceiveLogCbFunc)
  
  follower节点写入数据成功的回调函数（仅follower节点会触发回调）

```mermaid
graph TB
ReceiveLogCbFunc-->CheckBuildReasons-->CheckConfigFile
-->XLogWalRcvReceive
-->DcfUpdateAppliedRecordIndex
```

- dcf_register_status_notify(PromoteOrDemote)
  
  节点角色变化的回调函数（只有当本节点变为leader会收到该回调）

```mermaid
graph TB
PromoteOrDemote-->PromoteCallbackFunc-->SendNotifySignal
PromoteOrDemote-->DemoteCallbackFunc-->ResetDCFNodesInfo
-->SendPostmasterSignal-->ProcessDemoteRequest
```

- dcf_register_election_notify(ElectionCbFunc)
  
  选举leader变化的回调函数.

- 节点间消息
  
  节点间消息为1对1消息，为普通tcp通信，为某一节点明确分为某一节点的消息。
  
  - dcf_register_msg_proc(ProcessMsgCbFunc)
    
    节点收到另一个节点发来的消息的回调函数

```mermaid
graph TB
ProcessMsgCbFunc-->|检查是否有leader|QueryLeaderNodeInfo
QueryLeaderNodeInfo-->|当前节点是leader|ReplyFollower
QueryLeaderNodeInfo-->|收到来自leader的消息|CheckLeaderReply
```

### 发送消息

发送消息同样分为集群间消息和节点间消息。

集群间消息所有节点都会收到并处理，节点间消息为一对一的tcp通信。

- 集群间消息发送
  
  - XLogWritePaxos

```mermaid
graph TB
WalWriterMain-->XLogBackgroundFlush-->XLogWritePaxos-->|往dcf集群写入数据仅leader节点能写入成功|dcf_write
XLogSelfFlush-->XLogBackgroundFlush
XLogInsert-->XLogInsertRecord-->XLogInsertRecordSingle-->
CopyXLogRecordToWAL-->XLogSelfFlushWithoutStatus-->XLogWritePaxos
```

- 节点间消息发送
  
  - DCFSendMsg

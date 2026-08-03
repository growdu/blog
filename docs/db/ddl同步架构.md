# ddl同步架构

## 整体架构

```shell
┌──────────────────────────────────────────────────────────────┐
│                     Publisher Side                           │
├──────────────────────────────────────────────────────────────┤
│ ProcessUtility()                                             │
│         ↓                                                    │
│ CapturePublicationSyncDDL()                                  │
│         ↓                                                    │
│  DDL Rule Filter                                             │
│ (DDL Type / Schema / Regex / Plugin Rule)                    │
│         ↓                                                    │
│ pg_publication_sync                                          │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼

┌──────────────────────────────────────────────────────────────┐
│               Logical Replication Layer                      │
├──────────────────────────────────────────────────────────────┤
│ Logical Decoding → pgoutput → Replication Protocol           │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ▼

┌──────────────────────────────────────────────────────────────┐
│                     Subscriber Side                          │
├──────────────────────────────────────────────────────────────┤
│ apply_handle_ddl()                                           │
│         ↓                                                    │
│  DDL Rule Filter                                             │
│ (subddl / Security / Object Rule / Regex Rule)              │
│         ↓                                                    │
│ Replay Framework                                             │
│         ↓                                                    │
│ execute_publication_sync_sql_command()                       │
└───────────────┬───────────────┬───────────────┬──────────────┘
                │               │               │
                ▼               ▼               ▼
       ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
       │ Babelfish   │  │ Oracle      │  │ MySQL       │
       │ Adapter     │  │ Adapter     │  │ Adapter     │
       └─────────────┘  └─────────────┘  └─────────────┘
```
## 分层架构

```shell
┌──────────────────────────────────────────────┐
│               DDL Producer                   │
├──────────────────────────────────────────────┤
│ Capture → Rule Filter → Message Store        │
│            (pg_publication_sync)             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼

┌──────────────────────────────────────────────┐
│          Replication Transport               │
├──────────────────────────────────────────────┤
│ Logical Decoding → pgoutput → Protocol       │
└──────────────────┬───────────────────────────┘
                   │
                   ▼

┌──────────────────────────────────────────────┐
│            DDL Replay Framework              │
├──────────────────────────────────────────────┤
│ Apply → Rule Filter → Replay Engine          │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   Babelfish    Oracle      MySQL
    Adapter     Adapter     Adapter
```
# DDL同步整体架构

```mermaid
flowchart TB

    subgraph PUB["Publisher Side"]
        PU["ProcessUtility()"]
        CAP["CapturePublicationSyncDDL()"]

        PF["DDL Rule Filter
Type / Schema / Regex / Plugin"]

        STORE["pg_publication_sync"]

        PU --> CAP
        CAP --> PF
        PF --> STORE
    end

    subgraph TRANS["Logical Replication Layer"]
        DEC["Logical Decoding"]
        OUT["pgoutput"]
        PROTO["Replication Protocol"]

        DEC --> OUT
        OUT --> PROTO
    end

    subgraph SUB["Subscriber Side"]

        APPLY["apply_handle_ddl()"]

        SF["DDL Rule Filter
subddl / Security / Object Rule"]

        REPLAY["DDL Replay Framework"]

        EXEC["execute_publication_sync_sql_command()"]

        APPLY --> SF
        SF --> REPLAY
        REPLAY --> EXEC
    end

    subgraph ADAPTER["Adapter Framework"]

        PG["PostgreSQL Adapter"]

        BABEL["Babelfish Adapter"]

        ORA["Oracle Adapter"]

        MYSQL["MySQL Adapter"]
    end

    STORE --> DEC

    PROTO --> APPLY

    EXEC --> PG
    EXEC --> BABEL
    EXEC --> ORA
    EXEC --> MYSQL
```
# DDL Replication Platform 分层架构

```mermaid
flowchart TB

    subgraph L1["DDL Producer Layer"]

        C1["Capture Framework"]

        C2["Rule Filter Framework"]

        C3["Message Store
pg_publication_sync"]

        C1 --> C2
        C2 --> C3

    end

    subgraph L2["Replication Transport Layer"]

        T1["Logical Decoding"]

        T2["pgoutput"]

        T3["Replication Protocol"]

        T1 --> T2
        T2 --> T3

    end

    subgraph L3["DDL Replay Framework"]

        R1["Apply Worker"]

        R2["Rule Filter"]

        R3["Replay Engine"]

        R1 --> R2
        R2 --> R3

    end

    subgraph L4["Adapter Framework"]

        A1["PostgreSQL"]

        A2["Babelfish"]

        A3["Oracle"]

        A4["MySQL"]

    end

    L1 --> L2

    L2 --> L3

    R3 --> A1
    R3 --> A2
    R3 --> A3
    R3 --> A4
```
# Replay Framework

```mermaid
flowchart LR

    MSG["DDL Message"]

    RF["Replay Framework"]

    RE["Replay Engine"]

    MSG --> RF

    RF --> RE

    RE --> PG["PostgreSQL Adapter"]

    RE --> BABEL["Babelfish Adapter"]

    RE --> ORA["Oracle Adapter"]

    RE --> MYSQL["MySQL Adapter"]
```
# Dual Rule Filter Framework

```mermaid
flowchart LR

    DDL["DDL SQL"]

    PF["Publisher Rule Filter"]

    MSG["DDL Message"]

    SF["Subscriber Rule Filter"]

    REP["Replay Engine"]

    DDL --> PF

    PF --> MSG

    MSG --> SF

    SF --> REP
```
# DDL Replication Platform

```mermaid
flowchart TB

    DDL["DDL SQL"]

    CAP["Capture Framework"]

    FILTER["Rule Filter Framework"]

    MSG["DDL Message"]

    TRANS["Replication Transport"]

    REPLAY["Replay Framework"]

    ADAPTER["Adapter Framework"]

    TARGET["Target Database"]

    DDL --> CAP

    CAP --> FILTER

    FILTER --> MSG

    MSG --> TRANS

    TRANS --> REPLAY

    REPLAY --> ADAPTER

    ADAPTER --> TARGET
```
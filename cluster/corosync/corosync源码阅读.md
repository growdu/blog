# corosync源码阅读

corosync采用服务的方式设计，使用totem协议作为分布式一致性协议，使用libqb库进行进程间通信。
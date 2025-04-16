# corosync共享多仲裁方案设计

## 需求背景

当前corosync仲裁方式qnetd的现状如下：

- 为保证corosync的高可用，在出现网络分区时需使用第三方仲裁来帮助corosync投票，来选择出quorate的一方。

- corosync官方提供的qnetd存在单点故障问题，且每个corosync集群只能连接一个qnetd
- 使用qnetd的lms算法时，因为qnetd的票数较高，在qnetd存活时，高可用性高；但qnetd挂掉后，高可用性显著降低，corosync集群节点不允许再挂掉

期望达到的要求：

- 尽量保证高可用性的要求，即qnetd的比重不能过高，即使qnetd挂死，也只相当于普通节点挂死

corosync通过votequorum模块允许添加第三方仲裁。

## 多仲裁

- corosync可以连接多个qnetd仲裁，每个仲裁1票
- 
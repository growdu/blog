```
iplist：
   192.168.11.121
   192.168.11.123
   192.168.1.129
port:
   21000
datadir
   /opengauss_210/ommdata210
GAUSSHOME
   /opengauss_210/opengauss
```

## 1\. 不使用om工具安装opengauss

```
#上传安装包步骤省略，默认传到/tmp下,使用root用户
yum install -y bzip2 bzip2-devel curl libaio&& \
groupadd omm210;  \
useradd -g omm210 -d /home/omm210 omm210;  \
mkdir -p /opengauss_210/{opengauss,ommdata210} && \
tar xf /tmp/openGauss-2.1.0-CentOS-64bit.tar.bz2 -C /opengauss_210/opengauss && \
chown -R omm210:omm210 /opengauss_210/ &&\

echo "export GAUSSHOME=/opengauss_210/opengauss"  >> /home/omm210/.bashrc && \
echo "export PATH=\$GAUSSHOME/bin:\$PATH " >> /home/omm210/.bashrc && \
echo "export LD_LIBRARY_PATH=\$GAUSSHOME/lib:\$LD_LIBRARY_PATH" >> /home/omm210/.bashrc
复制
```

## 2\. 初始化数据库

-   后续所有操作均使用omm210用户

```
# 初始化需要加-c参数，会生成dcf相关文件
gs_initdb --nodename=gaussdb1 -w og@123456  -D /opengauss_210/ommdata210/ -c
```

## 3\. 配置dcf参数

### 3.1. 配置白名单

```
#将下面信息添加到每个数据库的白名单中 /opengauss_210/ommdata210/pg_hba.conf
host    all             all            192.168.11.121/32       trust
host    all             all            192.168.1.229/32        trust
host    all             all            192.168.11.123/32       trust
```

### 3.2. 配置dcf参数与replconninfo

-   将以下信息依次添加到所有主机的/opengauss\_210/ommdata210/postgresql.conf 的最后面
    
-   192.168.11.123添加下列信息
    

```
port=21000
dcf_node_id = 1
dcf_ssl=off
dcf_data_path = '/opengauss_210/ommdata210/dcf_data'
dcf_log_path= '/opengauss_210/ommdata210/dcf_log'
dcf_config='[{"stream_id":1,"node_id":1,"ip":"192.168.11.123","port":21000,"role":"LEADER"},{"stream_id":1,"node_id":2,"ip":"192.168.11.121","port":21000,"role":"FOLLOWER"},{"stream_id":1,"node_id":3,"ip":"192.168.1.229","port":21000,"role":"FOLLOWER"}]'
replconninfo1 = 'localhost=192.168.11.123 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.11.121 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
replconninfo2 = 'localhost=192.168.11.123 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.1.229 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
# enable_dcf = on  #初始化时加-c参数会自动打开
```

-   192.168.11.121添加下列信息

```
port=21000
dcf_node_id = 2
dcf_ssl=off
dcf_data_path = '/opengauss_210/ommdata210/dcf_data'
dcf_log_path= '/opengauss_210/ommdata210/dcf_log'
dcf_config='[{"stream_id":1,"node_id":1,"ip":"192.168.11.123","port":21000,"role":"LEADER"},{"stream_id":1,"node_id":2,"ip":"192.168.11.121","port":21000,"role":"FOLLOWER"},{"stream_id":1,"node_id":3,"ip":"192.168.1.229","port":21000,"role":"FOLLOWER"}]'
replconninfo1 = 'localhost=192.168.11.121 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.11.123 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
replconninfo2 = 'localhost=192.168.11.121 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.1.229 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
# enable_dcf = on  #初始化时加-c参数会自动打开
```

-   192.168.1.229添加下列信息

```
port=21000
dcf_node_id = 3
dcf_ssl=off
dcf_data_path = '/opengauss_210/ommdata210/dcf_data'
dcf_log_path= '/opengauss_210/ommdata210/dcf_log'
dcf_config='[{"stream_id":1,"node_id":1,"ip":"192.168.11.123","port":21000,"role":"LEADER"},{"stream_id":1,"node_id":2,"ip":"192.168.11.121","port":21000,"role":"FOLLOWER"},{"stream_id":1,"node_id":3,"ip":"192.168.1.229","port":21000,"role":"FOLLOWER"}]'
replconninfo1 = 'localhost=192.168.1.129 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.11.121 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
replconninfo2 = 'localhost=192.168.1.129 localport=21001 localheartbeatport=21005 localservice=21004 remotehost=192.168.11.123 remoteport=21001 remoteheartbeatport=21005 remoteservice=21004'
# enable_dcf = on  #初始化时加-c参数会自动打开
```

## 4\. 启动opengauss

### 4.1. 集群全部节点以standby的模式启动

```
gs_ctl start -D /opengauss_210/ommdata210 -M standby
```

### 4.2. 手动设置存活节点为少数派模式运行，在主节点执行（即 LEADER）

```
gs_ctl setrunmode -D /opengauss_210/ommdata210  -v 1 -x minority
```

### 4.3. 集群其他节点主动重建拉起，在所有备节点执行（即 FOLLOWER）

```
gs_ctl build -b full -Z single_node -D /opengauss_210/ommdata210
```

### 4.4. 存活节点重回多数派，在主节点执行（即 LEADER）

```
gs_ctl setrunmode -D /opengauss_210/ommdata210 -x normal
```

### 4.5. 全部节点查看状态

```
gs_ctl query -D /opengauss_210/ommdata210
```

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-b44a1ee0-c040-4a72-8cd5-53f9264bbae1.png)

## 5\. 测试集群

### 5.1. 数据同步测试

#### （1）数据修改前集群各节点情况

node1  
![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-e9904c2a-91c2-4447-b023-4fc9c808fd22.png)

node2  
![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-c1415839-b4da-4da4-a65c-3561996974aa.png)

node3  
![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-6fd3a915-50bb-489a-800e-91fb5849de98.png)

#### （2）在node1（LEADER）创建表，插入数据

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-2979bdc4-9370-4376-9455-7a8a57b85fb7.png)

#### （3）在其他节点查看是否同步

node2  
![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-16d94d20-b8ce-4b57-a1fb-7aa4fe9aca02.png)

node3  
![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-b5475f6b-c835-4c5a-a670-eea036f95980.png)

### 5.2. LEADER异常切换测试

#### （1）模拟异常前状态

```
gs_ctl query -D /opengauss_210/ommdata210
```

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-928f9455-43ff-4627-9d09-bb26599f8ce1.png)

-   可以看到node1为LEADER,图片所示状态是在FOLLOWER节点查看

#### （2）将LEADER stop

```
gs_ctl stop -D /opengauss_210/ommdata210
```

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-27edda99-02a8-41b5-94ab-223a6d34d46f.png)

#### （3）查看当前集群状态

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-49d72411-7984-4443-ae80-c5e1681cfe1b.png)

-   可以看到node2已经切换为LEADER

#### （4）将旧LEADER重启

```
gs_ctl start -D /opengauss_210/ommdata210 -M standby#以standby的方式启动
gs_ctl query -D /opengauss_210/ommdata210#再次查看状态
```

![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-d1577416-d5b8-432b-a231-9156a8e042fe.png)

-   仍然是node2为LEADER，node1以FOLLOWER加入集群
-   node1以FOLLOWER加入集群是因为启动时指定了standby模式，如果未指定，则不会加入集群

### 5.3. switchover测试

```
#在node1执行switchover命令
gs_ctl switchover -D /opengauss_210/ommdata210/
```

-   执行后集群状态和node2（旧LEADER）状态  
    ![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-56837002-8360-48ea-824e-684bc88612df.png)  
    node2  
    ![image.png](https://oss-emcsprod-public.modb.pro/image/editor/20211125-a64d388d-fc98-49d7-b1a8-50a038117c7e.png)
    
-   可见node2已经shutdown，不手动以standby的模式启动的话，无法加入集群
    
-   备注
    

```
1. opengauss的dcf模式，对switchover的兼容性并没有达到100%
普通主备架构执行switchover命令后，主库会自动降为备，备库也会自动提升为主
然而dcf模式下，switchover后旧LEADER会被shutdown，而不会重启为FOLLOWER，需要手动重启
2. opengauss的自动异常切换，并没有一个权重的概念，集群内节点随机切换，这样在跨机房/地区的情况下不是很友好，希望dcf模式继续发展
```
# windows的139、445端口到底在做什么

## 139端口

NBT 协议（NetBIOS over TCP/IP）是一种用于在 TCP/IP 网络上实现 NetBIOS 服务的协议。
NBT使用137（UDP）、138（UDP）和139（TCP）来实现基于TCP/IP的NETBIOS网际互联。
而139端口的作用就是获得NETBIOS/SMB服务（即NetBIOS File and Print Sharing协议），这个协议被用于Windows文件和打印机共享。

## 445端口

445端口是一个毁誉参半的端口，它能够让我们可以在局域网中轻松访问各种共享文件夹或共享打印机。
445端口使用的是SMB（Server Message Block）协议，在Windows NT中SMB基于NBT实现，而在 Windows 2000/XP/2003 中，SMB除了基于NBT实现还直接通过445端口实现。
而在windows中，SMB协议通过windows服务LanmanServer来实现。

## 139端口和445端口的区别

1. 139端口是在NBT协议基础上，而445端口是在TCP/IP协议基础上
2. 在客户端开启了NBT的情况下，139得到回应则从139端口进行会话，而如果是445端口得到回应则445端口进行会话。
3. 在服务器禁用了NBT的情况下，不会监听139端口，只会监听445端口
4. <font color="red">在低版本的windows系统里（比如windows7），139端口的功能和445端口的功能是一致的，都是文件共享。进行文件共享时会先去尝试访问445端口，445端口无法访问再去访问139端口。</font>

## 如果445端口没有在监听会影响windows7的功能吗

不会。若默认没有监听445端口，监听139端口其功能也是一致的。
而且LanmanServer不依赖于445端口，即使没有445端口，LanmanServer也能正常运行，文件共享服务不受影响。
因而，即使我们在127.0.0.1监听445端口也不会对现有功能造成影响。
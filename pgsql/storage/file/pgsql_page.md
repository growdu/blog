# pgsql之page


## 基本概念

文件是数据库的持久化存储，当然我们已经知道数据库的relation以文件的形式存在在磁盘上，无论是xxx文件还是xxx_fsm,还是xxx_vm，这是文件的概念。
当relation的xxx的文件特别大，超过1G的时候，同一个relation还会分文件存储，出现xxx.1，xxx.2这种文件。
所谓block，指的是每次加载进内存的基本单位，如果PostgreSQL需要某个relation的信息，不会是直接relation对应的磁盘文件全部读入内存，而是分block载入内存。
PostgreSQL有一定的规则知道自己需要的信息或者记录或者说tuple 落在磁盘文件的那个8K block上，然后将8K block加载入local buffer，或者shared buffer，总之加载入内存。
简单的说，block是磁盘上文件和内存之间加载/驱逐的基本单位。

## page

page大小也是8K，就是上面提到的block，只不过，page仔细的端详了8KB的内容，分析了信息是如何组织，如何存放到8KB的block空间之内。

page，就是管理8K大小的一亩三分地，他要把多条记录（Tuple）有条不紊地组织在这8K的空间之内。

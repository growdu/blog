# pktgen

- 编译环境

```shell
ssh duanyings@10.252.0.64
cd /home/duanyingshou/github/pktgen-dpdk
```

- 下载源码

```shell
git clone http://dpdk.org/git/apps/pktgen-dpdk
git checkout pktgen-19.12.0
# dpaa2
export RTE_SDK=/home/duanyingshou/github/dpdk
export RTE_TARGET=arm64-dpaa2-linuxapp-gcc
export CROSS=aarch64-linux-gnu-
make
# x86
export RTE_SDK=/home/duanyingshou/github/dpdk
export RTE_TARGET=x86_64-native-linuxapp-gcc
make
cd <Pktgen compiled source code>
cp Pktgen.lua <target board>
cp app/app/arm64-dpaa-linuxapp-gcc/pktgen <target board>
```

## lua交叉编译

```shell
wget http://www.lua.org/ftp/lua-5.4.3.tar.gz
```

## 使用

```shell
pktgen -c 0xc --socket-mem 1024 -n 2 -- -P -m [2:3].0 -s 0:5gc.pcap -T --crc-strip
# -c cpu core mask
# -m [18:19].1 18core用来做rx，19core用来作tx，使用dpdk的port1
# -s 1:5gc.pcap 使用port1来回放5gc.pcap
```



# reference

1. https://blog.csdn.net/firebolt2002/article/details/79808169

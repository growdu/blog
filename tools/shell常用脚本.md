# shell常用脚本

## 计算程序运行时间

### 按秒计算

```shell
#!/bin/bash

start=$(date +%s)
#你要执行的操作


end=$(date +%s)
take=$(( end - start ))
echo Time taken to execute commands is ${take} seconds.
```

### 按毫秒计算

```shell
#!/bin/bash
start=$(date +%s%3N)
# 你要执行的操作

end=$(date +%s%3N)
take=`expr ${end} - ${start}`
echo Time taken to execute commands is ${take} ms.
```

## 循环执行

```shell
#!/bin/bash
#一般先声明数组，在里面填循环的东西
ips=(192.168.1.1 192.168.1.2)
for ip in ${ips[@]}
do
	echo "${ip}"
done

# 从第二个元素开始
for ip in ${ips[@]:1}
do
	echo "${ip}"
done
```

## 条件判断

### 字符串判断

```shell
#!/bin/bash
ip="192.168.1.1"
if [ "${ip}"x == ""x ];
then
	echo "eqal"
fi
```

### 数字判断

```shell
#!/bin/bash
ip=192
if [ ${ip} -eq 192 ];
then
	echo "equal"
fi
```

### 文件判断

```shell
#!/bin/bash
ip="192"
if [ -d ${ip} ];
then
	echo "exist"
fi
```


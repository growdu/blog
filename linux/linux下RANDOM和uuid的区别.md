# linux下RANDOM和uuid的区别

## RANDOM

> `$RANDOM` 是 Bash 中用来生成 0 至 32767 之间随机整数[[1\]](https://clay-wangzhi.com/code/shell/part3/09_3_random_generate_random_integer.html#footnote1)的一个内置 [函数](https://clay-wangzhi.com/code/shell/part3/09_3_random_generate_random_integer.html)（而非常量）。

## uuid

> **UUID 的目的**，是让分布式系统中的所有元素，都能有唯一的辨识信息，而不需要通过中央控制端来做辨识信息的指定。如此一来，每个人都可以创建不与其它人冲突的 UUID。在这样的情况下，就不需考虑数据库创建时的名称重复问题。它会让网络任何一台计算机所生成的uuid码，都是互联网整个服务器网络中唯一的。它的原信息会加入硬件，时间，机器当前运行信息等等。
>
> **UUID格式是：**包含32个[16进位](http://zh.wikipedia.org/wiki/十六進位)数字，以“-”连接号分为五段，形式为8-4-4-4-12的32个字符。范例；550e8400-e29b-41d4-a716-446655440000 ,所以：UUID理论上的总数为216 x 8=2128，约等于3.4 x 1038。 也就是说若每奈秒产生1兆个UUID，要花100亿年才会将所有UUID用完。
>
> linux的uuid码也是由内核提供的，在/proc/sys/kernel/random/uuid这个文件内。
>
> ```shell
> cat /proc/sys/kernel/random/uuid
> dff68213-b700-4947-87b1-d9e640334196
> ```
>
> 也可以使用命令uuidgen生成uuid。

1. RANDOM与uuid的生成都与/dev/random设备有关系。
2. RANDOM是一个5位数以内的整数，不同的机器有可能会生成相同的RANDOM；
3. uuid为32个字符，不同的机器一般不会生成相同的uuid；
4. linux下生成uuid和RANDOM的方式是通用的。
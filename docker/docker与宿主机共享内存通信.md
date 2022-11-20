# docker与宿主机共享内存通信

docker中的进程要与宿主机使用共享内存通信，需要在启动容器的时候指定<font color="red">“--ipc=host”</font>选项。然后再编写相应的共享内存的程序，一个跑在宿主机上，另一个跑在docker上面。

## 宿主机程序准备

- shm_data.h

```c
#ifndef _SHMDATA_H_HEADER
#define _SHMDATA_H_HEADER
 
#define TEXT_SZ 2048
 
struct shared_use_st
{
    int written; // 作为一个标志，非0：表示可读，0：表示可写
    char text[TEXT_SZ]; // 记录写入 和 读取 的文本
};
 
#endif
```

- shm_slave.c

```c
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/shm.h>
#include "shmdata.h"
 
int main(int argc, char **argv)
{
    void *shm = NULL;
    struct shared_use_st *shared = NULL;
    char buffer[BUFSIZ + 1]; // 用于保存输入的文本
    int shmid;
 
    // 创建共享内存
    shmid = shmget((key_t)1234, sizeof(struct shared_use_st), 0666|IPC_CREAT);
    if (shmid == -1)
    {
        fprintf(stderr, "shmget failed\n");
        exit(EXIT_FAILURE);
    }
 
    // 将共享内存连接到当前的进程地址空间
    shm = shmat(shmid, (void *)0, 0);
    if (shm == (void *)-1)
    {
        fprintf(stderr, "shmat failed\n");
        exit(EXIT_FAILURE);
    }
 
    printf("Memory attched at %X\n", (int)shm);
 
    // 设置共享内存
    shared = (struct shared_use_st *)shm;
    while (1) // 向共享内存中写数据
    {
        // 数据还没有被读取，则等待数据被读取，不能向共享内存中写入文本
        while (shared->written == 1)
        {
            sleep(1);
            printf("Waiting...\n");
        }
 
        // 向共享内存中写入数据
        printf("Enter some text: ");
        fgets(buffer, BUFSIZ, stdin);
        strncpy(shared->text, buffer, TEXT_SZ);
 
        // 写完数据，设置written使共享内存段可读
        shared->written = 1;
 
        // 输入了end，退出循环（程序）
        if (strncmp(buffer, "end", 3) == 0)
        {
            break;
        }
    }
 
    // 把共享内存从当前进程中分离
    if (shmdt(shm) == -1)
    {
        fprintf(stderr, "shmdt failed\n");
        exit(EXIT_FAILURE);
    }
 
    sleep(2);
    exit(EXIT_SUCCESS);
}
```

- makefile

```makefile
all:
	gcc -o shm_slave shm_slave.c
clean:
	rm -rf shm_slave
```

## docker镜像准备

- shm_data.h

```c
#ifndef _SHMDATA_H_HEADER
#define _SHMDATA_H_HEADER
 
#define TEXT_SZ 2048
 
struct shared_use_st
{
    int written; // 作为一个标志，非0：表示可读，0：表示可写
    char text[TEXT_SZ]; // 记录写入 和 读取 的文本
};
 
#endif
```

- shm_master.c

```c
#include <stddef.h>
#include <sys/shm.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include "shmdata.h"
 
int main(int argc, char **argv)
{
    void *shm = NULL;
    struct shared_use_st *shared; // 指向shm
    int shmid; // 共享内存标识符
    // 将内容写入到文件，可以通过查看文件确定共享内存是否成功
    FILE* file = fopen("t.txt","w+");
 
    // 创建共享内存
    shmid = shmget((key_t)1234, sizeof(struct shared_use_st), 0666|IPC_CREAT);
    if (shmid == -1)
    {
        fprintf(stderr, "shmat failed\n");
        exit(EXIT_FAILURE);
    }
 
    // 将共享内存连接到当前进程的地址空间
    shm = shmat(shmid, 0, 0);
    if (shm == (void *)-1)
    {
        fprintf(stderr, "shmat failed\n");
        exit(EXIT_FAILURE);
    }
 
    printf("\nMemory attached at %X\n", (int)shm);
 
    // 设置共享内存
    shared = (struct shared_use_st*)shm; // 注意：shm有点类似通过 malloc() 获取到的内存，所以这里需要做个 类型强制转换
    shared->written = 0;
    while (1) // 读取共享内存中的数据
    {
        // 没有进程向内存写数据，有数据可读取
        if (shared->written == 1)
        {
            printf("You wrote: %s", shared->text);
            fputs(shared->text,file);
            fflush(file);
            sleep(1);
 
            // 读取完数据，设置written使共享内存段可写
            shared->written = 0;
 
            // 输入了 end，退出循环（程序）
            if (strncmp(shared->text, "end", 3) == 0)
            {
                break;
            }
        }
        else // 有其他进程在写数据，不能读取数据
        {
            sleep(1);
        }
    }
 
    // 把共享内存从当前进程中分离
    if (shmdt(shm) == -1)
    {
        fprintf(stderr, "shmdt failed\n");
        flcose(file);
        exit(EXIT_FAILURE);
    }
 
    // 删除共享内存
    if (shmctl(shmid, IPC_RMID, 0) == -1)
    {
        fprintf(stderr, "shmctl(IPC_RMID) failed\n");
        fclose(file);
        exit(EXIT_FAILURE);
    }
 	flcose(file);
    exit(EXIT_SUCCESS);
}
```

- makefile

```makefile
all:
	gcc -o shm_master shm_master.c
clean:
	rm -rf shm_master
```

- Dockerfile

```dockerfile
FROM gcc:latest

RUN  mkdir /usr/src/shm_test

COPY shm_master.c shm_data.h makefile /usr/src/shm_test/

WORKDIR /usr/src/shm_test

RUN  make

CMD ["./shm_master"]
```

## 运行

运行时需要先下载docker，获取支持c语言编译运行的基础镜像，比如ubuntu、gcc等。这里使用gcc作为基础镜像。

```shell
sudo apt install docker
sudo docker pull gcc
# 查看一下gcc的镜像是否拉取下来了
docker images
```

基础镜像有了后就可以基于基础镜像构建docker容器，基于上面所写的dockerfile，构建镜像：

```shell
sudo docker build -t shm_master:v1 .
# 查看镜像是否创建成功
sudo docker images
```

镜像创建成功后就可以启动容器，启动时记得加上参数“--ipc”。

```shell
# fe9c3bd6d102是之前创建成功的镜像的id
sudo docker run -d --ipc=host --name master fe9c3bd6d102
```

成功启动容器后可以进入到容器内部查看通信相关信息。

```shell
sudo docker exec -it master /bin/bash
```

运行结果如下图所示：

![](./docker_image/docker_ipc_with_host.png)

## docker与宿主机通信时间损耗

在当前demo中，宿主机本地ipc通信时间损耗如下：

```shell
send time:1641533324779
send content:test
recv time:1641533326499
send time:1641533327499
send content:end
recv time:1641533328779
```

宿主机与docker通信时间损耗如下：

```shell
send time:1641533611791
send content:test
recv time:1641533614055
send time:1641533615056
send content:end
recv time:1641533617589
```

通过计算，宿主机本地ipc通信损耗为1720ms和1280ms，平均1500ms；宿主机与docker ipc通信损耗为2264ms和2533ms，平均为2398ms。<font color="red">从这个结果来看，宿主机与docker ipc通信损耗要稍微高一些。</font>

# reference

1. https://www.cnblogs.com/hailun1987/p/9697236.html

2. https://www.jianshu.com/p/7eb7c7f62bf3
3. https://www.cnblogs.com/52php/p/5861372.html


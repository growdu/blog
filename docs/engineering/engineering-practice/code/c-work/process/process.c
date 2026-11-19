#include <sys/types.h>
#include <stdio.h>
#include <stdlib.h>
int glob=10;
static void my_exit1(void)  //进程退出时调用函数
{
    printf("pid=%d first exit handler\n",getpid());
}

static void my_exit2(void)
{
    printf("pid=%d second exit handler\n",getpid());
}

int main()
{
    int local;
    pid_t pid;
    local=8;
    if(atexit(my_exit1)!=0)  //为进程注册的退出时调用函数也会被子进程共享，先注册的后调用
    {
        perror("atexit");
    }

    if(atexit(my_exit2)!=0)
    {
        perror("atexit");
    }

    if((pid=fork())==0)
    {
        printf("child pid is %d\n",getpid());   //子进程执行某个任务完后尽量使用exit退出，不然，若父进程中创建的子进程位于循环中，可能会引起未知的行为
    }
    else if(pid>0)
    {
        sleep(10);
        glob++;
        local--;
        printf("father pid is %d\n",getpid());       
    }
    else
    {
        perror("fork");
    }
    printf("pid=%d,glob=%d,localar=%d\n",getpid(),glob,local);//这段代码父子进程共享
    return 0;//也可以使用exit(0)
}

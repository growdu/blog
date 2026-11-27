#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>

#include <sys/types.h>
#include <sys/stat.h>
int main()
{
    puts("dup test.");
    int fd=-1;
    fd=open("tmp",O_WRONLY|O_CREAT|O_TRUNC,0664);

    /*if error*/
    #if 0
    close(1);//关闭标准输出
    dup(fd);
    #endif
    dup2(fd,1);
    close(fd);
    puts("dup test.");
    return 0;
}


#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>


int main()
{
    pid_t pid;
    printf("[%d] Starts!\n",getpid());

    pid=fork();
    if(pid<0){
        perror("fork()");
        exit(1);
    }else if(0==pid){
        printf("[%d] Child process.\n",getpid());
    }else{
        printf("[%d] Parent process.\n",getpid());
    }

    sleep(10);

    puts("End");

    return 0;
}


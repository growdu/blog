#include <stdio.h>
#include <shadow.h>
#include <unistd.h>
#include <string.h>

int main(int argc,char **argv)
{
    char name[32]="",*pwd;
    struct spwd *p;
    size_t namelen=0;

    printf("请输入用户名：");
    fgets(name,32,stdin);
    pwd=getpass("\n请输入密码：");

    namelen=strlen(name);
    name[namelen-1]=0;
    p=getspnam(name);
    if(!p){
        fprintf(stderr,"用户名或密码错误。\n");
        return -1;
    }

    if(!strcmp(crypt(pwd,p->sp_pwdp),p->sp_pwdp)){
        printf("\n密码正确。");
    }else{
        fprintf(stderr,"用户名或密码错误。\n");
    }
    return 0;
}


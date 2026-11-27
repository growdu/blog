#include <stdio.h>
#include <stdlib.h>
#include <glob.h>
#include <unistd.h>
#include <string.h>

#include <sys/types.h>
#include <sys/stat.h>

#define BUFSIZE 1024

int path_noloop(const char *path){
    //去除.和..
    char *pos=strrchr(path,'/');
    if(pos){
        if((!strcmp("/.",pos))
           ||(!strcmp("/..",pos))){
            return 0;
        }
    }else if((!strcmp(".",path))||(!strcmp("..",path))){
        return 0;
    }
    return 1;
}

int mydu(const char *path){
    static char str[BUFSIZE]="";
    glob_t globt;
    int i=0,ret=0;
    struct stat buf;

    lstat(path,&buf);
    
    //path为目录文件
    if(S_ISDIR(buf.st_mode)){
        //非隐藏文件
        snprintf(str,BUFSIZE,"%s/*",path);
        glob(str,0,NULL,&globt);
        ret=buf.st_blocks;

        for(i=0;i<globt.gl_pathc;i++){
            if(path_noloop(globt.gl_pathv[i])){
                ret+=mydu(globt.gl_pathv[i]);
            }
        }
        globfree(&globt);
    }else{
        ret=buf.st_blocks;
    }
    return ret;
}

int main(int argc,char **argv)
{
    if(argc<2)
        return 1;

    printf("%d\n",mydu(argv[1])/2);
    exit(0);
}


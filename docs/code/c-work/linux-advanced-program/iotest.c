#include <stdio.h>
#include<unistd.h>

int main(){
    
    for(int i=0;i<3;i++){
        putchar('a');
        write(1,"b",1);
    }
    printf("\n");

    return 0;
}
/*标准IO图吞吐量高，系统IO实时性好
 * */
/*输出结果会是bbbaaa
 * 标准IO具有合并系统调用的功能
 * stdout默认使用行缓冲
 * */

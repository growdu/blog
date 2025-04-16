#include <stdio.h>
#include <stdlib.h>
void f1(void){
    puts("f1");
}
void f2(void){
    puts("f2");
}

void f3(void){
    puts("f3");
}
void f4(void){
    puts("f4");
}

int main()
{
    puts("Begin!");
    
    atexit(f1);
    atexit(f2);
    atexit(f3);
    atexit(f4);
    
    puts("End!");
    exit(0);
}


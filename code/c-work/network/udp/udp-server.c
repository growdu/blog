// file name : udpserver.c
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define BUFLEN 512    //数据缓冲区的大小

void error(const char* message){
  fprintf(stderr, "%s\n", message);
  exit(1);
}

int main(int argc, char* argv[]){
  int server_fd ;
  int recv_len ;   // 保存接收到的数据长度
  char buf[BUFLEN] = {0}; //保存接收到的数据
  struct sockaddr_in si_me, si_other;
  int slen = sizeof(si_other);
  
  if(argc < 2){
    fprintf(stderr, "USAGE : %s  port\n", argv[0]);
    exit(1);
  }
  // 创建套接字，指明使用的是数据包协议
  if((server_fd=socket(AF_INET, SOCK_DGRAM, 0))==-1){
    error("Error to create socket");
  }
  // 设置服务器参数
  memset(&si_me, 0, sizeof(si_me));
  si_me.sin_family = AF_INET;
  si_me.sin_port = htons( atoi(argv[1]) );  
  si_me.sin_addr.s_addr = htonl(INADDR_ANY);
  // 将udp套接字绑定到指定端口
  if(bind(server_fd, &si_me, sizeof(si_me)) == -1){
    error("Error when bind to port");
  }
  // 循环：接收数据并写回
  while(1){
    memset(buf, 0, BUFLEN);
    printf("Waiting from data ...\n");
    if( (recv_len = recvfrom(server_fd, buf, BUFLEN-1, 0, 
      &si_other, &slen)) == -1){
      error("Error receive from udp client");
    }
    printf("Receive : %s\n", buf);
    if(sendto(server_fd, buf, strlen(buf), 0, &si_other, slen) == -1){
      error("Error send to udp client");
    }
  }
  close(server_fd);
  return 0;
}
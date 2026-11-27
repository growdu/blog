// file name : client.c
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include<arpa/inet.h>

void error(char* msg){
  fprintf(stderr, "%s\n", msg);
  exit(1);
}

int main(int argc, char* argv[]){
  int sockfd, portno, n;
  struct sockaddr_in serv_addr;
  char buffer[256] = {0};

  if(argc < 3){
    // 使用客户端的方式为 ：执行文件名   主机名或IP   端口号
    fprintf(stderr, "usage %s hostname port\n", argv[0]);
    exit(1);
  }
  portno = atoi(argv[2]);
  // 创建套接字
  sockfd = socket(AF_INET, SOCK_STREAM, 0);  
  if(sockfd == NULL) exit("Error opening socket");
  
  // 设置待连接服务器参数
  memset(&serv_addr, 0, sizeof(serv_addr));
  serv_addr.sin_family = AF_INET ;
  serv_addr.sin_addr.s_addr = inet_addr(argv[1]);
  serv_addr.sin_port = htons(portno);
  
  // 连接指定服务器
  if(connect(sockfd, &serv_addr, sizeof(serv_addr)) < 0)
    error("Error connecting");
  printf("Please enter the massage : ");
  fgets(buffer, 255, stdin);
  // 向服务器发送数据
  n = write(sockfd, buffer, strlen(buffer));
  if(n < 0) error("Error writing to socket");
  memset(buffer, 0, 256);
  // 读取服务器发送过来的数据
  n = read(sockfd, buffer, 255);
  if(n < 0)
    error("Error reading from socket");
  printf("%s\n", buffer);
  return 0;
}
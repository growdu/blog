// file name : server.c
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>  //定义了大量系统调用需要使用的类型
#include <sys/socket.h>  //定义了大量套接字所需要的结构体
#include <netinet/in.h>  //与网络相关的结构体及函数

// 该函数将字符串 msg 输出到 stderr，并退出执行
void error(char* msg){
  fprintf(stderr, "%s\n", msg);
  exit(1);
}
int main(int argc , char* argv[]){
  int sockfd;   //保存服务器套接字的文件描述符
  int newsockfd;   //保存与客户端通讯套接字的文件描述符
  int portno;   //保存服务器要绑定的端口号
  int clilen;   //保存client地址的大小，系统调用时需要使用
  int n;   //存放函数read、write的返回值
  char buffer[256];   //服务器将从套接字中读取的字符存入该缓存
  struct sockaddr_in serv_addr, cli_addr ; //存放服务器、客户端套接字属性
  if(argc < 2) error("Error : no port provided.\n");
  sockfd = socket(AF_INET , SOCK_STREAM , 0); //创建TCP套接字
  if(sockfd < 0) error("Error : fail to open socket");
  memset(&serv_addr , 0 , sizeof(serv_addr));
  portno = atoi(argv[1]) ;  //将输入的第二个参数转换为端口号

  // 配置服务器参数
  serv_addr.sin_family = AF_INET;
  serv_addr.sin_port = htons(portno);
  serv_addr.sin_addr.s_addr = INADDR_ANY;  //本机地址 0

  if(bind(sockfd, (const struct sockaddr*)&serv_addr, 
    sizeof(serv_addr) ) < 0){
    error("Error : binding");
  }
  listen(sockfd, 5);  //进行端口侦听
  clilen = sizeof(cli_addr);
  //阻塞等待客户端的连接
  newsockfd = accept(sockfd, (struct sockaddr*) &cli_addr, &clilen);
  if(newsockfd < 0){
    error("Error on accept");
  }
  memset(buffer, 0, 256);
  n = read(newsockfd, buffer, 255);
  if(n < 0) error("Error reading from socket");
  printf("client message : %s\n" , buffer);
  n = write(newsockfd, "I got your message", 18);
  if(n < 0)error("Error writing to socket");
  close(newsockfd);
  close(sockfd);
  return 0;
}

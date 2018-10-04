// file name : udpclient.c
#include <stdio.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <string.h>

#define BUFLEN 512

void error(const char* message){
  fprintf(stderr, "%s\n", message);
  exit(1);
}

int main(int argc, char* argv[]){
  int clientSocket, portNum, nBytes;
  char buffer[BUFLEN];
  struct sockaddr_in serverAddr;
  socklen_t addr_size;

  if(argc < 3){
    fprintf(stderr, "USAGE : %s  ip  port \n", argv[0]);
    exit(1);
  }
  // 创建客户端套接字
  if((clientSocket = socket(PF_INET, SOCK_DGRAM, 0))==-1){
    error("Error to create udp socket");
  }

  // 配置连接属性
  serverAddr.sin_family = AF_INET;
  serverAddr.sin_port = htons(atoi(argv[2]));
  serverAddr.sin_addr.s_addr = inet_addr(argv[1]);
  memset(serverAddr.sin_zero, '\0', sizeof serverAddr.sin_zero);  
  addr_size = sizeof serverAddr;

  while(1){
    printf("请输入发送数据:");
    fgets(buffer,BUFLEN,stdin);
    nBytes = strlen(buffer) + 1;
    
    /*将命令行收到的数据发送到服务器端*/
    sendto(clientSocket,buffer,nBytes,0,&serverAddr,addr_size);

    /*接收从服务器端发送来的数据*/
    nBytes = recvfrom(clientSocket,buffer,BUFLEN,0,NULL, NULL);
    printf("接收数据: %s\n",buffer);
  }
  return 0;
}
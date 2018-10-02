# 文件基本操作

* 读取文件
* 写入文件
* 重命名文件
* 读取目录
* 读取目录下的文件
* 创建目录
* 在创建目录下写入文件
* 不同文件格式之间进行转换

各种编程语言都实现了文件的基本操作，提供了对应的接口，熟悉并能使用即可。涉及到文件操作，另一个无法避免的问题是字符（串）操作，最终写入文件的是字符串。

## C语言

流程

打开文件 --> 关闭文件。

### 打开文件
```C
//filename 是字符串，用来命名文件,mode是访问模式
FILE *fopen( const char * filename, const char * mode );
//二进制文件，使用下面的访问模式关键字
//"rb", "wb", "ab", "rb+", "r+b", "wb+", "w+b", "ab+", "a+b"
```

|模式|描述|
|:--|:--|
|r|打开一个已有的文本文件，允许读取文件。|
|w|打开一个文本文件，允许写入文件。如果文件不存在，则会创建一个新文件，程序会从文件的开头写入内容。如果文件存在，则该文件会被截断为零长度，重新写入。|
|a|打开一个文本文件，以追加模式写入文件。如果文件不存在，则会创建一个新文件，会在已有的文件内容中追加内容。|
|r+|打开一个文本文件，允许读写文件。|
|w+|打开一个文本文件，允许读写文件。如果文件已存在，则文件会被截断为零长度，如果文件不存在，则会创建一个新文件。|
|a+|打开一个文本文件，允许读写文件。如果文件不存在，则会创建一个新文件。读取会从文件的开头开始，写入则只能是追加模式。|

### 关闭文件

```c
 int fclose( FILE *fp );
```

### 写入文件

```c
//把参数 c 的字符值写入到 fp 所指向的输出流中。如果写入成功，它会返回写入的字符，如果发生错误，则会返回 EOF
int fputc( int c, FILE *fp );
//把字符串 s 写入到 fp 所指向的输出流中。如果写入成功，它会返回一个非负值，如果发生错误，则会返回 EOF
int fputs( const char *s, FILE *fp );
//将格式化字符串写入到文件中
int fprintf(FILE *fp,const char *format, ...); 
```

### 读取文件

```c
//读取单个字符，返回值是读取的字符，如果发生错误则返回 EOF
int fgetc( FILE * fp );
//函数 fgets() 从 fp 所指向的输入流中读取 n - 1 个字符。它会把读取的字符串复制到缓冲区 buf，并在最后追加一个 null 字符来终止字符串。
char *fgets( char *buf, int n, FILE *fp );
//在遇到第一个空格字符时，会停止读取
int fscanf(FILE *fp, const char *format, ...);
```
### 二进制I/O函数

```c
//存储块的读写 - 通常是数组或结构体
size_t fread(void *ptr, size_t size_of_elements, 
             size_t number_of_elements, FILE *a_file);
              
size_t fwrite(const void *ptr, size_t size_of_elements, 
             size_t number_of_elements, FILE *a_file);
```

### 补充

```C
//fseek 可以移动文件指针到指定位置读,或插入写
int fseek(FILE *stream, long offset, int whence);
```

### 代码示例

代码示例详见code.


## java

## C sharp

## python

## shell



# 字符串操作

## C语言

## java

## C sharp

## python

## shell
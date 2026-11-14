# 文件基本操作

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 修订：理顺结构与定位，修正 C / Java / Python / shell 里的错误写法，补常见坑清单与延伸阅读 | 2026-11-14 |

文件操作看着是四门语言各自的 API，底下却是同一套机制：文件描述符、缓冲、原子性。
本文会把这三件事摊开说，再把 C、Java、C#、Python、shell、bat 的调用摆在一起对照——
重点不在「有哪些函数」，而在「哪些坑会让你以为写对了、其实没写对」。

## 文件系统

文件在操作系统里不是一串字节，而是「元数据 + 数据块」两样东西。以 ext2/ext3/ext4
这类文件系统为例，磁盘上主要有三样结构：

- **超级块（superblock）**：记录整个文件系统的总体情况。
- **inode**：记录一个文件或目录本身的属性——类型、权限、属主、大小、时间戳。
- **数据块（block）**：存放文件内容。

目录本身也是文件，它的内容是一串「名字 → inode 号」的条目。于是打开一个文件时，
查找链是：目录项查到 inode 号 → inode 查到数据块在哪 → 把块读上来。
下面四种语言的 API，都只是这条链上不同的一层封装。

```C
struct stat {
    dev_t st_dev; /* 设备   */
    ino_t st_ino; /* 节点   */
    mode_t st_mode; /* 模式   */
    nlink_t st_nlink; /* 硬连接 */
    uid_t st_uid; /* 用户ID */
    gid_t st_gid; /* 组ID   */
    dev_t st_rdev; /* 设备类型 */
    off_t st_size; /* 文件字节数 */
    blksize_t st_blksize; /* 文件系统 I/O 用的块大小 */
    blkcnt_t st_blocks; /* 已分配的块数，单位 512 字节 */
    time_t st_atime; /* 最后一次访问时间 */
    time_t st_mtime; /* 最后一次修改时间 */
    time_t st_ctime; /* 最后一次改变时间(指属性) */
};
```

`st_size` 和 `st_blocks` 不是一回事。`st_blocks` 的单位是 **512 字节**，
所以 `st_blocks × 512` 才是真正占掉的磁盘空间，它跟 `st_size` 可以差很多：

- 2 字节的文件也会占满一个块——实测 `st_size=2`、`st_blocks=8`，即 4096 字节。
- 有空洞（sparse）的文件反过来更小——实测 1 MiB 的稀疏文件 `st_blocks=0`。

查看文件属性：

```shell
#查看某个文件属性
ls -l
#查看文件结构体
stat filename
#查看文件各类属性
file filename
```

文件操作大致是这些：

* 读取文件
* 写入文件
* 重命名文件
* 读取目录
* 读取目录下的文件
* 创建目录
* 在创建目录下写入文件
* 不同文件格式之间进行转换

## 1 C语言

流程

打开文件 --> 读/写 --> （可选：fseek / fsetpos 定位）--> 关闭文件。

### 1.1 打开文件
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

### 1.2 关闭文件

```c
 int fclose( FILE *fp );
```
### 1.3 写入文件

```c
//把参数 c 的字符值写入到 fp 所指向的输出流中。如果写入成功，它会返回写入的字符，
//如果发生错误，则会返回 EOF
int fputc( int c, FILE *fp );
//把字符串 s 写入到 fp 所指向的输出流中。如果写入成功，它会返回一个非负值，
//如果发生错误，则会返回 EOF
int fputs( const char *s, FILE *fp );
//将格式化字符串写入到文件中
int fprintf(FILE *fp,const char *format, ...); 
```
### 1.4 读取文件

```c
//读取单个字符，返回值是读取的字符，如果发生错误则返回 EOF
int fgetc( FILE * fp );
//函数 fgets() 从 fp 所指向的输入流中读取 n - 1 个字符。它会把读取的字符串复制到缓冲区 buf，
//并在最后追加一个 null 字符来终止字符串。
char *fgets( char *buf, int n, FILE *fp );
//在遇到第一个空格字符时，会停止读取
int fscanf(FILE *fp, const char *format, ...);
```
### 1.5 二进制I/O函数

```c
//存储块的读写 - 通常是数组或结构体
size_t fread(void *ptr, size_t size_of_elements, 
             size_t number_of_elements, FILE *a_file);
              
size_t fwrite(const void *ptr, size_t size_of_elements, 
             size_t number_of_elements, FILE *a_file);
```
### 1.6 补充

```C
//fseek 可以移动文件指针到指定位置读,或插入写
int fseek(FILE *stream, long offset, int whence);
```
### 1.7 目录操作

```c
int mkdir(const char *pathname, mode_t mode);
//打开一个目录
DIR * opendir(const char* path);
//读取dir_handle目录下的目录项，如果有未读取的目录项，返回目录项，否则返回NULL。
struct dirent * readdir(DIR * dir_handle);
//关闭目录
int closedir(DIR * dir_handle);
```
### 1.8 删除文件

```c
//filename为要删除的文件名，可以为一目录。如果参数filename 为一文件，则调用unlink()处理；
//若参数filename 为一目录，则调用rmdir()来处理。
int remove(char * filename);
```

## 2 java

### 2.1 流

流是个抽象的概念，是对输入输出设备的抽象，Java程序中，对于数据的输入/输出操作都是以“流”的方式进行。设备可以是文件，网络，内存等。

流具有方向性，至于是输入流还是输出流则是一个相对的概念，一般以程序为参考，如果数据的流向是程序至设备，我们成为输出流，反之我们称为输入流。

使用流我们可以任意读取写入文件中的内容，而对于文件的操作来说，更多的是对文件的存储进行操作，创建文件到磁盘上，移动文件到指定位置上，更改文件的文件名等。这些操作更多的是和操作系统以及文件系统打交道。

### 2.2 流的分类

* 处理的数据单位不同，可分为：字符流，字节流
* 数据流方向不同，可分为：输入流，输出流

||字节流|字符流|
|:--:|:--:|:--:|
|输入流|InputStream|Reader|
|输出流|OutputStream|Writer|

1.继承自InputStream/OutputStream的流都是用于向程序中输入/输出数据，且数据的单位都是字节(byte=8bit).
2.继承自Reader/Writer的流都是用于向程序中输入/输出数据，且数据的单位都是字符(2byte=16bit)

* 功能不同，可分为：节点流，处理流

**节点流**：节点流从一个特定的数据源读写数据。即节点流是直接操作文件，网络等的流，例如FileInputStream和FileOutputStream，他们直接从文件中读取或往文件中写入字节流。

**处理流**：包装在另一个流之上，在包装里加能力——加缓冲、加编解码、加类型转换。
例如 `BufferedInputStream` 一次从底层流读 8192 字节填进自己的缓冲区，
之后程序每次 `read` 都从这块内存里取，直到缓冲空了才再读一次底层流；
于是逐字节读 8K 数据，`read(2)` 系统调用的次数从 8192 次降到 1 次。

### 2.3 常见流类介绍
**节点流类型常见的有**：

对文件操作的字符流有FileReader/FileWriter，字节流有FileInputStream/FileOutputStream。

**处理流类型常见的有**：

**缓冲流**：缓冲流要“套接”在相应的节点流之上，对读写的数据提供了缓冲的功能，同时增加了一些新的方法。字节缓冲流有BufferedInputStream/BufferedOutputStream，字符缓冲流有BufferedReader/BufferedWriter，字符缓冲流分别提供了读取和写入一行的方法 readLine() 和 newLine()。

**转换流**：用于字节数据到字符数据之间的转换。仅有字符流InputStreamReader/OutputStreamWriter。其中，InputStreamReader需要与InputStream“套接”，OutputStreamWriter需要与OutputStream“套接”

**数据流**：提供了读写Java中的基本数据类型的功能。DataInputStream和DataOutputStream分别继承自InputStream和OutputStream，需要“套接”在InputStream和OutputStream类型的节点流之上。

**对象流**：用于直接将对象写入写出。流类有ObjectInputStream和ObjectOutputStream，本身这两个方法没什么，但是其要写出的对象有要求，该对象必须实现Serializable接口，来声明其是可以序列化的。否则，不能用对象流读写。

**注**：关键字transient用于修饰实现了Serializable接口的类内的属性，被该修饰符修饰的属性，在以对象流的方式输出的时候，该字段会被忽略。

### 2.4 file类

一个File类对象可以存放的是目录，也可以是文件。

#### 2.4.1 File的构造方法

```java
//传入一个表示路径的字符串，可以是绝对路径也可以是相对路径
public File(String pathname)
//传入两个字符串,将其拼接为一个路径
public File(String parent, String child)
public File(File parent, String child)
```
#### 2.4.2 文件名和文件路径操作

`getName()` 返回路径的最后一段，`getPath()` 返回构造时拼进去的整条路径；
要拿规范化路径用 `getCanonicalPath()`——它会解析 `.`、`..`，并解析符号链接。

```java
//获取该文件对象的文件名（路径的最后一段）
public String getName()
//获取构造时传入的整条路径
public String getPath()
//判断是否绝对路径
public boolean isAbsolute()
//获取父目录路径
public String getParent()
public File getParentFile()
//获取绝对路径
public String getAbsolutePath()
public File getAbsoluteFile()
//获取规范化路径：解析 . 与 ..，并解析符号链接
public String getCanonicalPath()
public File getCanonicalFile()
```
#### 2.4.3 文件的信息

```java
//判断文件的信息
public boolean canRead()
public boolean canWrite()
public boolean exists()
public boolean isDirectory()
public boolean isFile()
public boolean isHidden()
public long lastModified()  //最后一次修改的时间
```
#### 2.4.4 操作文件

##### 2.4.4.1 创建文件
java中的File对象被创建出来之后，并不意味着在磁盘上已经创建了对应的文件，真正想要在磁盘上创建文件需要调用createNewFile方法。使用createNewFile创建文件成功返回true，失败返回false。如果文件已经存在则不创建，返回false。

两个容易踩的坑：

- `createNewFile()` 要求**父目录已经存在**，否则抛
  `IOException: No such file or directory`；
- `mkdir()` 只建**一层**，父目录不存在时返回 false，`mkdirs()` 才递归建。

所以顺序是先 `mkdirs()` 再 `createNewFile()`。

```java
//创建目录（递归建，父目录不存在时会一起建出来）
File f = new File("a");
f.mkdirs();
//创建文件（此时父目录 a 已经存在）
File d = new File("a/a.txt");
d.createNewFile();
```
##### 2.4.4.2 删除文件
文件的删除主要有两个方法。delete和deleteOnExit，前者会删除文件或者目录返回boolean，后者标记一下，等到虚拟机退出时候进行实际删除操作。需要注意的是如果将要删除的文件目录不为空就不能完成删除操作。

### 2.5 目录操作

#### 2.5.1 目录创建

```java
//创建单层目录（父目录不存在时返回 false）
public boolean mkdir()
//迭代创建多层目录
public boolean mkdirs()
```
#### 2.5.2 列出目录下的文件

```java
public String[] list()
public File[] listFiles()

public String[] list(FilenameFilter filter)
public File[] listFiles(FilenameFilter filter)
public File[] listFiles(FileFilter filter)
```
```java
File f = new File("f:/example");
String[] list = f.list();
for (String s : list){
    System.out.println(s);
}
```
## 3 C#

C#文件操作主要用到以下几个类，区别在于**面向文件还是面向目录**、以及**静态方法还是实例方法**：

| 类 | 面向 | 静态方法 / 实例方法 |
| --- | --- | --- |
| `File` | 文件 | 静态：直接吃路径字符串 |
| `FileInfo` | 文件 | 实例：先 new 出来，能缓存路径、便于链式调用 |
| `Directory` | 目录 | 静态：直接吃路径字符串 |
| `DirectoryInfo` | 目录 | 实例：先 new 出来，能缓存路径、便于链式调用 |

```C#
//创建文件夹
Directory.CreateDirectory(@"D:\example");
//创建文件
using (var w = new StreamWriter(@"D:\example\example.txt"))
{
    w.WriteLine("hello");
}
//删除文件
if (File.Exists(filePath))
{
     File.Delete(filePath);
}
//删除文件夹
Directory.Delete(dirPath); //删除空目录，否则需捕获指定异常处理
Directory.Delete(dirPath, true);//删除该目录以及其所有内容
//直接使用file类读取文件
public static string ReadAllText(string path);　
public static string[] ReadAllLines(string path);
public static IEnumerable<string> ReadLines(string path);
public static byte[] ReadAllBytes(string path);
//使用流读取文件

```

## 4 python

### 4.1 文件操作

#### 4.1.1 打开和关闭文件

用Python内置的open()函数打开一个文件，创建一个file对象，再用相关的方法才可以调用它进行读写。

```python
#file_name 变量是一个包含了你要访问的文件名称的字符串值
#access_mode 决定了打开文件的模式：只读，写入，追加等（默认为 'r' 只读）
#buffering：文本模式下 1 表示行缓冲（默认），大于 1 是缓冲区大小，负数用系统默认；
#           二进制模式下 0 表示不缓冲，文本模式下写 0 会报 ValueError
file_object = open(file_name, access_mode, buffering)
```

最该用的是 `with`：它保证异常时也会把文件关掉，不会漏句柄。

```python
with open(file_name, "r") as f:
    content = f.read()
```

#### 4.1.2 File对象的属性

一个文件打开后，其实就是创建了一个File对象，该对象保存了文件的具体信息，具体如下：

```python
fp=open("1.txt","wb")
```
|属性|描述|
|:--:|:--:|
|file.closed|关闭文件，成功返回true；刷新缓冲区里任何还没写入的信息，并关闭该文件|
|file.mode|返回被打开文件的访问模式|
|file.name|返回文件的名称|

#### 4.1.3 文件的读写操作

* __write()__

write()方法可将任何字符串写入一个打开的文件。

* __read()__

read() 方法读取文件**剩下的全部内容**；给了 size 才只读 size 个字符。

* __readline()__

f.readline() 会从文件中读取单独的一行。换行符为 '\n'。f.readline() 如果返回一个空字符串, 说明已经已经读取到最后一行。

* __readlines()__

f.readlines()将以列表的形式返回该文件中包含的所有行，列表中的一项表示文件的一行。如果设置可选参数 sizehint, 它是**读入字符总数的近似提示**——累计读到的字符数超过它就停，不是「读这么多字节」。

#### 4.1.4 文件的定位操作

tell()方法获取文件的当前位置；

seek（offset,from）方法改变当前文件的位置。Offset变量表示要移动的字节数，From变量指定开始移动字节的参考位置。如果from被设为0，这意味着将文件的开头作为移动字节的参考位置。如果设为1，则使用当前的位置作为参考位置。如果它被设为2，那么该文件的末尾将作为参考位置。

#### 4.1.5 文件的重命名和删除

* __rename()__

```python
#rename()方法需要两个参数，当前的文件名和新文件名。
os.rename(current_file_name, new_file_name)
```
* __remove()__

```python
os.remove(file_name)
```
### 4.2 python目录操作

* __mkdir()__

mkdir()创建新目录。

* __chdir()__

chdir()方法改变当前的目录。

* __getcwd()__

getcwd()获取当前目录。

* __rmdir()__

rmdir()方法删除目录，目录名称以参数传递。在删除这个目录之前，它的所有内容应该先被清除。

### 4.3 总结

|方法|是不是方法|说明|
|:--|:--:|:--|
|file.close()|是|关闭文件|
|file.flush()|是|刷新文件内部缓冲，直接将内部缓冲区的数据写入文件|
|file.fileno()|是|返回整型文件描述符|
|file.isatty()|是|文件是否连接到终端|
|file.read(size)|是|从文件读取指定字节数，若未给定或为负则读取所有|
|file.readline(size)|是|读取整行，包括“\n”字符|
|file.readlines(sizehint)|是|读取所有行并返回列表，sizehint 是总字符数的近似提示|
|file.seek(offset,whence)|是|设置文件当前位置|
|file.tell()|是|获取当前位置|
|file.truncate(size)|是|把文件**截断到** size 字节，与当前读写位置无关|
|file.write()|是|将字符串写入文件|
|file.writelines(sequence)|是|向文件写入一个序列字符串列表|

## 5 脚本

### 5.1 shell

* 创建文件、文件夹

```shell
touch filename
mkdir -m 741 dirname
```
* 删除文件、文件夹

```shell
#!/bin/bash
rm filename
rm -rf dirname
#删除一个目录下的所有文件夹
direc="$(pwd)"   #要删的目录，换成自己的路径
for dir2del in "$direc"/* ; do
if [ -d "$dir2del" ]; then
  rm -rf "$dir2del"
fi
done
```
* 判断文件是否存在

```shell
#!/bin/bash
filename=/home/along/shell/file
if [ -e "$filename" ]
then
    echo "$filename exited"
fi
```
* 判断文件是否为空

```shell
#!/bin/bash
filename=/home/along/shell/file
if [ ! -s "$filename" ]
then
    echo "$filename is null"
else
    echo "$filename is not null"
fi
```
* 遍历一个目录下的所有文件

```shell
#!/bin/bash
readpath="/home/along/shell"
for file in "$readpath"/*
do
    echo "$file"
done
```
### 5.2 bat

* 创建文件

```bat
::利用重定向>
echo "hello" >1.txt
```
* 创建目录

```bat
::MKDIR [drive:]path
::MD [drive]path
```
* 复制文件

```bat
::复制单个文件
copy 1.txt 2.txt
::复制文件夹文件
::xcopy 要复制的文件或目录树　目标地址目录名 复制文件和目录树
::用参数/Y将不提示覆盖相同文件
```
* 删除文件

```bat
::将直接删除d:\testa.bat，没有任务提示
del /s /q /f d:\testa.bat
::将直接删除 本目录的 temp 目录的所有文件，没有任务提示
::*表示通配符
del temp\* /q /f /s
```
* 删除文件夹

```bat
::删除空目录
rd /q /s d:\testlog
::删除非空目录
::必须指定目录名称，不能使用通配符
::/s 除当前目录外，还将删除指定目录下的所有子目录
::/q 安静模式，无任何提示信息
rmdir /q /s d:\testlogs
```

## 6 常见坑清单

1. **`fopen(..., "w")` 会截断**：文件已存在时长度直接归零，内容全丢。
   要追加用 `"a"`，要读写用 `"r+"`。
2. **`fclose` 不调用会丢数据**：stdio 有用户态缓冲。`exit()` 正常退出时会自动
   刷新，但崩溃或 `_exit()` 不会——缓冲区里的内容就丢了。
3. **`fgets` 会把行尾的换行符一起读进缓冲区**：它读的是「含 `\n` 的一整行」，
   要自己去掉。
4. **`createNewFile` 的父目录必须存在**：否则抛
   `IOException: No such file or directory`。
5. **`mkdir` vs `mkdirs`**：`mkdir` 只建一层，父目录不存在时返回 false 且不报错，
   `mkdirs` 才递归建。
6. **Python 不用 `with` 会漏句柄**：异常路径上文件不会被关闭，
   句柄泄漏到进程结束。默认用 `with open(...) as f:`。
7. **shell 里路径带空格要加引号**：`rm -rf $dir` 会被拆成多个参数，
   写成 `rm -rf "$dir"`。
8. **「写临时文件再 rename」是原子替换**：先把内容写进同目录下的临时文件，
   再 `rename` 覆盖目标。POSIX 保证 rename 是原子的，读者要么看到旧内容，
   要么看到新内容，不会看到写了一半的文件。

## 7 延伸阅读

- [PostgreSQL IO 调优](../pgsql/pg_io_调优.md)——本文讲的是「一次 read 到底做了什么」，
  那篇讲的是「数据库怎么把这件事做快」。
- [04 存储抽象层 SMGR](../db/postgresql/learning-path/04-storage-abstraction.md)——
  PG 怎么在 OS 文件系统之上加一层自己的存储抽象。
- [分布式存储需要解决的问题](../cluster/分布式存储需要解决的问题.md)——
  从单机文件走到多副本，要额外解决哪些问题。

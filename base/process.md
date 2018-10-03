<body bgcolor="khaki"></body><font color="black"></font>


# <center>进程</center>

## 1 基本概念

程序是指令的集合，而进程则是程序执行的基本单元。程序运行起来成为进程，进而利用处理器资源、内存资源，进行各种I/O操作，从而完成特定任务。

进程与线程，本质意义上说， 是操作系统的调度单位，可以看成是一种操作系统 “资源” 。

进程除了包含程序文件中的指令数据以外，还在内核中有一个数据结构用以存放特定进程的相关属性，以便内核更好地管理和调度进程，从而完成多进程协作的任务。

一个程序可能创建多个进程，通过多个进程的交互完成任务。在linux下，多进程的创建通常是通过fork系统调用来实现。

程序可以由多种不同程序语言描述，包括C语言程序、汇编语言程序和最后编译产生的机器指令。

## 2 java进程

在 JDK 中，与进程有直接关系的类为 Java.lang.Process，它是一个抽象类。在 JDK 中也提供了一个实现该抽象类的 ProcessImpl 类，如果用户创建了一个进程，那么肯定会伴随着一个新的 ProcessImpl 实例。

同时和进程创建密切相关的还有 ProcessBuilder。

### 2.1 创建进程

#### 2.1.1 ProcessBuilder.start()方法

Process类是一个抽象类，在它里面主要有几个抽象方法，如下

```java
public abstract class Process
{  
    abstract public OutputStream getOutputStream();   //获取进程的输出流  
    abstract public InputStream getInputStream();    //获取进程的输入流
    abstract public InputStream getErrorStream();   //获取进程的错误流
    abstract public int waitFor() throws InterruptedException;   //让进程等待
    abstract public int exitValue();   //获取进程的退出标志
    abstract public void destroy();   //摧毁进程
}
```
ProcessBuilder是一个final类，它有两个构造器,构造器中传递的是需要创建的进程的命令参数

* 第一个构造器是将命令参数放进List当中传进去
* 第二构造器是以不定长字符串的形式传进去。

```java
public final class ProcessBuilder
{
    private List<String> command;
    private File directory;
    private Map<String,String> environment;
    private boolean redirectErrorStream;
  
    public ProcessBuilder(List<String> command) {
    if (command == null)
        throw new NullPointerException();
    this.command = command;
    }
  
    public ProcessBuilder(String... command) {
    this.command = new ArrayList<String>(command.length);
    for (String arg : command)
        this.command.add(arg);
    }
....
}
```
ProcessBuilder.start 方法来建立一个本地的进程.如果希望在新创建的进程中使用当前的目录和环境变量，则不需要任何配置，直接将命令行和参数传入 ProcessBuilder 中，然后调用 start 方法，就可以获得进程的引用。

```java
Process p = new ProcessBuilder("command", "param").start();
```

也可以先配置环境变量和工作目录，然后创建进程。

```java
ProcessBuilder pb = new ProcessBuilder("command", "param1", "param2"); 
Map<String, String> env = pb.environment(); 
env.put("VAR", "Value"); 
pb.directory("Dir"); 
Process p = pb.start();
```
可以预先配置 ProcessBuilder 的属性是通过ProcessBuilder创建进程的最大优点。而且可以在后面的使用中随着需要去改变代码中pb变量的属性。如果后续代码修改了其属性，那么会影响到修改后用 start 方法创建的进程，对修改之前创建的进程实例没有影响。


#### 2.1.2 Runtime.exec()方法

```java
public class Runtime {
    private static Runtime currentRuntime = new Runtime();
  
    public static Runtime getRuntime() {
    return currentRuntime;
    }
  
    /** Don't let anyone else instantiate this class */
    private Runtime() {}
    ...
 }
public Process exec(String[] cmdarray, String[] envp, File dir)
   throws IOException {
   return new ProcessBuilder(cmdarray)
       .environment(envp)
       .directory(dir)
       .start();
}
Process exec(String command) 
Process exec(String [] cmdarray) 
Process exec(String [] cmdarrag, String [] envp) 
Process exec(String [] cmdarrag, String [] envp, File dir) 
Process exec(String cmd, String [] envp) 
Process exec(String command, String [] envp, File dir)
```
可以发现，事实上通过Runtime类的exec创建进程的话，最终还是通过ProcessBuilder类的start方法来创建的。

### 2.2 进程的实现

在 JDK 的代码中，只提供了 ProcessImpl 类来实现 Process 抽象类。其中引用了 native 的 create, close, waitfor, destory 和 exitValue 方法。

JDK中native方法和Windows API的对应关系

|native方法|Windows API|
|:--|:--|
|Creat|CreatProcess,CreatePipe|
|close|CloseHandle|
|waitfor|WaitForMultipleObjects|
|destory|TerminateProcess|
|exitValue|GetExitCodeProcess|

### 2.3 java进程和操作系统进程的关系

java进程在实现上就是创建了操作系统的一个进程，也就是每个JVM 中创建的进程都对应了操作系统中的一个进程。但是，Java为了给用户更好的更方便的使用，向用户屏蔽了一些与平台相关的信息。

在使用C/C++创建系统进程的时候，是可以获得进程的PID值的，可以直接通过该PID去操作相应进程。但是在 JAVA 中，用户只能通过实例的引用去进行操作，当该引用丢失或者无法取得的时候，就无法了解任何该进程的信息。

Java 进程在使用的时候还有些要注意的事情：

* Java 提供的输入输出的管道容量是十分有限的，如果不及时读取会导致进程挂起甚至引起死锁。
* 当创建进程去执行Windows下的系统命令时，如：dir、copy等。需要运行windows的命令解释器，command.exe/cmd.exe，这依赖于 windows 的版本，这样才可以运行系统的命令。
* 对于 Shell 中的管道‘ | ’命令，各平台下的重定向命令符‘>’，都无法通过命令参数直接传入进行实现，而需要在Java代码中做一些处理，如定义新的流来存储标准输出，等等问题。

### 2.4 线程

创建线程最重要的是提供线程函数（回调函数），该函数作为新创建线程的入口函数，实现自己想要的功能。Java 提供了两种方法来创建一个线程：

#### 2.4.1 继承Thread类

```java
class MyThread extends Thread{ 
    public void run() {    
        System.out.println("My thread is started."); 
    } 
    public static void main(String args[]) throws IOException{
        MyThread myThread = new MyThread(); 
        myThread.start();
    }  
}
```

#### 2.4.2 实现Runnable接口

```java
class MyRunnable implements Runnable{ 
    public void run() { 
        System.out.println("My runnable is invoked."); 
    } 
     public static void main(String args[]) throws IOException{
        MyThread myThread = new MyThread(new MyRunnable()); 
        myThread.start();
    }  ``
}
```

不管是用哪种方法，实际上都是要实现一个 run 方法的。 该方法本质是上一个回调方法。由start方法新创建的线程会调用这个方法从而执行需要的代码。run方法并不是真正的线程函数，只是被线程函数调用的一个Java方法而已，和其他的Java方法没有什么本质的不同。

从概念上来说，一个Java线程的创建根本上就对应了一个本地线程（native thread）的创建，两者是一一对应的。 问题是，本地线程执行的应该是本地代码，而Java线程提供的线程函数是Java方法，编译出的是Java字节码，所以可以想象的是，Java线程其实提供了一个统一的线程函数，该线程函数通过 Java 虚拟机调用 Java 线程方法 , 这是通过Java本地方法调用来实现的。

#### 2.4.3 Thread和Runnable的区别

如果一个类继承Thread，则不适合资源共享。但是如果实现了Runable接口的话，则很容易的实现资源共享。

实现Runnable接口比继承Thread类所具有的优势：

* 适合多个相同的程序代码的线程去处理同一个资源
* 可以避免java中的单继承的限制
* 增加程序的健壮性，代码可以被多个线程共享，代码和数据独立
* 线程池只能放入实现Runable或callable类线程，不能直接放入继承Thread的类

**注：**在java中，每次程序运行至少启动2个线程。一个是main线程，一个是垃圾收集线程。因为每当使用java命令执行一个类的时候，实际上都会启动一个JVM，每一个JVM就是在操作系统中启动了一个进程。

#### 2.4.4 线程状态

* **新建状态（New）：**新创建了一个线程对象。
* **就绪状态（Runnable）：**线程对象创建后，其他线程调用了该对象的start()方法。该状态的线程位于可运行线程池中，变得可运行，等待获取CPU的使用权。
* **运行状态（Running）：**就绪状态的线程获取了CPU，执行程序代码。
* **阻塞状态（Blocked）：**阻塞状态是线程因为某种原因放弃CPU使用权，暂时停止运行。直到线程进入就绪状态，才有机会转到运行状态。

阻塞状态分三种情况：

* **等待阻塞：**运行的线程执行wait()方法，JVM会把该线程放入等待池中。(wait会释放持有的锁)。
* **同步阻塞：**运行的线程在获取对象的同步锁时，若该同步锁被别的线程占用，则JVM会把该线程放入锁池中。
* **其他阻塞：**运行的线程执行sleep()或join()方法，或者发出了I/O请求时，JVM会把该线程置为阻塞状态。当sleep()状态超时、join()等待线程终止或者超时、或者I/O处理完毕时，线程重新转入就绪状态。（注意,sleep是不会释放持有的锁）。

#### 2.4.5 线程调度

##### 2.4.5.1 调整线程优先级

Java线程有优先级，优先级高的线程会获得较多的运行机会。Java线程的优先级用整数表示，取值范围是1~10，Thread类有以下三个静态常量：

```java
//线程可以具有的最高优先级，取值为10
static int MAX_PRIORITY
//线程可以具有的最高优先级，取值为1
static int MIN_PRIORITY
//线程可以具有的默认优先级，取值为5
static int NORM_PRIORITY
```
Thread类的setPriority()和getPriority()方法分别用来设置和获取线程的优先级。

每个线程都有默认的优先级。主线程的默认优先级为Thread.NORM_PRIORITY。

线程的优先级有继承关系，比如A线程中创建了B线程，那么B将和A具有相同的优先级。

##### 2.4.5.2 线程睡眠

Thread.sleep(long millis)方法，使线程转到阻塞状态。millis参数设定睡眠的时间，以毫秒为单位。当睡眠结束后，就转为就绪（Runnable）状态。sleep()平台移植性好。

##### 2.4.5.3 线程等待

Object类中的wait()方法，导致当前的线程等待，直到其他线程调用此对象的 notify() 方法或 notifyAll() 唤醒方法。这个两个唤醒方法也是Object类中的方法，行为等价于调用 wait(0) 一样。

##### 2.4.5.4 线程让步

Thread.yield()方法，暂停当前正在执行的线程对象，把执行机会让给相同或者更高优先级的线程。

##### 2.4.5.5 线程加入

join()方法，等待其他线程终止。在当前线程中调用另一个线程的join()方法，则当前线程转入阻塞状态，直到另一个进程运行结束，当前线程再由阻塞转为就绪状态。

##### 2.4.5.6 线程唤醒

Object类中的notify()方法，唤醒在此对象监视器上等待的单个线程。如果所有线程都在此对象上等待，则会选择唤醒其中一个线程。选择是任意性的，并在对实现做出决定时发生。线程通过调用其中一个 wait 方法，在对象的监视器上等待。 直到当前的线程放弃此对象上的锁定，才能继续执行被唤醒的线程。被唤醒的线程将以常规方式与在该对象上主动同步的其他所有线程进行竞争。

### 2.5 常用函数

* **sleep(long millis):** 在指定的毫秒数内让当前正在执行的线程休眠（暂停执行）
* **join():**等待线程终止

join是Thread类的一个方法，启动线程后直接调用，即join()的作用是：“等待该线程终止”，这里是指主线程等待子线程的终止。也就是在join()方法后面的代码，只有等到子线程结束了才能执行。

在很多情况下，主线程生成并起动了子线程，如果子线程里要进行大量的耗时的运算，主线程往往将于子线程之前结束，但是如果主线程处理完其他的事务后，需要用到子线程的处理结果，也就是主线程需要等待子线程执行完成之后再结束，这个时候就要用到join()方法了。

* **yield():**暂停当前正在执行的线程对象，并执行其他线程

yield()应该做的是让当前运行线程回到可运行状态，以允许具有相同优先级的其他线程获得运行机会。因此，使用yield()的目的是让相同优先级的线程之间能适当的轮转执行。但是，实际中无法保证yield()达到让步目的，因为让步的线程还有可能被线程调度程序再次选中。

* **interrupt():**向线程发送一个中断信号，让线程在无限等待时（如死锁时）能抛出，从而结束线程，但是如果你吃掉了这个异常，那么这个线程不会中断
* **wait()**

Obj.wait()，Obj.notify()必须要与synchronized(Obj)一起使用，也就是wait,notify是对已经获取了锁的Obj进行操作。从语法角度来说就是Obj.wait(),Obj.notify必须在synchronized(Obj){...}语句块内。从功能上来说wait是线程在获取对象锁后，主动释放对象锁，同时本线程休眠。直到有其它线程调用对象的notify()唤醒该线程，才能继续获取对象锁，并继续执行。相应的notify()就是对对象锁的唤醒操作。但有一点需要注意的是notify()调用后，并不是马上就释放对象锁的，而是在相应的synchronized(){}语句块执行结束，自动释放锁后，JVM会在wait()对象锁的线程中随机选取一线程，赋予其对象锁，唤醒线程，继续执行。这样就提供了在线程间同步、唤醒的操作。Thread.sleep()与Object.wait()二者都可以暂停当前线程，释放CPU控制权，主要的区别在于Object.wait()在释放CPU同时，释放了对象锁的控制。

### 2.6 线程同步

线程同步控制，即使用某种方式使得一个线程在操作完某个数据前，别的线程无法操作这个数据，从而避免多个线程同时操作一个数据，进而避免线程安全问题，线程同步控制的方式有同步锁机制、等待/通知机制、信号量机制等。

#### 2.6.1 synchronize同步锁机制

Java中每个对象都有一把锁，同一时刻只能有一个线程持有这把锁。线程可以使用synchronized关键字向系统申请某个对象的锁，得到锁之后，别的线程再申请该锁时，就只能等待。持有锁的线程在这次操作完成后，可以释放锁，以便其他线程可以获得锁。

* synchronized代码块
* synchronized方法

非静态同步方法申请的锁是类的当前对象的锁，静态同步方法申请的锁是类的Class对象的锁。同步方法执行完后即向系统归还锁。所有需要同步的线程必须都申请同一个对象的锁，当申请不同的锁或者有的线程没有使用synchronized时，同步锁机制就会失效。

#### 2.6.2 wait()/notify()等待通知机制

对于稍复杂的情况，比如多个线程需要相互合作有规律的访问共享数据，就可以使用wait/notify机制，即等待/通知机制，也称等待/唤醒机制。

等待/通知机制建立在synchronized同步锁机制的基础上，即在同步代码块（或同步方法）内，如果当前线程执行了lockObject.wait()（lockObject表示提供锁的对象），则当前线程立即暂停执行，并被放入阻塞队列，并向系统归还所持有的锁，并在lockObject上等待，直到别的线程调用lockObject.notify()。

如果有多个线程在同一个对象上等待，notify()方法只会随机通知一个等待的线程，也可以使用notifyAll()方法通知所有等待的线程。被通知的线程获得锁后会进入就绪队列。

## 3 C sharp进程

## 4 python进程

## 5 shell进程

### 5.1 进程的创建

通常在命令行键入某个程序文件名后，一个进程就被创建了。

### 5.2 进程的基本操作

#### 5.2.1 查看进程的运行信息

```shell
# 用pidof查看指定程序名的进程ID
pidof mysqld
#查看进程的内存映像
cat /proc/pid/maps
#查看系统当前所有进程的属性
ps -ef
#查看命令中包含某字符的程序对应的进程
ps -ef |grep init*
#查看特定用户启动的进程
ps -U user
#输出命令名和cpu使用率
ps -e -o "%C %c"
#通过pstree查看进程亲缘关系
pstree
#动态查看进程信息
top
#查看特定用户的进程信息
top -u user
```
#### 5.2.2 调整进程的优先级

```shell
#获取进程优先级
ps -e -o "%p %c %n" |grep vmtools*
#调整进程优先级
sudo renice 1 -p pid
```
#### 5.2.3 结束进程

```shell
#获取进程优先级
sudo kill pid
#列出可以向进程发送的信号
kill -l
#kill命令发送SIGSTOP信号给某个程序让其停止，SIGCONT继续执行
kill -s SIGSTOP pid
kill -s SIGCONT pid
#查看作业情况
jobs
#kill只能通过pid或者jobs id来控制进程
#pkill和killall扩展了通过程序名或进程的用户名来控制进程
```
#### 5.2.4 进程退出状态

在 Shell 中，可以检查这个特殊的变量 $?，它存放了上一条命令执行后的退出状态。一般情况下，返回0表示正常结束，返回非0值表示出现异常。

```shell
#查看程序结束状态
echo $?
```

#### 5.2.5 进程通信

##### 5.2.5.1 无名管道

在 Linux 下，可以通过 | 连接两个程序，这样就可以用它来连接后一个程序的输入和前一个程序的输出，因此被形象地叫做个管道。在 C 语言中，创建无名管道非常简单方便，用 pipe 函数，传入一个具有两个元素的 int 型的数组就可以。这个数组实际上保存的是两个文件描述符，父进程往第一个文件描述符里头写入东西后，子进程可以从第一个文件描述符中读出来。

```shell
#将ps的输出作为grep命令的输入
ps -ef | grep init*
```
当输入这样一组命令时，当前 Shell 会进行适当的解析，把前面一个进程的输出关联到管道的输出文件描述符，把后面一个进程的输入关联到管道的输入文件描述符，这个关联过程通过输入输出重定向函数 dup （或者 fcntl ）来实现。

##### 5.2.5.2 有名管道

有名管道实际上是一个文件（无名管道也像一个文件，虽然关系到两个文件描述符，不过只能一边读另外一边写），不过这个文件比较特别，操作时要满足先进先出，而且，如果试图读一个没有内容的有名管道，那么就会被阻塞，同样地，如果试图往一个有名管道里写东西，而当前没有程序试图读它，也会被阻塞。

```shell
#创建有名管道
mkfifo fifo_test
#往有名管道写入内容
echo "hello">fifo_test
#此时的终端被堵塞，需要另开一个终端来读取管道内容
cat fifo_test
#让管道在后台运行,无需另开终端
#echo 和 cat 是两个不同的程序，在这种情况下，通过 echo 和 cat 
#启动的两个进程之间并没有父子关系。不过它们依然可以通过有名管道通信。
echo "hello">fifo_test &
cat fifo_test
```
#### 5.2.5.3 信号（Signal）

信号是软件中断，Linux 用户可以通过 kill 命令给某个进程发送一个特定的信号，也可以通过键盘发送一些信号，比如 CTRL+C 可能触发 SGIINT 信号，而 CTRL+\ 可能触发 SGIQUIT 信号等，除此之外，内核在某些情况下也会给进程发送信号，比如在访问内存越界时产生 SGISEGV 信号，当然，进程本身也可以通过 kill，raise 等函数给自己发送信号。

对于有些信号，进程会有默认的响应动作，而有些信号，进程可能直接会忽略，当然，用户还可以对某些信号设定专门的处理函数。在 Shell 中，可以通过 trap 命令（Shell 内置命令）来设定响应某个信号的动作（某个命令或者定义的某个函数），而在 C 语言中可以通过 signal 调用注册某个信号的处理函数。

```shell
#定义signal_handler函数,空格不能少
function signal_handler { echo "hello, world."; } 
#执行该命令设定：收到SIGINT信号时打印hello, world
trap signal_handler SIGINT 
#按下CTRL+C，可以看到屏幕上输出了hello, world字符串
```
```shell
#!/bin/bash
function signal_handler {
    #实际Shell编程会用该方式在程序退出时来做一些清理临时文件的收尾工作
    echo "hello, world"
}
trap signal_handler 0
```

#### 5.2.5.4 作业和作业控制

当我们为完成一些复杂的任务而将多个命令通过 |,\>,< 等组合在一起时，通常这个命令序列会启动多个进程，它们间通过管道等进行通信。而有时在执行一个任务的同时，还有其他的任务需要处理，那么就经常会在命令序列的最后加上一个&，或者在执行命令后，按下 CTRL+Z 让前一个命令暂停。以便做其他的任务。等做完其他一些任务以后，再通过 fg 命令把后台任务切换到前台。这样一种控制过程通常被称为作业控制，而那些命令序列则被成为作业，这个作业可能涉及一个或者多个程序，一个或者多个进程。

```shell
#创建后台进程
sleep 20 &
##把作业调到前台并暂停
fg %1
^Z
#查看当前作业情况
jobs
#启动停止的进程并在后台运行
bg %1
```




# 进程

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
    }
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

**新建状态（New）：**新创建了一个线程对象。

**就绪状态（Runnable）：**线程对象创建后，其他线程调用了该对象的start()方法。该状态的线程位于可运行线程池中，变得可运行，等待获取CPU的使用权。

**运行状态（Running）：**就绪状态的线程获取了CPU，执行程序代码。

**阻塞状态（Blocked）：**阻塞状态是线程因为某种原因放弃CPU使用权，暂时停止运行。直到线程进入就绪状态，才有机会转到运行状态。

阻塞状态分三种情况：

**等待阻塞：**运行的线程执行wait()方法，JVM会把该线程放入等待池中。(wait会释放持有的锁)。

**同步阻塞：**运行的线程在获取对象的同步锁时，若该同步锁被别的线程占用，则JVM会把该线程放入锁池中。

**其他阻塞：**运行的线程执行sleep()或join()方法，或者发出了I/O请求时，JVM会把该线程置为阻塞状态。当sleep()状态超时、join()等待线程终止或者超时、或者I/O处理完毕时，线程重新转入就绪状态。（注意,sleep是不会释放持有的锁）。

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

**sleep(long millis):** 在指定的毫秒数内让当前正在执行的线程休眠（暂停执行）

**join():**等待线程终止

join是Thread类的一个方法，启动线程后直接调用，即join()的作用是：“等待该线程终止”，这里是指主线程等待子线程的终止。也就是在join()方法后面的代码，只有等到子线程结束了才能执行。

在很多情况下，主线程生成并起动了子线程，如果子线程里要进行大量的耗时的运算，主线程往往将于子线程之前结束，但是如果主线程处理完其他的事务后，需要用到子线程的处理结果，也就是主线程需要等待子线程执行完成之后再结束，这个时候就要用到join()方法了。

**yield():**暂停当前正在执行的线程对象，并执行其他线程

yield()应该做的是让当前运行线程回到可运行状态，以允许具有相同优先级的其他线程获得运行机会。因此，使用yield()的目的是让相同优先级的线程之间能适当的轮转执行。但是，实际中无法保证yield()达到让步目的，因为让步的线程还有可能被线程调度程序再次选中。

**interrupt():**向线程发送一个中断信号，让线程在无限等待时（如死锁时）能抛出，从而结束线程，但是如果你吃掉了这个异常，那么这个线程不会中断

**wait()**

`Obj.wait()，Obj.notify()`必须要与`synchronized(Obj)`一起使用，也就是wait,notify是对已经获取了锁的Obj进行操作。从语法角度来说就是`Obj.wait(),Obj.notify`必须在`synchronized(Obj){...}`语句块内。从功能上来说wait是线程在获取对象锁后，主动释放对象锁，同时本线程休眠。直到有其它线程调用对象的notify()唤醒该线程，才能继续获取对象锁，并继续执行。相应的notify()就是对对象锁的唤醒操作。但有一点需要注意的是`notify()`调用后，并不是马上就释放对象锁的，而是在相应的synchronized(){}语句块执行结束，自动释放锁后，JVM会在`wait()`对象锁的线程中随机选取一线程，赋予其对象锁，唤醒线程，继续执行。这样就提供了在线程间同步、唤醒的操作。`Thread.sleep()`与`Object.wait()`二者都可以暂停当前线程，释放CPU控制权，主要的区别在于`Object.wait()`在释放CPU同时，释放了对象锁的控制。

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

### 3.1 使用线程的理由

* 可以使用线程将代码同其他代码隔离，提高应用程序的可靠性。
* 可以使用线程来简化编码。
* 可以使用线程来实现并发执行。

### 3.2 基本知识

**进程：**进程作为操作系统执行程序的基本单位，拥有应用程序的资源，进程包含线程，进程的资源被线程共享，线程不拥有资源。进程是一个运行程序。进程是一个操作系统级别的概念，用来描述一组资源（比如外部代码库和主线程）和程序运行必须的内存分配。对于每一个加载到内存的*.exe，在它的生命周期中操作系统会为之创建一个单独且隔离的进程。

**线程：**线程是进程中的基本执行单元。每一个Windows进程都包含一个用作程序入口点的主线程。进程的入口点创建的第一个线程被称为主线程。.Net控制台程序使用Main()方法作为程序入口点。当调用该方法时，会自动创建主线程。仅包含一个主线程的进程是线程安全的，这是由于在某个特定时刻只有一个线程访问程序中的数据。然而，**如果这个线程正在执行一个复杂的操作，那么这个线程所在的进程（特别是GUI程序）对用户来说会显得没有响应一样。**因此，主线程可以产生次线程（也称为工作者线程，worker thread）。每一个线程（无论主线程还是次线程）都是进程中的一个独立执行单元，它们能够同时访问那些共享数据。**可以使用多线程改善程序的总体响应性，让人感觉大量的活动几乎在同一时间发送。**

**如果单个进程中的线程过多的话，性能反而会下降，因为CPU需要花费不少时间在这些活动的线程来回切换。**

**.NET应用程序域：**.Net可执行程序承载在进程的一个逻辑分区中，称为应用程序域（AppDomain）。一个进程可以包含多个应用程序域，每一个应用程序域中承载一个.Net可执行程序。如果不使用分布式编程协议（如WCF），运行在某个应用程序域中的应用程序将无法访问其它应用程序域中的任何数据（无论是全局变量还是静态变量）。

**对象上下文：**应用程序域是承载.Net程序集的进程的逻辑分区。应用程序域也可以进一步被划分成多个上下文边界。即，.Net上下文为单独的应用程序域提供了一种方式，该方式能为一个给定对象建立“特定的家”。和一个进程定义了默认的应用程序域一样，每个应用程序域都有一个默认的上下文。

**前台线程和后台线程：**通过Thread类新建线程默认为前台线程。当所有前台线程关闭时，所有的后台线程也会被直接终止，不会抛出异常。

**挂起（Suspend）和唤醒（Resume）：**由于线程的执行顺序和程序的执行情况不可预知，所以使用挂起和唤醒容易发生死锁的情况，在实际应用中应该尽量少用。

**阻塞线程:**Join，阻塞调用线程，直到该线程终止。

**终止线程:**Abort抛出ThreadAbortException异常让线程终止，终止后的线程不可唤醒。Interrupt抛出 ThreadInterruptException 异常让线程终止，通过捕获异常可以继续执行。

**线程优先级：**AboveNormal BelowNormal Highest Lowest Normal，默认为Normal。

### 3.3 线程的创建

#### 3.3.1 使用ThreadStart委托创建线程

线程函数通过委托传递，可以不带参数，也可以带参数（只能有一个参数），可以用一个类或结构体封装参数。

```C#
Thread t1 = new Thread(new ThreadStart(function));
t1.IsBackground = true;
t1.Start();
```

Thred类支持设置Name属性。如果没有设置这个值的话，Name将返回一个空字符串。如果需要用vs调试的话，可以为线程设置一个友好的Name，方便debug。

Thred类定义了一个名为Priority的属性，默认情况下，所有线程的优先级都处于Normal级别。但是，在线程生命周期的任何时候，都可以使用ThredPriority属性修改线程的优先级。

如果给线程的优先级指定一个非默认值，这并不能控制线程调度器切换线程的过程。实际上，一个线程的优先级仅仅是把线程活动的重要程度提供给CLR。因此，一个带有Highest优先级的线程并不一定保证能得到最高的优先级。 

#### 3.3.2 使用ParameterizedThreadStart委托创建线程，传递数据

ThreadStart委托仅仅支持指向无返回值、无参数的方法。如果想把数据传递给在次线程上执行的方法，则需要使用ParameterizedThreadStart委托类型。

```C#
Thread t2 = new Thread(new ParameterizedThreadStart(function));
t2.IsBackground = true;
t2.Start("hello");
```

#### 3.3.3 使用AutoResetEvent类强制线程等待，直到其他线程结束

```C#
private static AutoResetEvent waitHandle = new AutoResetEvent(false);
Thread t = new Thread(new ParameterizedThreadStart(Add));
t.Start(ap);
//Wait here until you are notified         
waitHandle.WaitOne();
```

### 3.4 前台线程和后台线程的区别

前台线程能阻止应用程序的终结。一直到所有的前台线程终止后，CLR才能关闭应用程序（即卸载承载的应用程序域）。后台线程被CLR认为是程序执行中可做出牺牲的线程，即在任何时候（即使这个线程此时正在执行某项工作）都可能被忽略。因此，如果所有的前台线程终止，当应用程序卸载时，所有的后台线程也会被自动终止。 

前台线程和后台线程并不等同于主线程和工作者线程。默认情况下，所有通过Thread.Start()方法创建的线程都自动成为前台线程。可以通过修改线程的IsBackground属性将前台线程配置为后台线程。

**多数情况下，当程序的主任务完成，而工作者线程正在执行无关紧要的任务时，把工作线程配置成后台类型时很有用的。**

### 3.5 线程并发

在构建多线程应用程序时，需要确保任何共享数据都需要处于被保护状态，以防止多个线程修改它的值。由于一个应用程序域中的所有线程都能够并发访问共享数据，所以，想象一下当它们正在访问其中的某个数据项时，由于线程调度器会随机挂起线程，所以如果线程A在完成之前被挂起了，线程B读到的就是一个不稳定的数据。

#### 3.5.1 使用lock关键字进行同步

同步访问共享资源的首先技术是C#的lock关键字。这个关键字允许定义一段线程同步的代码语句。采用这项技术，后进入的线程不会中断当前线程，而是停止自身下一步执行。lcok关键字需要定义一个标记（即一个对象引用），线程进入锁定范围的时候必须获得这个标记。当试图锁定的是一个实例级对象的私有方法时，使用方法本身所在对象的引用就可以。

```C#
//使用当前对象作为线程标记
private void Do()
{
     lock (this)
    {
        //所有在这个范围内的代码是线程安全的
    }
}
```

#### 3.5.2 使用Interlocked类型进行同步

.Net中并不是所有赋值和数值运算都是原子型操作。Interlocked允许我们原子型操作单个数据。

|成员|作用|
|:--|:--|
|CompareExchange|安全地比较两个值是否相等。如果相等，则替换其中一个值。|
|Decrement|以原子操作的形式递减指定变量的值并存储结果。|
|Exchange|以原子操作的形式，将对象设置为指定的值并返回对原始对象的引用。|
|Increment|以原子操作的形式递增指定变量的值并存储结果。|

### 3.6 线程池

由于线程的创建和销毁需要耗费一定的开销，过多的使用线程会造成内存资源的浪费，出于对性能的考虑，于是引入了线程池的概念。线程池维护一个请求队列，线程池的代码从队列提取任务，然后委派给线程池的一个线程执行，线程执行完不会被立即销毁，这样既可以在后台执行任务，又可以减少线程创建和销毁所带来的开销。

线程池线程默认为后台线程（IsBackground）。

```C#
namespace Test
{
    class Program
    {
        static void Main(string[] args)
        {
            //将工作项加入到线程池队列中，这里可以传递一个线程参数
            ThreadPool.QueueUserWorkItem(TestMethod, "Hello");
            Console.ReadKey();
        }

        public static void TestMethod(object data)
        {
            string datastr = data as string;
            Console.WriteLine(datastr);
        }
    }
}
```

### 3.7 Task类

使用ThreadPool的QueueUserWorkItem()方法发起一次异步的线程执行很简单，但是该方法最大的问题是没有一个内建的机制让你知道操作什么时候完成，有没有一个内建的机制在操作完成后获得一个返回值。为此，可以使用System.Threading.Tasks中的Task类。

构造一个`Task<TResult>`对象，并为泛型TResult参数传递一个操作的返回类型。

```C#
namespace Test
{
    class Program
    {
        static void Main(string[] args)
        {
            Task<Int32> t = new Task<Int32>(n => Sum((Int32)n), 1000);
            t.Start();
            t.Wait();
            Console.WriteLine(t.Result);
            Console.ReadKey();
        }

        private static Int32 Sum(Int32 n)
        {
            Int32 sum = 0;
            for (; n > 0; --n)
                checked{ sum += n;} //结果太大，抛出异常
            return sum;
        }
    }
}
```

#### 3.8 委托异步执行

委托的异步调用：BeginInvoke() 和 EndInvoke()。


## 4 python多线程

Python中使用线程有两种方式：函数或者用类来包装线程对象。

### 4.1 线程创建

启动一个线程就是把一个函数传入并创建Thread实例，然后调用start()开始执行：

```python
import time, threading

def loop():
    print('thread %s is running...' % threading.current_thread().name)
    n = 0
    while n < 5:
        n = n + 1
        print('thread %s >>> %s' % (threading.current_thread().name, n))
        time.sleep(1)
    print('thread %s ended.' % threading.current_thread().name)

print('thread %s is running...' % threading.current_thread().name)
t = threading.Thread(target=loop, name='LoopThread')
t.start()
t.join()
print('thread %s ended.' % threading.current_thread().name)
```
由于任何进程默认就会启动一个线程，我们把该线程称为主线程，主线程又可以启动新的线程，Python的threading模块有个current_thread()函数，它永远返回当前线程的实例。主线程实例的名字叫MainThread，子线程的名字在创建时指定，我们用LoopThread命名子线程。名字仅仅在打印时用来显示，完全没有其他意义，如果不起名字Python就自动给线程命名为Thread-1，Thread-2……

多线程和多进程最大的不同在于，多进程中，同一个变量，各自有一份拷贝存在于每个进程中，互不影响，而多线程中，所有变量都由所有线程共享，所以，任何一个变量都可以被任何一个线程修改，因此，线程之间共享数据最大的危险在于多个线程同时改一个变量，把内容给改乱了。

使用锁可以保证线程安全，创建一个锁就是通过threading.Lock()来实现。

```python
lock = threading.Lock()
lock.acquire()
lock.release()
```
当多个线程同时执行lock.acquire()时，只有一个线程能成功地获取锁，然后继续执行代码，其他线程就继续等待直到获得锁为止。

获得锁的线程用完后一定要释放锁，否则那些苦苦等待锁的线程将永远等待下去，成为死线程。可以用try...finally来确保锁一定会被释放。

锁的好处就是确保了某段关键代码只能由一个线程从头到尾完整地执行，坏处当然也很多，首先是阻止了多线程并发执行，包含锁的某段代码实际上只能以单线程模式执行，效率就大大地下降了。其次，由于可以存在多个锁，不同的线程持有不同的锁，并试图获取对方持有的锁时，可能会造成死锁，导致多个线程全部挂起，既不能执行，也无法结束，只能靠操作系统强制终止。

## 4.2 线程状态

创建线程之后，线程并不是始终保持一个状态。其状态大概如下：

* New 创建
* Runnable 就绪，等待调度
* Running 运行
* Blocked 阻塞，阻塞可能在 Wait Locked Sleeping
* Dead 消亡




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

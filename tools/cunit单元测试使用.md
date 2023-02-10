# cunit单元测试使用

## 下载安装

```shell
wget https://gigenet.dl.sourceforge.net/project/cunit/CUnit/2.1-3/CUnit-2.1-3.tar.bz2
cd CUnit-2.1-3
./bootstrap
./cobnfigure
make -j 8
make install
```

## 使用

cunit安装测试注册表，测试套，测试用例三个层级来管理单元测试。一般来说，一个项目对应一个测试注册表，一个测试套对应一个c文件，一个测试用例对应一个测试函数。当然一个c函数可能会有多个测试用例。

```shell
                  Test Registry
                        |
         ------------------------------
         |                            |
      Suite '1'      . . . .       Suite 'N'
         |                            |
   ---------------             ---------------
   |             |             |             |
Test '11' ... Test '1M'     Test 'N1' ... Test 'NM'

```

各个测试注册到套件（Suite）中，并在活动的测试注册表中注册。套件可以具有设置（setup）和拆卸（teardown）功能，可以在运行套件的测试之前和结束之后自动调用它们。注册表中的所有套件/测试都可以使用单个函数调用来运行，或者也可以运行选定的套件或测试。

使用CUnit框架的典型步骤序列为：

1. 编写测试功能方法(并在必要时进行套件(Suite)初始化/清除)
2. 初始化测试注册表:`CU_initialize_registry()`
3. 将套件添加到测试注册表:`CU_add_suite()`,可以调用多次添加多个测试套件
4. 将测试添加到套件:`CU_add_test()`，每个测试套件都可以调用多次添加多个测试
5. 使用适当的界面运行测试，例如:`CU_console_run_tests`或者`CU_automated_run_tests`
6. 清理测试注册表:`CU_cleanup_registry`

## 运行单元测试

CUnit支持在所有注册的套件中运行所有测试，但是也可以运行单个测试或套件。在每次运行期间，框架都会跟踪运行，通过和失败的套件，测试和断言的数量。请注意，每次启动测试运行时都会清除结果（即使失败）。
尽管CUnit为运行套件和测试提供了原始功能，但大多数用户将希望使用简化的用户界面之一。这些界面处理与框架交互的详细信息，并为用户提供测试详细信息和结果的输出。

cunit支持四种测试模式：

| 测试模式  | 平台       | 描述                              |
| --------- | ---------- | --------------------------------- |
| Automated | all        | 非交互模式，测试报告输出到XML文件 |
| Basic     | all        | 非交互模式，测试报告输出stdout    |
| Console   | all        | 控制台下的交互模式                |
| Curses    | Linux/Unix | curses的交互模式                  |

# reference

1. https://blog.csdn.net/iuices/article/details/115280751
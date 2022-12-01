# linux下svn吐血指北

<font color ="red">如非必要，请用git！如非必要，请用git！如非必要，请用git！</font>

## 安装

```shell
apt install svn
```

## 配置

设置默认编辑器为vim

```shell
echo "export SVN_EDITOR=vim" >> /etc/profile
source /etc/profile
```

## 命令

- 拉取仓库

```shell
svn checkout path
```

- 添加文件

```shell
svn add filename
```

<font color="red">注意：svn的文件只允许提交依次。当你第一次提交后，后面修改了直接commit。</font>

- 提交文件

```
# 默认会提交所有修改的文件
svn commit
# 指定要提交哪个文件
svn commit filename
```

- 查看当前文件状态

```shell
svn status
# 查看目录下文件是否修改
svn status path
# 列出目录下文件的状态
svn status -v path
```

- 查看修改记录

```shell
# 查看所有提交记录
svn log
# 查看单个文件提交记录
svn log filename
```

- 查看文件信息

```shell
svn info filename
```

- 更新到某个版本

```shell
svn update -r m path
```

- 版本回退

```shell
# 回退文件到与远程仓库一致，撤销本次修改
svn revert filename
# 回退整个目录
svn revert -R dir
# 恢复一个已经提交的版本，找到仓库的当前版本，现在是版本 22，我们要撤销回之前的版本，比如版本 21
svn merge -r 22:21 readme
```

>**一、改动还没被提交的情况（未commit）**
>
>这种情况下，见有的人的做法是删除work copy中文件，然后重新update，恩，这种做法达到了目的，但不优雅，因为这种事没必要麻烦服务端。
>
>其实一个命令就可以搞定：
>
>```
># svn revert [-R] PATH
>```
>
>PATH可以是准备回滚的文件、目录，如果想把某个目录下的所有文件包括子目录都回滚，加上-R选项。
>
>**二、改动已经提交（已commit）**
>
>1.首先取得当前最新版本，不是最新的有可能带来麻烦：
>
>```shell
>svn update
>```
>
>假设当前版本是2582. 
>
> 2.找到要回滚到的版本号，如果不清楚，查看log，diff
>
>```shell
>svn log | more
>svn diff -r version1:version2 PATH
>```
>
>假设回滚到版本2580.
>
>3.merge 
>
> ```shell
>svn merge -r 2582:2580 PATH
>```
>
>merge完使用diff确认结果 
>
> ```shell
>svn diff PATH
>```
>
>4.提交 
>
> ```shell
>svn ci PATH -m "Revert version from xxx to xxx because..."
>```
>
>因为又一次提交，版本号又升了一个，现在变成了2583.
>
> 见有的人是这么做回滚的，就是逐个修改代码，然后再提交，如果改动很多的话难免有所遗漏，非常不推荐。
>
>如果在这期间，其他人提交了很多代码，如何保留别人的劳动成果，只把自己的错误剔掉，不太容易。
>
> <font color="red">转载自Start-up的[博客](https://my.oschina.net/qihh/blog/55810?p=1)。</font>

# reference

1. https://www.runoob.com/svn/svn-revert.html
2. https://my.oschina.net/qihh/blog/55810?p=1


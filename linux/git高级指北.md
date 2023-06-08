# git 高级指北

## 解决分支与分支之间的碰撞

- 合并分支

```shell
# 直接将branch2硬合到branch1，有冲突再解决冲突
git checkout branch1
git merge branch2
```

- 合并分支的某个文件

```shell
# 只将branch2的test.c合并到branch1
git checkout branch1
git checkout branch2 test.c
```

- 比较两个分支的差异

```shell
git diff branch1 branch2
```

- 比较两个分支的提交

```shell
# branch1有的而branch2没有
git log branch1 ^branch2
# branch1比branch2多的提交
git log branch1..branch2
# 不管谁提交的多，有差异的提交
git log branch1...branch2
# 左箭头< 标识branch1，右箭头>标识branch2
git log --left-right branch1...branch2
```

## 将log格式化输出

```shell
git log --date=iso --pretty=format:'"%h","%an","%ad","%s"' >log.csv
```
logc参数说明如下：

```shell
-p 　　　　按补丁格式显示每个更新之间的差异。
--stat 　　显示每次更新的文件修改统计信息。
--shortstat 　　只显示 --stat 中最后的行数修改添加移除统计。
--name-only 　　仅在提交信息后显示已修改的文件清单。
--name-status 　　显示新增、修改、删除的文件清单。
--abbrev-commit 　　仅显示 SHA-1 的前几个字符，而非所有的 40 个字符。
--relative-date 　　使用较短的相对时间显示（比如，“2 weeks ago”）。
--graph 　　显示 ASCII 图形表示的分支合并历史。
--pretty 　　使用其他格式显示历史提交信息。可用的选项包括 oneline，short，full，fuller 和 format（后跟指定格式）
```

格式信息说明如下：

```shell
选项 说明
%H 　提交对象（commit）的完整哈希字串
%h 　提交对象的简短哈希字串
%T 　树对象（tree）的完整哈希字串
%t 　 树对象的简短哈希字串
%P 　父对象（parent）的完整哈希字串
%p 　父对象的简短哈希字串
%an 作者（author）的名字
%ae 作者的电子邮件地址
%ad 作者修订日期（可以用 -date= 选项定制格式）
%ar 作者修订日期，按多久以前的方式显示
%cn 提交者(committer)的名字
%ce 提交者的电子邮件地址
%cd 提交日期
%cr 提交日期，按多久以前的方式显示
%s 提交说明
```

可以在比较两个分支的同时，将日志格式化输出：

```shell
git log --date=iso --pretty=format:'"%h","%an","%ad","%s"' branch1..branch >log.csv
```

# reference

1. https://www.jianshu.com/p/413ea4c4ccf6

2. https://blog.csdn.net/allanGold/article/details/87181284
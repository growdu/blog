---
description: "本地搭一个 git 远程仓库：git init --bare 建库，再用 ssh 地址 clone 下来。"
---
# 本地git仓库

## 创建仓库

```shell
mkdir repo.git
git --init bare repo.git
```
## 连接仓库

```shell
git clone user@localhost:/path/repo.git
```
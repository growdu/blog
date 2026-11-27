---
description: "git 使用备忘：git bash 里 git status 显示不了中文时该配什么。"
---
# git指北

## git bash git status无法显示中文

```shell
git config --global core.quotepath false
```
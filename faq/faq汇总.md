# faq汇总

- vscode git status 中文乱码

```shell
git config --global core.quotepath false
```

```shell
PS D:\code\blog> git status .
On branch master
Your branch is ahead of 'gitee/master' by 16 commits.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        "vue/css\346\225\231\347\250\213.md"

nothing added to commit but untracked files present (use "git add" to track)
PS D:\code\blog> git config --global core.quotepath false
PS D:\code\blog> git status .
On branch master
Your branch is ahead of 'gitee/master' by 16 commits.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        vue/css教程.md

nothing added to commit but untracked files present (use "git add" to track)
```
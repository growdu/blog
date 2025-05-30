### vim + ctags + cscope = 强大的IDE

-   [1.看代码需求的功能](https://blog.csdn.net/weixin_42910064/article/details/113522043#1_10)
-   [2\. 插件简介](https://blog.csdn.net/weixin_42910064/article/details/113522043#2__19)
-   -   [2.1 ctags 和 cscope 的功能](https://blog.csdn.net/weixin_42910064/article/details/113522043#21_ctags__cscope__20)
    -   [2.1 安装插件](https://blog.csdn.net/weixin_42910064/article/details/113522043#21__28)
    -   [2.2 插件的使用方式](https://blog.csdn.net/weixin_42910064/article/details/113522043#22__31)
-   [3\. 如何在vim中快捷地使用ctags以及cscope](https://blog.csdn.net/weixin_42910064/article/details/113522043#3_vimctagscscope_39)
-   -   [3.1 快捷生成tags以及cscope.out](https://blog.csdn.net/weixin_42910064/article/details/113522043#31_tagscscopeout_43)
    -   [3.2 配置vim开启时加载插件所需文件](https://blog.csdn.net/weixin_42910064/article/details/113522043#32_vim_78)
    -   [3.3 快捷使用](https://blog.csdn.net/weixin_42910064/article/details/113522043#33__110)

> 刚开始工作的时候要使用 Linux 系统，不会安装 VS，就安了一个 Source Insight 用来看代码。小白的我把整个项目加载到 Source Insight 里面，导致远程服务器桌面卡崩溃，卡了一天！不愧是我！  
> 后来决定下狠心学 vim 命令，毕竟还是有不少大佬在用 vim 的。  
> 经过一段时间的适应和摸索，我最终学会了 vim 的使用技巧。 感叹一下它真是一个强大的 IDE！

vim 的最大痛点在于它就是文本编辑器，难以实现函数/变量的跳转。但有了 ctags 和 cscope 这两个插件，它就能实现非常方便的函数/变量跳转以及查找功能。

本文将总结 ctags 以及 cscope 两个插件的**快捷使用方式**以及在 .vimrc 中的**配置方式**。对于他们的详细使用命令以及下载安装，网上已经有很多博文，不再赘述。

## 1.看代码需求的功能

看代码时需求最大的功能其实也就两个：

1.  **跳转到定义**。  
    当你看到一个函数被调用，但并不知道这个函数实现了什么功能时，可能会想看一看这个函数具体怎么实现的。那就需要跳转的函数的定义查看它的代码。变量，结构体变量，实例也是如此。
2.  **跳转到调用**。  
    当你发现一个函数传入的参数有点问题，想看看哪里调用了这个函数以确定输入参数为何有误时。那就需要跳转到调用此函数的地方。

能高效并简单地实现以上两点的编辑器，我愿称之为强大的IDE。

## 2\. 插件简介

## 2.1 ctags 和 cscope 的功能

1.  ctags:  
    ctags 插件能实现上文所述第一个功能，跳转到定义。但遗憾的是它不能跳转到调用。
    
2.  cscope (cs):  
    cscope 可以实现以上两点，既可以跳转到定义，又可以跳转到调用。只不过它的操作没有ctags那么方便简单。
    

因此**将 vim， ctags， cscope 结合起来，他们就能完美实现跳转到定义以及跳转到调用的功能**。此外配合本文总结的快捷使用方式，我认为它们的效率和便捷程度能超越频频卡顿的Source Insight。

## 2.1 安装插件

目前的 vim 都是带着 ctags 以及 cscope 的，不需要额外安装。如果你的 Linux 系统太老，vim 没有安装这两个插件，那你网上搜一下，很多人总结过如何下载安装，shell控制台中输入命令即可。

## 2.2 插件的使用方式

这两个插件的使用方式都是：

1.  遍历代码文件，生成插件所需关键词文件。
2.  用 vim 加载插件所需文件
3.  采用插件的命令在vim中进行跳转。

这里不对基本命令作介绍，需要了解的搜索网络其他文章即可。下文会详细介绍快捷使用方式的配置，让其中的1和2步高效完成，让我们只需要进行代码阅读的第3步。

## 3\. 如何在vim中快捷地使用ctags以及cscope

我们知道在每个账户的根目录下可以用 .vimrc 文件进行对vim的配置，同时不影响其他账户使用vim。同样的在 .vimrc 中可以进行对 ctags 以及 cscope 的配置，让使用方式的第2步在vim开启时刻就完成。  
此外还可以运用 nmap 映射一个快捷键，在 vim 中运行 shell 命令以完成关键词文件的生成，也就是上述第1步。

## 3.1 快捷生成tags以及cscope.out

```
vim .vimrc
```

首先再用户根目录下进入 .vimrc文件。在其中添加以下语句。

```
"Generate tags and cscope.out from FileList.txt (c, cpp, h, hpp)
nmap <C-@> :!find -name "*.c" -o -name "*.cpp" -o -name "*.h" -o -name "*.hpp" > FileList.txt<CR>
                       \ :!ctags -L -< FileList.txt<CR>
                       \ :!cscope -bkq -i FileList.txt<CR>

```

将 find，ctags， cscope 命令映射到 ctrl + @ 快捷键上。

find具体实现的是查找当前目录以及子目录下所有 .h, .hpp, .c, .cpp文件，将找到的文件名放到 FileList.txt 文件中。如果你需要 java 文件，或是 hidl 文件，或是 .xml 文件，则将想要的文件后缀添加到 find 命令中即可。

ctags -L 是采用指定文件生成 tags，用这个命令生成 tags 会让它只包含 FileList.txt 文件中所列的文件。以这种方式过滤特定后缀的文件，使得 tags 大大减小。（tags的大小直接影响跳转的效率。有时包含一些编译生成文件.bin ,.so 等会让 tags 变得特别大，在跳转时非常卡顿，会列出许多无效的索引。）

cscope -bkq -i 同理会使用指定文件提供的文件列表生成 cscope.out。

编辑完成退出后，就可以使用 ctrl + @ 快捷生成 tags 以及 cscope.out 了。

```
cd xxxxxxx
vim ./

:qa!
```

进入工程**相关代码目录**（非工程根目录，不然你会为整个工程生成插件文件。有的工程非常大，导致生成插件文件会非常卡，并且不根本不需要无关的代码索引，所以你只需要进入你负责的代码目录就行），vim 打开本目录，然后 ctrl + @ 生成插件文件。  
生成后输入:qa! 强制退出 vim ，此时插件所需文件就完全准备好了。

## 3.2 配置vim开启时加载插件所需文件

再次回到用户根目录，进入 .vimrc 文件。在里面添加如下配置。

```
if has("cscope")
    set csto=0
    set nocsverb
    " add any database in current directory
    if filereadable("cscope.out")
        cs add cscope.out
    endif
    set csverb
    "set cst  这两句会将cscope当作tag，当找不到时会卡住，因此注释掉
    "set cscopetag
endif

nmap zs :cs find s <C-R>=expand("<cword>")<CR><CR>
nmap zg :cs find g <C-R>=expand("<cword>")<CR><CR>
nmap zc :cs find c <C-R>=expand("<cword>")<CR><CR>
nmap zt :cs find t <C-R>=expand("<cword>")<CR><CR>
nmap ze :cs find e <C-R>=expand("<cword>")<CR><CR>
nmap zf :cs find f <C-R>=expand("<cfile>")<CR><CR>
nmap zi :cs find i ^<C-R>=expand("<cfile>")<CR>$<CR>
nmap zd :cs find d <C-R>=expand("<cword>")<CR><CR>

```

vim 打开时会自动加载当前目录下的 tags 文件，因此 tags 不用配置了。但 cscope.out 需要配置才能在 vim 打开时加载。

如上的配置将在当前目录执行 cs add cscope.out 以完成加载，并将 cscope.out 当作 tags 使用。此外映射了 cs 的快捷建。其中 z + c 和 z + t 两个快捷操作可以实现跳转到定义，以及搜索光标所在字符串出现的所有位置。

最后保存退出，那么所有的快捷配置就完成了。

## 3.3 快捷使用

1.  每当拿到新的工程代码，进入相关代码目录，利用 vim ./ 打开当前目录， 然后 crtl + @ 生成插件所需文件，最后退出 vim。此步只需进行一次。
2.  在此目录中打开任意代码文件或任意子目录代码文件，  
    利用 crtl + \] 跳转到定义。  
    利用 z + c 跳转到调用。  
    利用 z + t 查找光标所在的字符串出现的所有位置。  
    利用 crtl + t 跳转回到上次的位置。

至此我们强大的IDE快捷使用方式就介绍完了。需要完善你的 IDE 使其超越 VS，那么你可以多多去了解其他 vim 的插件，诸如 Tlist，Minibuffer，omnifunc等。  
加油！
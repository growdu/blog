# kconfig和kbuild指北

kconfig和kbuild是linux用来辅助配置和编译的工具。

Linux Kernel在设计配置和编译体系时至少应该有如下几点考虑：

-  满足配置和编译内核以及内核模块的所有需求

- 较高的运行效率

- 配置阶段和编译阶段平滑结合

- 对内核开发者来说，这套体系应该易用、易变、易维护

- 其设计本身应该做到层次清晰

Kconfig，顾名思义，用于辅助2.6以后版本Linux内核的配置(**K**ernel **config**)；Kbuild，也物如其名，用于辅助2.6以后版本Linux内核的编译(**K**ernel **build**)。这里索性将Kconfig和Kbuild称作辅助工具(不单纯叫脚本或配置文件)，因为它们自身既有逻辑概念，又有物理存在。如果你曾在Linux Kernel的源码目录中徜徉过，你就会知道Kconfig文件散布在核心源码的各个角落；Kbuild文件还好，只在顶层目录、include目录下子目录、drivers下子目录以及各个arch/$ARCH/include的子目录中分布。

### make *config阶段



# reference

1. http://www.360doc.com/content/15/0610/18/4672432_477198876.shtml
2. https://www.cnblogs.com/fah936861121/p/7229522.html
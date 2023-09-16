# shell脚本进阶

## 跨脚本文件调用函数

- caller

    ```shell
    #!/bin/bash
    var1="caller"

    function main()
    {
        echo "var1 in caller is ${var1}"
    }
    ```

- call  

```shell
     #!/bin/bash
    . ./caller.sh
    # source ./caller.sh
    var1="call"

    main
```

执行结果如下：

```shell
$ ./call.sh
var1 in caller is call
```

可以看到成功调用了caller中main函数，同时由于先导入caller.sh文件，后再声明var1变量，最终打印出var1变量值为call。

下面更改变量和引入函数的顺序，修改call.sh脚本如下：

```shell
 #!/bin/bash
    var1="call"
    . ./caller.sh
    # source ./caller.sh
    #var1="call"

    main
```

此时执行结果如下：

```shell
 ./call.sh
var1 in caller is caller
```

可以看到成功调用了caller中main函数，同时由于先声明var1变量，后再导入caller.sh文件，最终打印出var1变量值为caller。
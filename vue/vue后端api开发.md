# vue后端api开发

前端界面写好后，一般需要开发后端进程，提供相关的接口给前端展示。
一般前端用js之类的语言编写，后端采用restful api提供，实现的话可以采用java、go、python等语言实现。

这里我们使用go语言和gin框架来编写restful api。

## go + gin

```shell
go mod init anycode_api
go env -w GOPROXY=https://proxy.golang.com.cn,direct
go get github.com/gin-gonic/gin
```

编写main.go，内容如下：

```
package main

import (
    "github.com/gin-gonic/gin"
    "net/http"
    "os"
    "fmt"
)

var count uint64


func main() {
    args := os.Args
    var url string
    if len(args) > 1 {
        url = args[1]
    } else {
        fmt.Println("unkown input, using ", args[0], "ip:port.");
        return
    }
    // 创建一个默认的 Gin 引擎
    r := gin.Default()
    r.Use(Cors())
    // 定义一个路由，处理 GET 请求
    r.GET("/login", func(c *gin.Context) {
        // 返回一个 JSON 响应
        count++
        c.JSON(http.StatusOK, gin.H{
            "visit":200,
        })
    })

    // 启动 HTTP 服务器，监听在 8080 端口
    r.Run(url)
}
```

离线打包，

```shell
go mod tidy
go mod vendor
```

## 接口测试

接口测试可以使用postman或者apifox（我搜索的是postman，推荐的是apifox）。

## 前端发起请求

引入axios库，用于发起http请求。

```shell
npm install axios
```
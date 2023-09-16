## 前言

-   CORS (Cross-Origin Resource Sharing) 是每个网页开发者早晚都会遇到的问题。当你阅读这篇文章时，你很有可能正在处理一个CORS错误。本文，我将告诉你CORS是什么，以及**如何处理CORS错误**。

___

-   这就是你正在处理的问题吧！

![](https://pic2.zhimg.com/v2-e863b12e52d77600f5f96135f5a97325_b.png)

-   我们正在试着从本机的1234端口请求一个位于本机的3000端口的一个url下的资源，这个请求被CORS阻止了，**因为两个地址的端口是不同的**。
-   **CORS默认阻止所有不同“来源”之间的任何形式的请求。这能阻止人们从不在他们控制范围内的服务器那里获取数据。**想象一下，你并不希望随便哪个人，只要拿着你的cookie，假装是你一样，向你的知乎账号或者银行账户发起请求（这些cookie中可能含有你的关键信息）。
-   **CORS不关心来自相同“来源”的请求。**如果你从本机3000端口的根目录请求其中的一个子目录的资源，CORS不会起作用，你也不会遇到阻碍。
-   **相同的“来源”可以理解为相同的scheme并且相同的host并且相同的port**。

___

## 如何解决CORS？

-   如果你想从你的服务器向你的客户端发起请求，并且他们位于不同的“源”，那么你需要 ↓

-   **让你的服务器向客户端在每次请求的响应报文中加入 Access-Control-Allow-Origin 的字段，取值为服务器允许的客户端访问的源。**
-   **注意：如果你不打算对客户端的来源做任何限制，你可以将这个字段设置为\*。**
-   比如，我们正在从本机1234端口向本机3000端口发送请求，那么我们就要在从3000向1234返回的响应报文中加入 Access-Control-Allow-Origin 的字段，取值设置为xxx:1234，即服务器允许的请求来源地址。

-   如何让服务器返回这个字段呢？这取决于你使用的编程语言。如果你使用的是Node.js，可以使用cors库。如果是其它语言，也可以找到合适的处理手段。

___

## CORS 预告  

-   如果你正在跨域请求一个PUT请求，等更为复杂的请求。那么仅仅按照上文所述进行操作是不够的。当跨域请求为简单的请求，**如GET和POST，那么不会进行CORS预告。**
-   **浏览器会在发送请求报文之前发送一个预告报文，询问服务器是否允许PUT请求。**这个预告的请求报文会包括 Access-Control-Request-Method 和 Access-Control-Request-Headers 的字段，包含了客户端将要在正式的请求中使用的方法和请求头的值。
-   之后，服务器会在响应报文中告诉浏览器，这些方法和请求头是否有效。这些信息会放在 Access-Control-Request-Headers 字段和Access-Control-Allow-Headers 字段中。如果浏览器发现这些字段完全匹配，那么正式请求就得以实现。
-   如果使用node.js的cors库，实现这个操作的方式会很简单：

```
const express = require('express')
const app = express()
const cors = require('cors')

app.use(cors({
  origin: 'http://localhost:1234',
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type']
}))

// Server code 

app.listen(3000)
```

-   这样服务器就会响应报文中添加刚才说的那些字段。值得一提的是，你并不需要手动设置allowedHeaders字段，因为它的默认值和客户端发来的那个字段中的值相同。

___

## CORS 设置cookie  

-   默认情况下，CORS不会允许设置cookie。如果你希望能够使用，需要做两件事： ↓

1.  浏览器告知服务器，我需要设置cookie。
2.  服务器将 Access-Control-Allow-Credentials设置为true，允许使用cookie。

-   js实现如下：  
    

-   客户端：
-   `javascript fetch(url, { credentials: 'include' })`
-   服务器端(使用cors库实现)：

```
 const express = require('express')
const app = express()
const cors = require('cors')

app.use(cors({
  origin: 'http://localhost:1234',
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type'],
  credentials: true
}))

// Server code 

app.listen(3000)
```

___

## 总结

-   CORS默认阻止不同来源的任何形式的请求。这样一来，服务器可以只对其信任的请求方提供数据和服务，提高安全性。为了解决CORS报错的问题，只要让服务器信任自己使用的客户端就可以了，这需要让服务器在响应报文中为**Access-Control-Allow-Origin字段**添加相应的值。如果为了调试方便，可以设置为**\***，对来源不做限制。
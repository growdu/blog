# html简单教程

## 简单登录界面

以下是一个简单的HTML登录页面的代码，你可以根据自己的需要进行修改：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>登录页面</title>
<style type="text/css">
body {
background-color: #f2f2f2;
}
.login {
width: 400px;
height: 300px;
background-color: #fff;
border-radius: 5px;
box-shadow: 0px 0px 10px #ccc;
position: absolute;
top: 50%;
left: 50%;
margin-top: -150px;
margin-left: -200px;
}
.login h1 {
text-align: center;
font-size: 30px;
color: #333;
padding-top: 30px;
}
.login input[type="text"], .login input[type="password"] {
width: 300px;
height: 40px;
border-radius: 5px;
border: none;
outline: none;
margin-top: 30px;
margin-left: 50px;
padding-left: 10px;
font-size: 16px;
}
.login input[type="submit"] {
width: 300px;
height: 40px;
background-color: #f00;
border-radius: 5px;
border: none;
outline: none;
color:#fff;
font-size: 18px;
cursor:pointer; 
margin-top: 30px; 
margin-left:50px; 
}
</style>
</head>
<body>
<div class="login">
<h1>登录</h1>
<form action="" method="post">
<input type="text" name="username" placeholder="请输入用户名"><br>
<input type="password" name="password" placeholder="请输入密码"><br>
<input type="submit" value="登录">
</form>
</div>
</body>
</html>
```
这是一个简单的登录页面，你可以根据自己的需要进行修改。如果你想了解更多关于HTML的知识，可以参考这些网站：[W3Schools](https://www.w3schools.com/html/)、[MDN Web Docs](https://developer.mozilla.org/zh-CN/docs/Learn/HTML)。

(1) HTML+CSS+JS实现十款好看的登录注册界面模板，赶紧收藏起来吧！_好看的登录界面_王同学要努力的博客-CSDN博客. https://blog.csdn.net/m0_46374969/article/details/115906705.
(2) HTML+CSS登录界面_html登录页面代码_桐艾的博客-CSDN博客. https://blog.csdn.net/tongai1/article/details/105954419.
(3) 如何制作一个简单的HTML登录页面（附代码） - 知乎专栏. https://zhuanlan.zhihu.com/p/143671138.

## 发送get请求并显示返回内容

当客户端使用GET方法向服务器发送请求时，请求的数据会附加在URL的末尾。服务器可以使用相同的HTTP协议来回答请求。在客户端，可以使用JavaScript来获取GET请求的数据。以下是一个简单的例子：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>GET请求</title>
<script src="https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
<script>
$(document).ready(function(){
    $("button").click(function(){
        $.get("demo_test_get.asp",
        {
          name: "Donald Duck",
          city: "Duckburg"
        },
        function(data, status){
            alert("Data: " + data + "\nStatus: " + status);
        });
    });
});
</script>
</head>
<body>

<button>发送 GET 请求</button>

</body>
</html>
```

在这个例子中，我们使用了jQuery库来发送GET请求。当用户点击按钮时，jQuery会向demo_test_get.asp发送GET请求，并将数据附加在URL的末尾。当服务器回答请求时，jQuery会调用回调函数，并将服务器返回的数据作为参数传递给它。

如果你想了解更多关于HTML、JavaScript和jQuery的知识，可以参考这些网站：[W3Schools](https://www.w3schools.com/)、[MDN Web Docs](https://developer.mozilla.org/zh-CN/)。

(1) 发送表单数据 - 学习 Web 开发 | MDN - MDN Web Docs. https://developer.mozilla.org/zh-CN/docs/Learn/Forms/Sending_and_retrieving_form_data.
(2) 纯 HTML 页面发请求获取数据并渲染到页面上 - CSDN博客. https://blog.csdn.net/LuckKing0925/article/details/111308084.
(3) 使用Ajax发送http请求（get&post请求） - 千古壹号 - 博客园. https://www.cnblogs.com/qianguyihao/p/8485028.html.

## 发送post请求

在HTML中，可以使用form元素来创建一个表单，然后使用POST方法将表单数据发送到服务器。以下是一个简单的例子：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>POST请求</title>
</head>
<body>
<form action="http://www.example.com/login" method="post">
<label for="username">用户名:</label>
<input type="text" id="username" name="username"><br><br>
<label for="password">密码:</label>
<input type="password" id="password" name="password"><br><br>
<input type="submit" value="提交">
</form>
</body>
</html>
```

在这个例子中，我们使用了form元素来创建一个表单，然后使用POST方法将表单数据发送到http://www.example.com/login。在表单中，我们使用了两个input元素来接收用户名和密码。当用户点击提交按钮时，表单数据将被发送到服务器。

如果你想了解更多关于HTML的知识，可以参考这些网站：[W3Schools](https://www.w3schools.com/html/)、[MDN Web Docs](https://developer.mozilla.org/zh-CN/docs/Learn/HTML)。

(1) POST - HTTP | MDN - MDN Web Docs. https://developer.mozilla.org/zh-CN/docs/web/http/methods/post.
(2) HTML 请求方法 - w3school 在线教程. https://www.w3school.com.cn/tags/html_ref_httpmethods.asp.
(3) jQuery post() 方法 | 菜鸟教程. https://www.runoob.com/jquery/ajax-post.html.
(4) 发送表单数据 - 学习 Web 开发 | MDN - MDN Web Docs. https://developer.mozilla.org/zh-CN/docs/Learn/Forms/Sending_and_retrieving_form_data.

### 接收post请求

当客户端使用POST方法向服务器发送请求时，服务器会将请求的数据存储在HTTP请求的请求主体中。服务器可以使用相同的HTTP协议来回答请求。在客户端，可以使用JavaScript来获取POST请求的数据。以下是一个简单的例子：

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>POST请求</title>
<script src="https://cdn.bootcdn.net/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
<script>
$(document).ready(function(){
    $("button").click(function(){
        $.post("demo_test_post.asp",
        {
          name: "Donald Duck",
          city: "Duckburg"
        },
        function(data, status){
            alert("Data: " + data + "\nStatus: " + status);
        });
    });
});
</script>
</head>
<body>

<button>发送 POST 请求</button>

</body>
</html>
```

在这个例子中，我们使用了jQuery库来发送POST请求。当用户点击按钮时，jQuery会向demo_test_post.asp发送POST请求，并将数据存储在HTTP请求的请求主体中。当服务器回答请求时，jQuery会调用回调函数，并将服务器返回的数据作为参数传递给它。

如果你想了解更多关于HTML、JavaScript和jQuery的知识，可以参考这些网站：[W3Schools](https://www.w3schools.com/)、[MDN Web Docs](https://developer.mozilla.org/zh-CN/)。

(1) 发送表单数据 - 学习 Web 开发 | MDN - MDN Web Docs. https://developer.mozilla.org/zh-CN/docs/Learn/Forms/Sending_and_retrieving_form_data.
(2) javascript能否获取到post请求内的数据? - SegmentFault 思否. https://segmentfault.com/q/1010000004523107.
(3) ChatGPT流式streaming回复的实现 - 掘金. https://juejin.cn/post/7222440107214241829.
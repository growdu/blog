# vue项目开发流程

## 环境配置

```shell
asdf plugin add nodejs
asdf install nodejs 16.20.2
```

## 创建项目

```shell
npm create vite@latest my-vue-app -- --template vue
npm install 
npm run dev
```

### 修改调试端口

修改vite.config.js,修改如下所示，添加server的host和port。

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 3000 // 设置 Vite 服务器监听的端口
  }
})

```

## 项目结构

- index.html

项目入口是index.html,里面有一个app的div，就是vue里面的app,这个app指定了要运行的js入口，也就是main.js。

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vite + Vue</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```
这个html里的内容也是可以更改的，比如这里的 <head>标签里的内容。

- main,js

在index.html里指定入口是main.js后，就会在main.js里初始化vue相关的东西。

```js
import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

createApp(App).mount('#app')
```

在这个文件里主要是把vue接口导入进来，以及导入css，然后导入App.vue，到这里入口传到到App.vue。

main.js会将vue框架mount到界面。这些一般都不需要更改，除非需要引入其他的东西。

- App.vue

App.vue就是vue的核心开发文件，这里就是整个页面的展示，对于单页面应用来说，这个就是页面对应的代码。

```shell
<script setup>
import HelloWorld from './components/HelloWorld.vue'
</script>

<template>
  <HelloWorld msg="anycode开发环境" />
</template>
```

vue采用组件化和模板化来开发，在开头可以引入其他的组件，这个一般是封装好的组件，放在components目录下。

比如上面的例子中就导入了HelloWorld这个组件。

然后对于这个App来说，有一个模板，这个template可以简单理解为页面的body。

然后里面会显示HelloWorld这个组件，这个时候控制权就到了./components/HelloWorld.vue。

app.vue给它传了一个msg的参数。

- ./components/HelloWorld.vue

```vue
<script setup>
defineProps({
  msg: String,
})
</script>

<template>
  <h1>{{ msg }}</h1>
  <p>
    hello,anycode.
  </p>
</template>
```

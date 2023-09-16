# gitbook教程

## 下载gitbook

```shell
 npm install gitbook-cli -g
```

## 初始化项目

```shell
gitbook init
```

初始化时报错，

```shell
E:\node_global\node_modules\gitbook-cli\node_modules\npm\node_modules\graceful-fs\polyfills.js:287
      if (cb) cb.apply(this, arguments)
                 ^

TypeError: cb.apply is not a function
    at E:\node_global\node_modules\gitbook-cli\node_modules\npm\node_modules\graceful-fs\polyfills.js:287:18
    at FSReqCallback.oncomplete (node:fs:199:5)
```

解决方案为：

```shell
 cd node_global/node_modules/gitbook-cli/node_modules/npm/node_modules/
 npm install graceful-fs@latest --save
```

即将graceful-fs更新到最新。请参考[Stack Overflow](https://stackoverflow.com/questions/64211386/gitbook-cli-install-error-typeerror-cb-apply-is-not-a-function-inside-graceful).

修改后gitbook init 无任何报错，但未生成README.md和SUMMARY.md，手动生成也无法构建。

解决方案为：

```shell
npm install gitbook-cli@2.1.2 --global
```

此时在执行gitbook init，发现只生成了README.md，手动创建SUMMARY.md。

## 构建

```shell
gitbook serve
gitbook build
```

## 结合github 部署gitbook

创建另一个page分支，用于发布构建的gitbook。

```shell
PS F:\code\db021> git branch
* master
  page
```

然后构建gitbook，

```shell
growd@DESKTOP-0ED5P84 MINGW64 /f/code/db021 (master)
$ gitbook build
info: 7 plugins are installed
info: 6 explicitly listed
info: loading plugin "highlight"... OK
info: loading plugin "search"... OK
info: loading plugin "lunr"... OK
info: loading plugin "sharing"... OK
info: loading plugin "fontsettings"... OK
info: loading plugin "theme-default"... OK
info: found 9 pages
info: found 29 asset files
info: >> generation finished with success in 2.4s !

growd@DESKTOP-0ED5P84 MINGW64 /f/code/db021 (master)
$ ls
_book/  img/      part2.md  part4.md  part6.md  part8.md   SUMMARY.md
code/   part1.md  part3.md  part5.md  part7.md  README.md
```

构建成功后可以看到目录下多了一个_book目录，将这个目录重命名为docs然后提交到github上（github只能识别/docs或者/），然后开启page功能，选定分支为page。

```shell
growd@DESKTOP-0ED5P84 MINGW64 /f/code/db021 (master)
$ mv _book/ docs
$ git checkout page
Switched to branch 'page'
$ git add docs
$ git commit -m "update docs"
$ git push origin master
```


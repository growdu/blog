# docusaurus自定义渲染内容

使用docusaurus编写文档时，docusaurus仅支持编译成网页，在编译成pdf时需要做一些特殊处理。

这个时候就需要在markdown文件中保留一些rst格式或者rst语法，这些语法格式在编译html时被忽略，在编译pdf才生效。

Docusaurus 使用的是 remark 库，来解析和处理 Markdown 文件，可以通过 remark 自定义插件来忽略 eval-rst 代码块。

## 下载unist-util-visit

```shell
npm install unist-util-visit
```

## 编写插件

```shell
mkdir remark-plugins
vim  remark-ignore-eval-rst.js
```
在js文件中添加如下内容：

```js
// remark-plugins/remove-code-blocks.js
import { visit } from 'unist-util-visit';

module.exports = function removeCodeBlocks() {
  return (tree) => {
    visit(tree, 'code', (node) => {
      if (node.lang === 'eval-rst' || node.lang === 'eval-md') {
        node.type = 'text';
        node.value = ''; // Remove the content
      }
    });
  };
};

```

在docusaurus.config.js中引入该插件：

```js
const remarkIgnoreEvalRst = require('./remark-plugins/remark-ignore-eval-rst');
......
docs: {
          remarkPlugins: [remarkIgnoreEvalRst],  // 添加自定义的 Remark 插件
        },
.....
```

同时修改一个md文件，使其内容被"```eval-rst" 和"```"包裹:

```md
这里的内容显示在网页。

```eval-rst
这里的内容不显示在网页。
```
```
最后执行npm start观察结果。

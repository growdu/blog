# pandoc自定义过滤器

pandoc是一个强大的文本转换工具，可以实现各种文本格式的互相转换。

在开发过程中常用的文档格式有rst、markdown、pdf、docx等，pandoc支持这些格式互转，但是对于一些特殊格式和排版支持不是太好，需要做一些适配和二次开发。

常见的方式用过滤器方式、模板方式、使用高级参数等来进行调整适配。

但要想达到高度定制，还是需要使用过滤器的方式。

## pandoc的工作原理

pandoc使用语法树来进行解析，并且使用json来表示文档的内部抽象语法树，是pandoc文档内容的结构化表述。

pandoc允许用户通过解析和操作json结构来自定义文档内容和格式。

Pandoc 的 JSON 结构（schema）是 Pandoc 文档转换过程中的核心部分，它表示文档的抽象语法树 (AST)，允许用户通过解析和操作 JSON 结构来自定义文档内容和格式。JSON schema 的细节可以帮助你理解 Pandoc 如何表示文档中的各类元素（如段落、标题、代码块、表格等）。

以下是 Pandoc JSON schema 的详细介绍：

### 1. **顶层结构**
Pandoc 的 JSON 文件的顶层结构通常包括两个主要部分：
- `meta`: 包含文档的元数据，如标题、作者、日期等。
- `blocks`: 包含文档的主要内容，以列表的形式表示。每个列表项都是一个块元素，例如段落、标题、列表、表格等。

**示例顶层结构：**

```json
{
  "meta": {
    "title": {
      "t": "MetaInlines",
      "c": [
        {"t": "Str", "c": "Sample Document"}
      ]
    }
  },
  "blocks": [
    {
      "t": "Para",
      "c": [
        {"t": "Str", "c": "Hello"},
        {"t": "Space"},
        {"t": "Str", "c": "world"}
      ]
    }
  ]
}
```

- `meta`: 包含文档元数据的对象，通常包括 `title`, `author`, `date`。
- `blocks`: 是文档主体的内容，这里包含了一个段落 (`Para`)。

### 2. **元数据 (`meta`)**
`meta` 包含文档的元数据信息，可以包括：
- `title`: 文档的标题。
- `author`: 作者列表。
- `date`: 文档的日期。
元数据可以有多种形式，包括字符串、内联元素或块元素。

**示例：**

```json
{
  "title": {
    "t": "MetaInlines",
    "c": [{"t": "Str", "c": "My Document"}]
  },
  "author": {
    "t": "MetaInlines",
    "c": [{"t": "Str", "c": "Author Name"}]
  },
  "date": {
    "t": "MetaInlines",
    "c": [{"t": "Str", "c": "2024-09-15"}]
  }
}
```

### 3. **块元素 (`blocks`)**
块元素表示文档的结构部分，它可以是段落、标题、列表、代码块等。常见的块元素包括：

- `Para`: 段落，内容为内联元素的列表。
- `Header`: 标题，包含一个级别（1-6）和内联元素。
- `CodeBlock`: 代码块，包含代码和可选的属性。
- `BlockQuote`: 引用块。
- `Table`: 表格结构。
- `BulletList` 和 `OrderedList`: 列表。

**段落 (`Para`) 示例：**

```json
{
  "t": "Para",
  "c": [
    {"t": "Str", "c": "This"},
    {"t": "Space"},
    {"t": "Str", "c": "is"},
    {"t": "Space"},
    {"t": "Str", "c": "a"},
    {"t": "Space"},
    {"t": "Str", "c": "paragraph."}
  ]
}
```

### 4. **内联元素 (`Inlines`)**
内联元素是嵌入在段落或标题等块元素中的文本或小型元素。常见的内联元素包括：
- `Str`: 字符串。
- `Emph`: 斜体。
- `Strong`: 粗体。
- `Code`: 内联代码。
- `Link`: 超链接。
- `Image`: 图片。

**内联代码 (`Code`) 示例：**

```json
{
  "t": "Code",
  "c": [{"t": "Str", "c": "print('Hello, world!')"}]
}
```

### 5. **表格 (`Table`)**
`Table` 是一个复杂的结构，包含表头、表格主体、对齐方式、列宽等内容。表格的定义较为灵活，允许你指定每列的对齐、列宽、以及包含的内容。

**表格的结构示例：**

```json
{
  "t": "Table",
  "c": [
    [{"t": "AlignLeft"}, {"t": "AlignCenter"}],  # 对齐方式
    [{"t": "ColWidthDefault"}, {"t": "ColWidthDefault"}],  # 列宽
    [[{"t": "Plain", "c": [{"t": "Str", "c": "Header 1"}]}],  # 表头
     [{"t": "Plain", "c": [{"t": "Str", "c": "Header 2"}]}]],
    [[[{"t": "Plain", "c": [{"t": "Str", "c": "Row 1, Col 1"}]}],  # 表格数据
      [{"t": "Plain", "c": [{"t": "Str", "c": "Row 1, Col 2"}]}]]]
  ]
}
```

### 6. **Raw Block/Inline**
有时，文档中可能包含特定格式的原始数据（如 HTML 或 LaTeX）。这些内容以 `RawBlock` 或 `RawInline` 形式出现，用于保留特定格式的内容。

**示例：**

```json
{
  "t": "RawBlock",
  "c": ["html", "<div class='custom-class'>Custom HTML Content</div>"]
}
```

## 如何查看pandoc的json格式

以rst文件为例：

```shell
pandoc input.rst -f rst -t json
```

## rst转markdown

markdown由于历史原因为了支持更多的格式，衍生出多种markdown方言，pandoc在转换时支持指定gfm、markdown、markdown-strict、commonmark，来确定你所转换的markdown方言。

这里我们想要转换为docsuaurus（Facebook开源的一个文档框架）能识别的格式，因而只能使用commonmark来转换。其转换命令如下：

```shell
pandoc rst/input.rst -f rst -t commonmark -o md/output.md
```

在这里使用一个带有表格、图片、列表、代码块、告警的rst文件，将其转换为md。

### 图片

rst的代码如下：

```shell
.. image:: https://docusaurus.io/zh-CN/img/undraw_typewriter.svg
   :alt: element
```

换后的md格式如下：

```markdown
![element](https://docusaurus.io/zh-CN/img/undraw_typewriter.svg)
```

可以看到就是markdown的标准语法。

但是rst有一种类型的图片语法，使用figure关键字，pandoc将其转为md后变成了html标签：

rst的代码如下：

```rst
.. figure:: https://docusaurus.io/zh-CN/img/docusaurus.svg
```

转换后的md文件如下：

```markdown
<figure>
<img src="https://docusaurus.io/zh-CN/img/docusaurus.svg"
alt="https://docusaurus.io/zh-CN/img/docusaurus.svg" />
</figure>
```

可以看到直接变成了html标签，这个不太符合我们的格式要求，需要对其进行适配。

需要编写figure_filter.py的过滤器，用于对输入内容进行转换，其脚本内容如下：

```python
#!/usr/bin/env python3

from pandocfilters import toJSONFilter, Para, RawInline

def figure_to_markdown(key, value, format, meta):
    if key == 'Figure':
        # 获取 Figure 内部的 Plain 节点
        plain_node = value[2][0]
        if plain_node['t'] == 'Plain':
            # 遍历 Plain 中的元素，找到 Image
            for item in plain_node['c']:
                if item['t'] == 'Image':
                    # 获取 Image 节点中的图片 URL
                    image_info = item['c']
                    image_url = image_info[2][0]  # 获取图片 URL
                    
                    # 使用 RawInline 插入原始 Markdown 代码，并将其放入 Para 块中
                    return Para([RawInline('markdown', f'![]({image_url})')])

if __name__ == "__main__":
    toJSONFilter(figure_to_markdown)

```

在转换时使用如下命令进行转换：

```shell
pandoc rst/input.rst -t commonmark -o md/output_filter_figure.md --filter=./src/figure_filter.py
```
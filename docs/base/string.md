

# <center>字符串操作</center>

## 1 C语言

在 C 语言中，字符串实际上是使用 null 字符 '\0' 终止的一维字符数组。因此，一个以 null 结尾的字符串，包含了组成字符串的字符。

```C
char greeting[6] = {'H', 'e', 'l', 'l', 'o', '\0'};
char greeting[] = "Hello";
```

字符串常用操作函数：

|函数名称|功能|
|:--|:--|
|strcpy(s1,s2)|复制字符串s2到s1|
|strcat(s1,s2)|在s1末尾连接s2|
|strlen(s1)|返回s1字符串的长度|
|strcmp(s1,s2)|比较s1和s2的长度|
|strchr(s1,ch)|返回字符ch所在位置的指针|
|strstr(s1,s2)|返回字符串s2在s1中出现的起始位置|


## 2 java

|方法|功能|
|:--|:--|
|int length()|返回字符串|
|char charAt(int index)|返回指定位置的字符|
|void getChars(int sourceStart,int sourceEnd,char target[],int targetStart)|选取子串|
|char[\] toCharArray()|将字符串转换为字符数组|
|boolean contains(String str)|是否包含另一字符串|
|boolean equals（String str)|字符串是否相等|
|int compareTo(Object o)|把这个字符串和另一个对象比较。|
|int compareTo(String anotherString)|按字典顺序比较两个字符串。|
|int compareToIgnoreCase(String str)|按字典顺序比较两个字符串，不考虑大小写。|
|String concat(String str)|将指定字符串连接到此字符串的结尾|
|boolean endsWith(String suffix)|测试此字符串是否以指定的后缀结束。|
|byte[\] getBytes()|使用平台的默认字符集将此 String 编码为 byte 序列，并将结果存储到一个新的 byte 数组中。|
|byte[\] getBytes(String charsetName)|使用指定的字符集将此 String 编码为 byte 序列，并将结果存储到一个新的 byte 数组中。|
|int hashCode()|返回此字符串的哈希码。|
int indexOf(int ch)|返回指定字符在此字符串中第一次出现处的索引。|
|int indexOf(int ch, int fromIndex)|返回在此字符串中第一次出现指定字符处的索引，从指定的索引开始搜索。|
|int lastIndexOf(int ch)|返回指定字符在此字符串中最后一次出现处的索引。|
|int lastIndexOf(int ch, int fromIndex)|返回指定字符在此字符串中最后一次出现处的索引，从指定的索引处开始进行反向搜索。|
|boolean matches(String regex)|告知此字符串是否匹配给定的正则表达式。|
|String replace(char oldChar, char newChar)|返回一个新的字符串，它是通过用 newChar 替换此字符串中出现的所有 oldChar 得到的。|
|String replaceAll(String regex, String replacement)|使用给定的 replacement 替换此字符串所有匹配给定的正则表达式的子字符串。|
|String replaceFirst(String regex, String replacement)|使用给定的 replacement 替换此字符串匹配给定的正则表达式的第一个子字符串。|
|String[] split(String regex)|根据给定正则表达式的匹配拆分此字符串。
|
|boolean startsWith(String prefix)|测试此字符串是否以指定的前缀开始。|
|String substring(int beginIndex)|返回一个新的字符串，它是此字符串的一个子字符串。|
|String trim()|返回字符串的副本，忽略前导空白和尾部空白。|

## 3 C sharp

## 4 python

## 5 shell
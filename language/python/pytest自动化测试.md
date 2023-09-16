# pytest自动化测试

## yaml

yaml语法规则：

- 大小写敏感
- 使用缩进表示层级关系（不能用Tab，只能用空格）
- 相同层级的元素左对齐
- #号表示单行注释
- 字符串可以不用引号标注

使用如下命令下载安装：

```shell
pip install pyyaml
```

### yaml列表

```shell
#test_list.yaml 
- 5
- 2
- 0
```

```python
#!/usr/bin/python
# -*- coding: utf-8 -*-
import yaml

with open("list.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("list.yaml list is:")
    for d in data:
        print(d)
```

### yaml列表字典

```shell
-
 name: test
 age: 18
-
 name: cest
 age: 18
```

```python
with open("dict.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("dict.yaml list is:")
    for d in data:
        #print(d)
        print("name is " + d['name'] + ", age is " + str(d['age']))
```

### yaml字典列表

```shell
# 字典中存放列表
name:
 - jack
 - bob
 - anne
course:
 - english
 - math
 - chinese
```

```python
with open("dict_list.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("dict_list.yaml list is:")
    print("name list is:")
    for d in data['name']:
        #print(d)
        print(d)
    print("course list is:")
    for d in data['course']:
        #print(d)
        print(d)
```

## pytest fixture

> fixture是在测试函数运行前后，由pytest执行的外壳函数。fixture中的代码可以定制，满足多变的测试需求，包括定义传入测试中的数据集、配置测试前系统的初始状态、为批量测试提供数据源等等。fixture是pytest的精髓所在，类似unittest中setup/teardown，但是比它们要强大、灵活很多，它的优势是可以跨文件共享。

### fixture 作为参数使用

```python
@pytest.fixture()
def login():
    print("this is login fixture")
    user = "chen"
    pwd = 123456
    return user, pwd

def test_login(login):
    """将fixture修饰的login函数作为参数传递给本用例"""
    print(login)
    assert login[0] == "chen"
    assert login[1] == 123456
    assert "chen" in str(login)
```

#### 同一个用例传入多个fixture

```python
@pytest.fixture()
def user():
    user = "cris"
    return user

@pytest.fixture()
def pwd():
    pwd = "123456"
    return pwd

def test_trans_fixture(user, pwd):
    """同一条用例中传入多个fixture函数"""
    print(user, pwd)
    assert "cris" in str(user)
    assert pwd == "123456"
```

### 提供灵活的类似setup和teardown功能

> Pytest的fixture另一个强大的功能就是在函数执行前后增加操作，类似setup和teardown操作，但是比setup和teardown的操作更加灵活；具体使用方式是同样定义一个函数，然后用装饰器标记为fixture，然后在此函数中使用一个yield语句，yield语句之前的就会在测试用例之前使用，yield之后的语句就会在测试用例执行完成之后再执行。

```python
@pytest.fixture()
def run_function():
    print("run before function...")
    yield
    print("run after function...")

def test_run_1(run_function):
    print("case 1")

def test_run_2():
    print("case 2")

def test_run_3(run_function):
    print("case 3")
```

### 利用pytest.mark.usefixtures叠加调用多个fixture

> 如果一个方法或者一个class用例想要同时调用多个fixture，可以使用@pytest.mark.usefixtures()进行叠加。注意叠加顺序，先执行的放底层，后执行的放上层。需注意：

- 与直接传入fixture不同的是，@pytest.mark.usefixtures无法获取到被fixture装饰的函数的返回值；

- @pytest.mark.usefixtures的使用场景是：被测试函数需要多个fixture做前后置工作时使用；

```python
@pytest.fixture
def func_1():
    print("用例前置操作---1")
    yield
    print("用例后置操作---1")

@pytest.fixture
def func_2():
    print("用例前置操作---2")
    yield
    print("用例后置操作---2")

@pytest.fixture
def func_3():
    print("用例前置操作---3")
    yield
    print("用例后置操作---3")

@pytest.mark.usefixtures("func_3")  # 最后执行func_3
@pytest.mark.usefixtures("func_2")  # 再执行func_1
@pytest.mark.usefixtures("func_1")  # 先执行func_1
def test_func():
    print("这是测试用例")
```

# reference

1. https://zhuanlan.zhihu.com/p/613431669
2. https://zhuanlan.zhihu.com/p/564168267
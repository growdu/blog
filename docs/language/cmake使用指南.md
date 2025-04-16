# cmake使用指南

## cmake常用变量

- 获取当前目录

  ```cmake
  CMAKE_CURRENT_SOURCE_DIR
  CMAKE_CURRENT_LIST_FILE
  ```

## list

```cmake
# 声明一个list
set(name a.c b.c c.c)
# 往list里追加
list(append name d.c e.c)
# 使用list
add_executeable(test ${name})
```

## 添加库

- 添加动态库

  ```cmake
  add_library(name SHARED lib.c)
  ```

- 添加静态库

  ```cmake
  add_library(name STATIC lib.c)
  ```

  

## 添加可执行程序

```cmake
add_executeable(name main.c)
```

## 添加头文件路径

```cmake
target_include_directories(target private path)
```

## 添加链接库

```cmake
target_link_libraries(target name)
```

## 指定安装位置

```cmake
install(TARGETS test DESTINATION bin) #将test安装到/usr/local/bin目录下
```

## 拷贝相关依赖到指定目录

```cmake
install(DIRECTORY lib DESTINATION bin PATTERN "lib/*") #将lib下的所有文件拷贝到bin目录下
```


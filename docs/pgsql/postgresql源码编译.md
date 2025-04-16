# postgresql 源码编译

## 下载源码

```
git clone git://git.postgresql.org/git/postgresql.git
```

## 下载依赖

```
sudo yum install icu.x86_64 libicu-devel.x86_64
sudo yum install readline
sudo yum install readline-devel.x86_64
sudo yum install zlib-devel.x86_64
sudo yum install bison yacc
sudo yum install flex
```

## 编译

```
./configutr --prefix=`pwd`/debug
make -j 8
make install
```



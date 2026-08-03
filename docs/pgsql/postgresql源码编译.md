# postgresql 源码编译

## 下载源码

```text
git clone git://git.postgresql.org/git/postgresql.git
```text
## 下载依赖

```text
sudo yum install icu.x86_64 libicu-devel.x86_64
sudo yum install readline
sudo yum install readline-devel.x86_64
sudo yum install zlib-devel.x86_64
sudo yum install bison yacc
sudo yum install flex
```text
## 编译

```text
./configutr --prefix=`pwd`/debug
make -j 8
make install
```text
# 用 Meson 编译 PostgreSQL：从配置到回归测试的完整命令清单

| 编写人 | 编写内容 | 编写时间 |
| --- | --- | --- |
| growdu | 初稿，结合 PostgreSQL 18 dev 源码 | 2026-08-20 |

PostgreSQL 自 16 起把构建系统从 autotools 迁到了 **Meson + Ninja**。如果你还在用 `./configure && make`，新版本会直接劝退——configure 文件已经没了。这一篇把"用 Meson 把 PostgreSQL 17/18 源码变成可用二进制、跑全套回归测试"这件事**一行一行命令**说清楚。

读完本文你应该能在任何一个干净的 Linux 机器上：

- 用 Meson 配置 PostgreSQL（连安装目录、特性开关一起）
- 用 Ninja 编译整个项目
- 把结果安装到本地目录
- 跑全套 `regress` 测试、单测、TAP 测试
- 用一行命令跑指定的某个测试用例

---

## 一、为什么 PostgreSQL 要换 Meson？

autotools 有两个老毛病：

1. **太慢**：`./configure` 在大型项目里要扫遍系统环境，慢得像老牛车。
2. **跨平台差**：Windows 上 MinGW + MSYS 的体验非常糟糕，PG 维护者长期需要 `src/template/win32`、`src/template/win32.meson` 等多套配置。

Meson 的卖点：

| 维度 | autotools | Meson |
| --- | --- | --- |
| 配置速度 | 慢（全跑） | 快（只跑一次） |
| 跨平台原生支持 | 弱 | 强 |
| 内置测试框架 | 没有 | `meson test` TAP 协议 |
| 子项目 / 预编译依赖 | 弱 | 一流（wrap） |
| 配置重运行 | 需要再次 `./configure` | 自动 |
| 语言 | m4 宏（劝退） | Python 风格 DSL |

对 PG 这种"在 Linux/macOS/Windows/AIX 上都要跑"的项目来说，Meson 的**跨平台一致性**是决定因素。

> Meson 是"配置器"，真正干活的是后端的 **Ninja**（PG 默认）——所以你会看到 `ninja -C build` 也能直接用，但本文全部走 `meson compile`/`meson test` 等高阶命令。

---

## 二、安装依赖与工具链

### 2.1 系统包（Debian/Ubuntu）

```bash
sudo apt update
sudo apt install -y \
    build-essential \
    ninja-build \
    pkg-config \
    python3 \
    perl \
    bison \
    flex \
    libreadline-dev \
    zlib1g-dev \
    libicu-dev \
    libssl-dev \
    libldap2-dev \
    libpam0g-dev \
    libxml2-dev \
    libxslt1-dev \
    liblz4-dev \
    libzstd-dev \
    libcurl4-openssl-dev
```

### 2.2 系统包（RHEL/CentOS/Fedora）

```bash
sudo dnf install -y \
    gcc make ninja-build pkgconfig \
    python3 perl bison flex \
    readline-devel zlib-devel libicu-devel openssl-devel \
    openldap-devel pam-devel libxml2-devel libxslt-devel \
    lz4-devel libzstd-devel libcurl-devel
```

### 2.3 装 Meson

Meson 要求 **>= 0.54**，PG18 源码注释里这么写：

```
# meson.build 顶端
meson_version: '>=0.54',
```

推荐装 **1.3.0 以上**（新版对 Ninja msvc backend 支持更好）：

```bash
# 三选一
pip3 install --user meson        # Python 安装，推荐
sudo apt install meson           # Debian 12+ 系统包
brew install meson               # macOS

# 验证
meson --version
# 输出形如：1.7.0
```

### 2.4 拉源码

```bash
git clone https://github.com/postgres/postgres.git ~/cwork/postgresql
cd ~/cwork/postgresql
git checkout REL_18_STABLE        # 或 REL_17_STABLE、master
git log -1 --oneline              # 看下头指针
```

---

## 三、Meson 配置 PostgreSQL

### 3.1 最小化配置

```bash
meson setup build
```

这条命令在 `~/cwork/postgresql` 下创建一个叫 `build/` 的目录，里面放着所有 Ninja 文件和最终产物。`meson.build` 在仓库根，所以不需要 `cd` 到别处。

`build/` 长什么样：

```text
build/
├── build.ninja              ← Ninja 的入口
├── meson-info/              ← Meson 元数据
│   ├── intro-buildoptions.json
│   ├── intro-projectinfo.json
│   └── ...
├── meson-private/           ← 私有缓存
└── src/                     ← 各子目录的实际 build.ninja
```

> ⚠️ **永远不要把 `build/` 提交到 git**。把 `build/` 加进 `.gitignore`。

### 3.2 指定安装前缀

```bash
# 装到 /usr/local/pgsql（PG 默认行为）
meson setup build --prefix=/usr/local/pgsql

# 装到当前目录的 install/ 子目录里（推荐：无需 root）
meson setup build --prefix=$PWD/install

# 装到自定义路径，便于多版本共存
meson setup build --prefix=$HOME/pg-dev/18
```

源码注释里默认 `prefix=/usr/local/pgsql`，但实际开发时基本都装到用户目录。

### 3.3 改配置（再跑一次 setup）

```bash
# 想加一个编译选项？直接再 setup 一次，meson 会增量更新
meson configure build -Dcassert=true

# 想看所有可用选项
meson configure build

# 想看某个选项的帮助
meson configure build -Dpgport
```

`meson configure` 等价于旧的 `./configure && make distclean`，但**不会清掉已经编译好的对象**——这正是 Meson 的爽点。

### 3.4 最常用的 PG 专属选项

源码 `meson_options.txt` 给出所有选项，下面是开发期最常用的几条：

```bash
meson setup build \
    --prefix=$PWD/install \
    -Dcassert=true \                # 启用断言检查（开发期必开）
    -Ddebug=true \                  # -O0 调试构建
    -Dtap_tests=enabled \           # 跑全套 TAP 测试
    -Dpgport=54329 \               # 改默认端口（避免与本地 PG 冲突）
    -Dextra_version=-dev.local     # pg_version 后缀，便于区分
```

每个选项的语义：

| 选项 | 默认 | 作用 |
| --- | --- | --- |
| `-Dcassert` | false | 编译进 `USE_ASSERT_CHECKING`，慢但能抓 bug |
| `-Ddebug` | false | `-O0 -g`，配合 gdb 调试 |
| `-Dtap_tests` | auto | 启用 TAP 协议输出（CI 必备） |
| `-Dpgport` | 5432 | `postgres` 默认端口 |
| `-Dicu` | auto | ICU 库（locale 排序、Unicode） |
| `-Dldap` | auto | LDAP 认证 |
| `-Dssl` | auto | OpenSSL（默认开） |
| `-Dlibcurl` | auto | 用于 pg_basebackup 等 |
| `-Dgssapi` | auto | GSSAPI/Kerberos 认证 |
| `-Dextra_version` | "" | 拼到 `PG_VERSION` 后的字符串 |
| `-Ddocs` | auto | 编译 SGML 文档（需要 docbook） |
| `-Dprefix` | /usr/local/pgsql | 安装前缀 |

> Tip：`meson configure build -Doption=value` 也可以只改一项，不用全列。

### 3.5 一次配置 vs 多次重配置

```text
meson setup build --prefix=/tmp/pg         ← 第一次：生成 build.ninja
meson configure build -Dcassert=true       ← 之后：增量更新配置
meson configure build -Dpgport=5433        ← 又改一项
```

`meson configure` 不会重编译，只重新生成 Ninja 文件。要"从头再来"就 `rm -rf build && meson setup build`。

---

## 四、编译

### 4.1 全量编译

```bash
# 官方推荐写法
meson compile -C build

# 等价的老写法
ninja -C build
```

`-j` 控制并行度（默认用所有核）：

```bash
meson compile -C build -j8
```

> MacBook Air M2 跑 PG 18 大概 3~5 分钟；普通 x86 服务器几十秒到一两分钟。

### 4.2 单独编译某个子项目

PG 把目标分成几组，根 `meson.build` 给出了若干"伪目标"（alias）：

```text
backend       ← 服务端可执行文件（postgres 等）
bin           ← 客户端二进制（psql, pg_dump ...）
pl            ← 过程语言（plpgsql.so 等）
contrib       ← contrib 模块
src/test/...  ← 测试可执行文件
```

单独编译这些：

```bash
meson compile -C build backend           # 只编后端
meson compile -C build bin               # 只编客户端
meson compile -C build contrib           # 只编 contrib
meson compile -C build pl                 # 只编 PL/pgSQL 等
```

### 4.3 只编译某个 target

```bash
# 只编译 postgres 服务端
meson compile -C build src/backend/postgres

# 只编译 psql
meson compile -C build src/bin/psql/psql

# 只编译 plpgsql.so
meson compile -C build src/pl/plpgsql/src/plpgsql.so
```

### 4.4 清理与重编译

```bash
meson compile -C build --clean           # 删所有对象，保留配置
rm -rf build                             # 彻底重来（含配置）
```

---

## 五、安装到本地目录

### 5.1 全量安装

```bash
meson install -C build
```

默认装到 `build/` 目录本身（不是 `--prefix` 指定的路径）！这是因为 meson install 在配置时把 `DESTDIR` 默认到 build 目录。

要装到 `--prefix` 指定的真实路径：

```bash
DESTDIR= meson install -C build
```

或者直接：

```bash
meson install -C build --destdir=
```

不过最常用的还是装到 `$PWD/install` 之类的临时目录：

```bash
meson setup build --prefix=/usr/local/pgsql   # 真正的安装路径
sudo meson install -C build                    # 需要 root 写到 /usr/local
```

### 5.2 看装到哪里

```bash
meson introspect --installed -C build | head -20
```

输出类似：

```
usr/local/pgsql/bin/postgres
usr/local/pgsql/bin/psql
usr/local/pgsql/bin/pg_dump
usr/local/pgsql/lib/libpq.so.5
usr/local/pgsql/include/postgresql/libpq-fe.h
usr/local/pgsql/share/postgresql/extension/plpgsql.control
...
```

### 5.3 加进环境变量

```bash
export PATH=$PWD/install/bin:$PATH
export LD_LIBRARY_PATH=$PWD/install/lib:$LD_LIBRARY_PATH    # Linux
export DYLD_LIBRARY_PATH=$PWD/install/lib:$DYLD_LIBRARY_PATH  # macOS
export PGDATA=$PWD/data

# 验证
which postgres
postgres --version
```

### 5.4 启动一个临时实例

```bash
# 初始化
initdb -D $PGDATA -E UTF8 --locale=C

# 启动
pg_ctl -D $PGDATA -l $PGDATA/server.log start

# 连一下
psql -d postgres -c "SELECT version();"

# 关闭
pg_ctl -D $PGDATA stop
```

---

## 六、回归测试：核心

PG 的回归测试一共有三类：

```text
src/test/regress/    ← pg_regress 跑的传统测试（最核心）
src/test/isolation/  ← 测试 SSI / 隔离级别
src/test/*/t/*.pl    ← TAP 协议测试（Perl 写的）
src/test/modules/    ← contrib 模块的测试
```

Meson 把这些都集成进了 `meson test`，统一接口。

### 6.1 准备阶段（必须先跑）

回归测试要在 **临时安装的二进制** 上跑（不能直接用 `build/` 里的产物），所以 Meson 提供了一个"tmp_install" setup：

```bash
# 安装到 build/tmp_install/（一个临时目录）
meson test -C build --setup=tmp_install setup:tmp_install

# 这一步把整个 PG 装到 build/tmp_install/usr/local/pgsql/
```

输出类似：

```text
setup:tmp_install                    OK   32.10s
```

> 这一步不在测试列表的"普通"位置（`priority: setup_tests_priority = 100`），但 `meson test` 默认会自动跑依赖它的所有测试。

### 6.2 跑全套回归测试（regress 套件）

```bash
# 跑全套回归测试（默认 setup=tmp_install）
meson test -C build --suite=regress
```

`--suite=regress` 会匹配所有 `suite: ['regress']` 的测试，等价于：

```bash
meson test -C build 'src/test/regress/regress'
```

跑完输出：

```text
1/1 src/test/regress/regress         OK   84.30s
```

> **84 秒**——这就是 PG 17/18 全套回归测试的时间。包含 200+ 个 `.sql` 测试文件，并发 20 个跑。

### 6.3 跑全部测试（包括 isolation、TAP、contrib）

```bash
# 全跑（耗时很长，几十套测试一起）
meson test -C build
```

测试矩阵速览：

```text
suite: setup          ← tmp_install, install_test_files, initdb_cache
suite: regress        ← src/test/regress（核心）
suite: isolation      ← src/test/isolation
suite: modules/*      ← contrib 模块的 regress
suite: plpgsql        ← plpgsql 测试
suite: subscription   ← 逻辑复制测试
suite: recovery       ← 崩溃恢复测试
suite: authentication ← 认证
suite: ldap, kerberos, ssl ← 各种扩展认证
suite: mb             ← 多字节字符集
suite: locale         ← locale
suite: icu            ← ICU
... 加起来 60+ 个 suite
```

### 6.4 跑单个测试 / 单个文件

```bash
# 跑 src/test/regress 整套（200+ 文件）
meson test -C build regress/regress

# 用 --suite 只跑某一种
meson test -C build --suite=isolation

# 跑 src/test/regress 下的具体文件？
# Meson 测试是 "整个 schedule" 为粒度的，不是单个 .sql 文件
# 想跑单个 .sql 文件，得直接调 pg_regress
```

### 6.5 深入到 pg_regress（直接调用）

`pg_regress` 是 PG 的回归测试驱动，Meson 把它也编译出来了：

```bash
PG_REGRESS=$PWD/build/src/test/regress/pg_regress

# 跑几个指定文件
$PG_REGRESS \
    --inputdir=$PWD/src/test/regress \
    --bindir=$PWD/build/tmp_install/usr/local/pgsql/bin \
    --dlpath=$PWD/build/src/test/regress \
    --max-concurrent-tests=20 \
    --schedule=$PWD/src/test/regress/serial_schedule \
    boolean int4 int8
```

参数说明：

| 参数 | 作用 |
| --- | --- |
| `--inputdir` | 测试用例 `.sql` 和 `expected/` 的目录 |
| `--bindir` | 用哪份二进制（必须是 tmp_install 里的） |
| `--dlpath` | 共享库搜索路径 |
| `--schedule` | 用串行还是并行的调度 |
| `--port` | 测试实例端口 |
| `--use-existing` | 跑 `installcheck` 模式，对已运行的实例 |
| `--dbname` | 默认数据库名 |

### 6.6 跑 installcheck（对已运行实例）

`make installcheck` 时代的老接口，对应 Meson 里的 `running` setup：

```bash
# 先确保 PG 已在跑
pg_ctl -D $PGDATA start

# 跑全套 regress，对这个正在运行的实例
meson test -C build --setup=running --suite=regress
```

> `running` setup 不创建临时实例，直接用 `localhost:5432` 上那个。所以你的 `pg_hba.conf` 要允许 trust 或 peer 认证，`postgresql.conf` 要打开足够日志。

### 6.7 跑 TAP 测试

```bash
# 跑某一个 TAP 测试
meson test -C build --suite=authentication

# 跑某个 TAP 测试的某一个 .pl
meson test -C build 'src/test/authentication/t/001_password'

# 列出所有 TAP 测试
meson test -C build --list | grep '\.pl\|tap'
```

`pg_regress` 协议和 TAP 协议是两个东西：

| 协议 | 工具 | 适用 |
| --- | --- | --- |
| `pg_regress` | C 写的驱动 | .sql + .out 期望文件 |
| `tap` | Perl `pg_regress` 兼容 | .pl Perl 测试 |

### 6.8 详细输出与失败排查

```bash
# 跑全套 regress 并打印详细输出
meson test -C build regress/regress -v

# 失败时打印 stdout/stderr
meson test -C build regress/regress --print-errorlogs

# 失败时停在第一个失败（不停下也行，加 --max-fail=1）
meson test -C build --max-fail=1

# 跑完之后看 log
ls build/testrun/regress/
cat build/testrun/regress/regress/regression.diffs
cat build/testrun/regress/regress/log/postmaster.log
```

测试产物的目录结构：

```text
build/testrun/
└── regress/
    └── regress/                       ← 测试名 suite/test
        ├── log/                       ← PG 服务器日志
        │   ├── postmaster.log
        │   └── ...
        ├── regression.diffs           ← 实际输出 vs 期望 diff
        ├── regression.out             ← 实际输出
        └── tmp_check/                 ← 临时实例（每个测试一个目录）
```

### 6.9 跑两次、改一行再跑

PG 改源码后想快速验证：

```bash
# 1) 改代码
vim src/backend/executor/nodeSeqscan.c

# 2) 只重编译
meson compile -C build backend

# 3) 重装到临时目录（增量）
meson test -C build --setup=tmp_install setup:tmp_install

# 4) 跑受影响的测试
meson test -C build regress/regress -v
```

`setup:tmp_install` 默认是 `--only-changed --no-rebuild`，所以很快。

### 6.10 性能 / 覆盖率 / 调试选项

```bash
# 带性能分析（callgrind）
meson configure build -Dbuildtype=debugoptimized   # 默认
meson configure build -Dbuildtype=debug             # -O0
meson configure build -Dbuildtype=release           # -O3，无调试信息

# 覆盖率（GCC）
meson configure build -Db_coverage=true
meson compile -C build
# 跑测试后 gcov/lcov
```

---

## 七、完整端到端示例（从零到回归通过）

把上面串成一个脚本，照抄即可：

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── 0) 拉源码 ─────────────────────────────
git clone https://github.com/postgres/postgres.git ~/cwork/pg-build
cd ~/cwork/pg-build
git checkout REL_18_STABLE

# ── 1) Meson 配置 ─────────────────────────
meson setup build \
    --prefix=$PWD/install \
    -Dcassert=true \
    -Dtap_tests=enabled \
    -Dpgport=54329 \
    -Dextra_version=-dev.local

# ── 2) 编译 ───────────────────────────────
meson compile -C build -j$(nproc)

# ── 3) 跑回归测试 ─────────────────────────
meson test -C build --suite=regress

# ── 4) 装到本地 prefix ────────────────────
DESTDIR= meson install -C build

# ── 5) 启动临时实例 ───────────────────────
export PATH=$PWD/install/bin:$PATH
export LD_LIBRARY_PATH=$PWD/install/lib:$LD_LIBRARY_PATH
export PGDATA=$PWD/data
initdb -D $PGDATA -E UTF8 --locale=C
pg_ctl -D $PGDATA -l $PGDATA/server.log start
psql -d postgres -c "SELECT version();"

# ── 6) 改天再回来用 ───────────────────────
cd ~/cwork/pg-build
export PATH=$PWD/install/bin:$PATH
export LD_LIBRARY_PATH=$PWD/install/lib:$LD_LIBRARY_PATH
export PGDATA=$PWD/data
pg_ctl -D $PGDATA start

# ── 7) 跑全套 TAP + isolation ─────────────
meson test -C build --suite=isolation
meson test -C build --suite=plpgsql
meson test -C build --suite=modules
```

---

## 八、常见坑与排错

### 8.1 "ERROR: Could not find Bison"

```text
meson setup build
ERROR: Program 'bison' not found or not usable
```

解决：装 bison，PG 17+ 要求 bison >= 2.3。

```bash
sudo apt install bison flex
```

### 8.2 "Cannot find ICU"

```bash
# 显式禁用
meson configure build -Dicu=disabled

# 或者装上
sudo apt install libicu-dev
meson setup build --reconfigure
```

### 8.3 端口冲突

```bash
# 改 PG 默认端口（编译时）
meson configure build -Dpgport=54329

# 改测试用端口（运行时）
# Meson 自动从 40000 起给每个测试分配不同端口
# 但如果你本机已有 PG 在 5432，tmp_install 默认会用 5432
```

### 8.4 测试失败但不知道哪里出问题

```bash
# 跑单个失败测试并打印日志
meson test -C build regress/regress -v --print-errorlogs

# 看 log
cat build/testrun/regress/regress/log/postmaster.log | tail -50

# 看 diff
cat build/testrun/regress/regress/regression.diffs | head -100
```

### 8.5 "libpq.so not found"

```bash
export LD_LIBRARY_PATH=$PWD/install/lib:$LD_LIBRARY_PATH    # Linux
export DYLD_LIBRARY_PATH=$PWD/install/lib:$DYLD_LIBRARY_PATH # macOS
```

### 8.6 想清空重新配置

```bash
rm -rf build
meson setup build -Dcassert=true
meson compile -C build
```

### 8.7 autotools 的等价命令速查

| 你想做的 | autotools 老命令 | Meson 新命令 |
| --- | --- | --- |
| 配置 | `./configure --prefix=...` | `meson setup build --prefix=...` |
| 改配置 | `make distclean && ./configure` | `meson configure build -Dxxx=yyy` |
| 编译 | `make -j` | `meson compile -C build -j` |
| 安装 | `make install` | `meson install -C build` |
| 跑全套回归 | `make check-world` | `meson test -C build` |
| 跑 regress | `make check` | `meson test -C build --suite=regress` |
| 跑 installcheck | `make installcheck` | `meson test -C build --setup=running --suite=regress` |
| 清理 | `make clean` | `meson compile -C build --clean` |
| 彻底清理 | `make distclean` | `rm -rf build` |

---

## 九、CI 里的推荐配置

如果你要在 CI 里跑，可以直接用 GitHub Actions 里的 **postgres/postgres** 仓库那个 `cirrus.yml` 的策略：

```yaml
# .github/workflows/postgres-build.yml 示例
name: PG build & test
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: sudo apt install -y bison flex libicu-dev libssl-dev ...

      - name: Meson configure
        run: |
          meson setup build \
            --prefix=$PWD/install \
            -Dcassert=true \
            -Dtap_tests=enabled

      - name: Compile
        run: meson compile -C build -j$(nproc)

      - name: Test
        run: meson test -C build --suite=regress --print-errorlogs

      - name: Test TAP
        run: meson test -C build --print-errorlogs
        continue-on-error: false
```

---

## 十、总结

PostgreSQL 16+ 用 Meson 替换 autotools 不是"为了赶时髦"，而是**为了让构建系统跟上 21 世纪**。从开发者角度，最大的好处是：

- **`meson configure` 增量更新**配置，不再 `make distclean`。
- **`meson test`** 把 regress、isolation、TAP、contrib 全统一到一个命令。
- **`meson introspect`** 直接看到所有可执行文件、库、选项——调试神器。
- **跨平台一致性**——Linux/macOS/Windows 用同一套命令。

把这一篇的命令序列存成脚本，下次改 PG 源码就能一键从 clone 到测试通过：

```bash
# 一键脚本骨架
git clone https://github.com/postgres/postgres.git && cd postgres && \
    meson setup build --prefix=$PWD/install -Dcassert=true && \
    meson compile -C build -j$(nproc) && \
    meson test -C build --suite=regress
```

等你需要做更深入的修改（比如改 hash join 的实现），就会发现 meson 比 autotools 快太多了——尤其是当你每天改 30 次代码、跑 30 次测试的时候。

---

## 参考资料

- PostgreSQL 18 dev 源码：
  - `meson.build` — 构建入口
  - `meson_options.txt` — 全部可配置选项
  - `src/test/regress/meson.build` — regress 测试定义
  - `src/test/regress/parallel_schedule` — 并行调度文件
- Meson 官方文档：https://mesonbuild.com/
- PostgreSQL 官方 wiki 迁移指南：https://wiki.postgresql.org/wiki/Meson

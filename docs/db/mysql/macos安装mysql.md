# 安装mysql

```shell
brew install mysql@8.4
```text
```shell
we've installed your MySQL database without a root password. To secure it run:
    mysql_secure_installation

MySQL is configured to only allow connections from localhost by default

To connect run:
    mysql -u root

To start mysql@8.4 now and restart at login:
  brew services start mysql@8.4
Or, if you don't want/need a background service you can just run:
  /opt/homebrew/opt/mysql@8.4/bin/mysqld_safe --datadir\=/opt/homebrew/var/mysql
==> Summary
🍺  /opt/homebrew/Cellar/mysql@8.4/8.4.8_2: 321 files, 315.2MB
==> Running `brew cleanup mysql@8.4`...
Disable this behaviour by setting `HOMEBREW_NO_INSTALL_CLEANUP=1`.
Hide these hints with `HOMEBREW_NO_ENV_HINTS=1` (see `man brew`).
==> Caveats
==> mysql@8.4
We've installed your MySQL database without a root password. To secure it run:
    mysql_secure_installation

MySQL is configured to only allow connections from localhost by default

To connect run:
    mysql -u root

To start mysql@8.4 now and restart at login:
  brew services start mysql@8.4
Or, if you don't want/need a background service you can just run:
  /opt/homebrew/opt/mysql@8.4/bin/mysqld_safe --datadir\=/opt/homebrew/var/mysql
```text
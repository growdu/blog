# python跨平台下载离线安装包

以allure-pytest为例

```shell
pip download -d ./ allure-pytest --only-binary=:all: --platform linux_x86_64 --trusted-host pypi.douban.com
cd allure-pytest
ls -l | awk '{print $9}'>> requirements.txt
```

将allure-pytest拷贝到目标机器上，在目标机器上执行：

```shell
pip install --no-index --find-links=./ -r requirements.txt
```
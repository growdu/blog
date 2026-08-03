# texlive安装

## 下载iso包

```shell
wget https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/Images/texlive2023-20230313.iso
```text
## 挂载iso

```shell
mount texlive2023-20230313.iso /mnt
```text
## 下载texlive

```shell
cd /mnt
./install-tl
```text
## 配置环境变量
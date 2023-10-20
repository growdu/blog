# texlive安装

## 下载iso包

```shell
wget https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/Images/texlive2023-20230313.iso
```

## 挂载iso

```shell
mount texlive2023-20230313.iso /mnt
```

## 下载texlive

```shell
cd /mnt
./install-tl
```

## 配置环境变量
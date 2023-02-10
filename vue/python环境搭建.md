# python环境搭建

## 下载anaconda

## 使用conda搭建各版本python环境

```shell
conda env list # 列出环境
conda create -n py37 python=3.7 # 创建python3.7环境
conda activate py37 # 激活python3.7环境
pip install pipenv # 下载pipenv
pipenv shell # 激活一个pipenv
pip install django #下载django
```

## django使用

```shell
django-admin startproject test_web # 创建项目
cd test_web
python manage.py runserver #运行项目
python manage.py startapp app1 # 创建app1
```


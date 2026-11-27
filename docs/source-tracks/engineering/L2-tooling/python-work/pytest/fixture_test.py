#!/usr/bin/python
# -*- coding: utf-8 -*-
import pytest

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
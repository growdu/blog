#!/usr/bin/python
# -*- coding: utf-8 -*-
import os

from numpy import equal

def write_index(path, num):
    num = num + 1
    allfilelist=os.listdir(path)
    for f in allfilelist:
        f = os.path.join(path, f)
        #判断是不是文件夹
        if os.path.isdir(f):
            temp = "\n"
            for n in range(num):
                temp = temp + "#"
            temp = temp + " " + os.path.basename(f) + "\n"
            if (path != "." and path != "..") :
                file.write(temp)
            write_index(f, num)
        else: 
            temp = "- " + "[" + os.path.basename(f).split('.')[0] + "]" + "(" + f + ")" + "\n"
            temp = temp.replace("\\", "/")
            file.write(temp)

filepath = "readme.md"
# 判断文件是否存在
if (os.path.exists(filepath)) :
	#存在，则删除文件
	os.remove(filepath)

file = open(filepath,'a')
file.write("# growdu's blog\n")
write_index("..", 0)
file.close()
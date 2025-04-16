#!/usr/bin/python
# -*- coding: utf-8 -*-
import yaml

with open("list.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("list.yaml list is:")
    for d in data:
        print(d)
    
with open("dict.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("dict.yaml list is:")
    for d in data:
        #print(d)
        print("name is " + d['name'] + ", age is " + str(d['age']))
        
with open("dict_list.yaml", encoding="utf-8") as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    print("dict_list.yaml list is:")
    print("name list is:")
    for d in data['name']:
        #print(d)
        print(d)
    print("course list is:")
    for d in data['course']:
        #print(d)
        print(d)
    
# -*- coding:UTF-8 -*-
import requests
 
if __name__ == '__main__':
    target = "http://fanyi.baidu.com/"
    req = requests.get(url = target)
    req.encoding = 'utf-8'
    print(req.text)
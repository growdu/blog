# -*- coding: UTF-8 -*-
from urllib import request
from urllib import parse
from fake_useragent import UserAgent

if __name__ == "__main__":
    ua=UserAgent()
    #请求头
    headers={"User-Agent":ua.random}
    #对应上图的Request URL
    Request_URL = 'http://fanyi.youdao.com/translate?smartresult=dict&smartresult=rule&smartresult=ugc&sessionFrom=https://www.baidu.com/link'
    #创建Form_Data字典，存储上图的Form Data
    Form_Data = {}
    Form_Data['type'] = 'AUTO'
    Form_Data['i'] = 'Jack'
    Form_Data['doctype'] = 'json'
    Form_Data['xmlVersion'] = '1.8'
    Form_Data['keyfrom'] = 'fanyi.web'
    Form_Data['ue'] = 'ue:UTF-8'
    Form_Data['action'] = 'FY_BY_CLICKBUTTON'
    #使用urlencode方法转换标准格式l
    data = parse.urlencode(Form_Data).encode('utf-8')
    resp = request.Request(url=Request_URL, headers=headers)
    response = request.urlopen(resp,data=data)
    #读取信息并解码
    html = response.read().decode('utf-8')
    print(html)
    #with open("youdao.html","wb") as f: 
    #    f.write(html)
    #使用JSON
    #translate_results = json.loads(html)
    #找到翻译结果
    #translate_results = translate_results['translateResult'][0][0]['tgt']
    #打印翻译信息
    #print("翻译的结果是：%s" % translate_results)
import os

path='C:\\Users\\duanys\\Desktop\\test\\html'
for file in os.listdir(path):
    if file[-2: ]=='py':
        continue
    name=file.replace(' ','')
    newName=name[1: ]+'.html'
    os.rename(os.path.join(path,file),os.path.join(path,newName))
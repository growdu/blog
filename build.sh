#!/bin/bash
yarn run clear
yarn run build
cp build/ /work/code/jswork/oh-my-world/conf/dist/blog -r
tar -zcvf build.tar.gz build
scp build.tar.gz ubuntu@growdu.cn:/home/ubuntu/
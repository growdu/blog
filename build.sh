#!/bin/bash
yarn run clear
yarn run build
cp build/ /work/code/jswork/oh-my-world/conf/dist/blog -r

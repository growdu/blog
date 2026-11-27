#!/bin/bash
num1=4;
num2=5;
let result=num1+num2;
echo "num1=$num1"
echo "num2=$num2"
# count by let
echo "num1+num2=$result count by let"
let num1++
echo "num1++=$num1"
# count by [  ]
result=$[ num1+num2 ]
echo "num1+num2=$result count by [  ]"
#let and [  ]only count integer
#use bc to count float number
result=`echo "sqrt(100)" | bc`
echo $result

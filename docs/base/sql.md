# sql总结

## union 与union all

结论：union all的性能大约是union的好几倍。

union在进行表链接后会筛选掉重复的记录，所以在表链接后会对所产生的结果集进行排序运算，删除重复的记录再返回结果。

```sql
select * from test_union1    
	  union  
select * from test_union2
```

这个SQL在运行时先取出两个表的结果，再用排序空间进行排序删除重复的记录，最后返回结果集，如果表数据量大的话可能会导致用磁盘进行排序。

 而union all只是简单的将两个结果合并后就返回。这样，如果返回的两个结果集中有重复的数据，那么返回的结果集就会包含重复的数据了。

 使用 union 组合查询的结果集有两个最基本的规则：  
 
 1.所有查询中的列数和列的顺序必须相同。  
 
 2.数据类型必须兼容

## select 0

 当我们只关心数据表有多少记录行而不需要知道具体的字段值时，类似“select 1 from tblName”是一个很不错的SQL语句写法，它通常用于子查询。
 
 这样可以减少系统开销，提高运行效率，因为这样子写的SQL语句，数据库引擎就不会去检索数据表里一条条具体的记录和每条记录里一个个具体的字段值并将它们放到内存里，而是根据查询到有多少行存在就输出多少个“1”，每个“1”代表有1行记录，同时选用数字1还因为它所占用的内存空间最小，当然用数字0的效果也一样。在不需要知道具体的记录值是什么的情况下这种写法无疑更加可取。

 ```sql
 --常规写法
select class,count (*) as pax from students 
 group by class;

 --select 0

select class,count (1) as pax from students 
group by class;
 ```

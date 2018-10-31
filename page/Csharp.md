# Csharp计算线程运行时间

# C#操作数据库进行增删改查

#  sender

sender最终会被转换为触发该事件的控件。

eg：

```C#
private void Button_Click(object sender, RoutedEventArgs e)
{
    //……blahblahblah
}
```

在上例中sender就是button按钮，类型是object，后续将sender就行类型转换就可以得到button，进而对button的属性进行修改。

object是事件的激发控件，或叫事件源。

e是事件参数，也就是说定义事件的类里。

```
Button button=sender as Button;
//其他控件与此类似
```

当有多个控件需要触发相同的事件时，使用sender来获取当前触发事件的控件，可以在同一个方法中进行事件的响应，能够使代码的重用性提高，也能更简洁，eg：

```C#
private void btnObj1_Click(object sender, RoutedEventArgs e)
        {
            Button btn = (Button)sender;
            if(btn == btnObj1)
            {
                MessageBox.Show("Btn1 被点击了");
            }
            else
            {
                MessageBox.Show("Btn2 被点击了");
            }
        }
```

# event and delegate

delegate可以理解为C语言中的函数指针。

C#中的事件处理实际上是一种具有特殊签名的delegate。

eg：

```
//sender代表事件发送者，e是事件参数类
public delegate void MyEventHandler(object sender, MyEventArgs e);
```
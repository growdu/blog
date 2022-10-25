# tcp_user_timeout与keepalive的关系与生效机制

## tcp未进入keepalive

当tcp流中有数据交互时，tcp流不会进入keepalive，此时的超时主要受tcp_user_timeout。数据包被发送后未接收到ACK确认的达到tcp_user_timeout时，以毫秒为单位，例如设置为10000时，代表如果发送出去的数据包在十秒内未收到ACK确认，则下一次调用send或者recv，则函数会返回-1，errno设置为ETIMEOUT。

## tcp 进入keepalive

tcp_keep_alive和tcp_user_timeout的生效机制：

1. 由tcp_keepalive_idle 设置的时长控制进入keep-alive；
2. 当进入keep-alive后，若未收到keep-alive-ack，将由tcp_keepalive_interval 设置的时长控制keep-alive的重传；若收到keep-alive-ack，由tcp_keepalives_idle 设置的时长控制下一次发送keep-alive；
3. 由tcp_keepalives_count 控制未收到多少个keep-alive-ack时进行拆链；但tcp_keepalives_interval *tcp_keepalives_count > tcp_user_timeout时，未收到多少个keep-alive-ack的时间达到tcp_user_timeout则立马拆链（RST）；
4. 当未收到keep-alive-ack时，何时拆链，由tcp_keepalives_interval *tcp_keepalives_count和tcp_user_timeout的较小值来确定。
# ptpclient

## 功能实现

- 仅支持slaver
- 仅支持E2E
- 仅支持做oc
- 不支持BMC算法，使用第一个发现的master作为主时钟

## 基站设备功能要求

- 应支持OC，可选支持BC
- 支持BMC状态信息提取，但不强制要求支持状态决策算法和选源算法
- 基站设备应支持PTP端口应可设置为Enable和Disable，并应可配置Slave_Only功能使能和不使能
- PTP报文封装应支持PTP over IEEE Std 802.3/Ethernet方式，可选支持 PTP over UDP over IPv4方式，可选支持VLAN功能
- 支持组播，单播可选支持
- 支持one-step模式，two-step模式可选
- 支持支持E2E延时机制，P2P延时机制可选
- 支持时延不对称补偿设置功能，补偿范围+/-100us，补偿步长不大于10ns

## 完整功能

- 支持master和slaver
- 支持oc、bc、tc
- 支持E2E和P2P
- 支持完整BMC算法（状态决策算法、选源算法）
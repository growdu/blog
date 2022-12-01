# vpp开发指南

vpp二次开发一般都是基于vpp框架进行插件开发。具体友包含以下几个方面：

- 配置
- 插入节点
- 收包
- 发包

## 配置

```c
// sample_config是配置读取函数
// sample是startup.conf文件中的模块名字
VLIB_CONFIG_FUNCTION (sample_config, "sample");
// 读取完配置后可以使用sample_init来进行初始化
VLIB_INIT_FUNCTION(sample_init);
```

## 插入节点

```c
// 注册一个名为sample_node的节点
VLIB_REGISTER_NODE (sample_node);
// sample_node收到报文后如何处理
VLIB_NODE_FN (sample_node) (vlib_main_t * vm, vlib_node_runtime_t * node,
				vlib_frame_t * f);
```

## 收包

收包插入一个收包节点，组织节点关系即可。

- L1

  ```c
  vnet_hw_interface_rx_redirect_to_node (vnet_main_t *vnm, u32 hw_if_index, u32 node_index);
  ```

- L2、L3

  ```c
  ethernet_register_input_type (vlib_main_t *vm, ethernet_type_t type, u32 node_index);
  ```

- L4

  ```c
  ip4_register_protocol (u32 protocol, u32 node_index);
  ```

- L5

  ```c
  udp_register_dst_port (vlib_main_t * vm, udp_dst_port_t dst_port, u32 node_index, u8 is_ip4);
  ```

## 发包

发包插入一个发包节点，组织节点关系即可。

## 命令下发

注册cli命令，进而可以在vppctl中对vpp流程进行控制。

```c
VLIB_CLI_COMMAND (sample_node, static) = {
  .path = "sample",
  .function = sample,
  .short_help = "sample",
};
```


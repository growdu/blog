# samba服务深度定制

## 修改smaba服务默认端口

在 Windows 7 中，您可以通过修改注册表来指定 Samba 服务器的端口。

请注意，修改注册表可能会导致系统不稳定，因此请谨慎操作。建议您在修改注册表之前备份注册表。

要修改注册表，请按照以下步骤操作：

1. 单击“开始”按钮，然后输入“regedit”。
2. 按下回车键。
3. 导航到以下注册表项：

```
HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters
netsh interface ipv4 set portproxy protocol=tcp listenport=445 listenaddress=0.0.0.0 connectport=445 connectaddress=127.0.0.1
netsh interface ipv4 set portproxy protocol=tcp listenport=139 listenaddress=0.0.0.0 connectport=139 connectaddress=127.0.0.1
netsh interface portproxy add v4tov4 listenport=3000 connectaddress=192.168.1.100 connectport=445
netsh interface portproxy add v4tov4 listenport=3000 connectaddress=192.168.10.200 connectport=445

```

4. 在右侧窗格中，找到名为“SmbPort”的 DWORD 值。
5. 双击“SmbPort”值。
6. 在“数值数据”字段中，输入您要使用的端口号。
7. 单击“确定”。
8. 关闭注册表编辑器。

现在，您应该能够使用指定的端口访问 Samba 共享。

请注意，您还需要在 Samba 服务器上配置相应的端口。具体配置方法取决于您使用的 Samba 版本。

以下是一些常见 Samba 版本的端口配置方法：

* **Samba 4：**

```
[global]
    port = 445
```

* **Samba 3：**

```
[global]
    smb ports = 445
```

请将 `445` 替换为您要使用的端口号。

希望这些信息对您有所帮助。
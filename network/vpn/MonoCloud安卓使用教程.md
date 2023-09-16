#### Clash

 **在设置前请确保您已经在控制面板中设置好了登陆客户端所使用的用户名和密码**

设置步骤

1.  在手机上下载并安装 Clash 代理客户端
    
    [Clash For Android](https://storage.monocloud.co/client/Android/Clash/cfa-2.5.12-premium-arm64-v8a-release.apk)
    
    请注意，知识库内提供的客户端版本可能不是最新的，且我们只提供了 arm64-v8a 版本（适用于目前市面上的绝大多数 Android 设备），若上述客户端不适合您的手机使用或者我们提供的文件版本较旧您需要更新的版本，可以在 Clash For Android 官方项目页内找到最新的最全版本的安装包：[Clash For Android Github](https://github.com/Kr328/ClashForAndroid/releases)
    
2.  **请确保您已经在控制面板中「设置登录信息」按钮设置****设置好了登陆客户端所使用的用户名和密码，之后再点击启用 Clash  
    **
    
    ![](https://storage.monocloud.co/image/Chrome/01.png)
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/01.png)
    
    **请注意：此处设置的登录信息是独立的，不需要也不允许设置为您官网注册账号的邮箱。**
    
3.  在上一步启用 Clash 之后，您会在页面上看到一个链接，请在手机上复制该链接，随后打开安装的 Clash 客户端，点击”配置“
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/02.png)
    
4.  在 Clash 的配置页面内，点击右上角的加号添加新配置**，**并选择从 URL 导入
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/03.png)
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/04.png)
    
5.  在 URL 处粘贴第三步中复制的 Clash 订阅链接，配置的名称和自动更新时间可以按照自己的需求配置
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/05.png)

    此处填入如下链接：

    ```shell
    https://mymonocloud.com/classic/865928/QphZPH9BJ98M
    ```
    
6.  确认无误之后，点击右上角的保存按钮
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/06.png)
    
7.  设置好之后，此时会回到添加配置文件的界面，点击刚刚添加好的配置并返回代理客户端主界面，点击已停止这里开启代理
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/07.png)
    
8.  成功开启之后的界面状态如下，如需关闭代理，只需点击”运行中“即可
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/08.png)
    
9.  如果您想要知道目前使用的是哪个代理节点，以及想更换代理节点的话，只需要点击 Clash 主界面第二项“代理”，在出现的列表中选择要使用的代理即可
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/09.png)
    
    ![](https://storage.monocloud.co/image/Android/Clash_Classic/10.png)
    
    **请注意：使用 Clash 时，由于节点无法和该客户端的测试功能很好的兼容，如延迟测试无法返回正常的数据还请不必太在意，尽量以实际测试体验为准。**
    

### Clash 客户端设置有关说明

#### 自启动

如需让 Clash 开机其启动，请在客户端“设置”→“应用”中开启自动重启功能，部分 Android 系统还需要在系统设置中打开始终开启的 VPN，具体为打开系统的“WLAN 和互联网”设置，切换到“VPN”选项，找到 Clash 客户端并点击旁边的设置按钮，点击打开“始终开启的 VPN”功能。

#### 禁止部分应用走代理通道

规则默认已经配置好国内 IP 及局域网 IP 走直连，国外 IP 走代理连接，如果您担心误判的话，可在 Clash 设置内点开“网络”选项，找到“访问控制模式”及“访问控制应用包列表”两项，将访问控制模式切换到“不允许已选择的应用”，同时在访问控制应用包列表中勾选不走代理通道的应用，勾选后的应用不通过代理通道进行连接。

您也可以通过调整访问控制模式来让仅勾选的应用走代理通道，但实际是否走代理还需要代理规则来判断。

**其它选项如您不了解有关设置且无特殊需求，我们不建议您进行任意更改，以免影响代理的正常使用。**
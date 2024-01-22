# 使用github作为docker镜像存储仓库

docker因为其便利性和隔离性已经成为日常开发中非常常见的技术，使用docker可以把我们的编译开发环境打包，在任何机器上只要把docker镜像来取下来运行，不需要重复搭建编译开发环境。

使用过docker的用户都知道，docker的镜像仓维护设计得跟代码维护类似，docker的很多命令与git的命令基本一致，比如pull、push、add、tag、commit，引入容器后，你会发现管理环境就像开发代码一样优雅。

在内网环境里，我们可以自己搭建公共镜像仓，并分享同步自己的开发环境镜像，大家一起使用，一人维护，全公司受益。

而在外网环境里，其实也有一些公共镜像仓库，我们期望能登录查看自己的镜像，切换到不同的机器时，我可以快速的拉取我的镜像环境，类似这样功能的公共镜像仓有dockerhub，不过很可惜，国内已被墙，无法访问，有梯子都不行。

那有没有什么替代方式呢？答案是肯定的。

我们说docker镜像管理就像是git管理代码一样优雅，那么作为git最流行的仓库网站github是否支持上传docker镜像仓呢？答案是支持，github的package支持上传docker镜像。

每个github用户有一个package，登录github后即可看到。而我们要上传自己的镜像到github呢，需要做如下几个操作：

- 登录github的docker镜像仓库（docker login）

```shell
# -u 后面跟github用户名
# -p 后面跟github的token，也可以不用token，用密码也行
docker login docker.pkg.github.com -u username -p token
```

当然docker.pkg.github.com一般不常用，常用的是ghcr.io，其登录方式类似

```shell
# username和token需要换成自己的
docker login ghcr.io -u username -p token
```

- 为自己的镜像添加tag（docker commit）

这里的tag有一定的规则在里面，其形式类似于这样：ghcr.io/username/repo_name/image_name:tag，比如我的实例如下：

```shell
docker commit -a "growdu" -m "add coder to sudoers,map hosts to solve can't visit github"  973641cea3f7 ghcr.io/growdu/oh-my-code/coder:v1.2
```

- 推送镜像到远程仓库（docker push）

到这里就可以把镜像上传，然后在其他机器拉取镜像开发了。

```shell
docker push ghcr.io/growdu/oh-my-code/coder:v1.2
```

- 拉取镜像进行开发（docker pull）

```shell
docker pull ghcr.io/growdu/oh-my-code/coder:v1.2
```
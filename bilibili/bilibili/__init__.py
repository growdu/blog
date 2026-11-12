"""B站 adapter。

两档：现在跑的是 `manual`（出包 + 人工上传），
`ARC_BASE` 权限开通后同一套代码改一档到 `api_publish`（直接投稿）。

本包与 `channels/` 平级、互不引用，也不 import 契约层或 `weixin/` 的包。
只读 `aiv/publish/<EP>.json`（这一期怎么自我介绍）与
`publish/capabilities/bilibili.toml`（平台认什么）。
"""

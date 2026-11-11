# aiv — 品牌系列视频的生产线

把写好的技术文章，变成一条能持续产出、还能被复现的成片流水线。

技术图示一律由代码绘制（cairo + ffmpeg），不交给模型生成；
形象是 3D 静帧 + 位移/缩放/淡入，文字用真实字体在 cairo 阶段渲染。
**入库的是事实**（规范、契约、台账、代码），**产物不入库**（图像与音频留本机）。

## 目录

| 目录 | 内容 |
| --- | --- |
| `pipeline/` | 出片流水线：`pyv/` 渲染引擎 + `tests/` + `Makefile` |
| `character/` | 3D 小象形象：生成、加眼镜、铭牌盖章（`scripts/`） |
| `brand/` | 品牌片头/片尾：渲染与配乐（`scripts/`） |
| `voice/` | 旁白音色与合成（`scripts/`） |
| `music/` | 背景音乐曲库：授权台账（入库）+ 曲库文件（不入库） |

## 规范

| 文档 | 内容 |
| --- | --- |
| [人格规范.md](人格规范.md) | 小象是谁、怎么想、怎么讲；9 条可机检规则 |
| [形象与音色规范.md](形象与音色规范.md) | 角色设定、铭牌文字的确定性、旁白音色定稿 |
| [背景音乐规范.md](背景音乐规范.md) | 选曲白名单、风格标准、技术规格、混音与 ducking 规则 |

模块自己的说明在 [character/README.md](character/README.md)、
[brand/README.md](brand/README.md)、[voice/README.md](voice/README.md)、
[music/README.md](music/README.md)。

## 跑一遍

```bash
cd aiv/pipeline
make test        # 全量测试
make persona     # 按《人格规范》检查口播稿
make bgm         # 按《背景音乐规范》检查曲库台账
```

出片链路（`validate → brand → render → compose`）需要 `storyboard.json` 契约与旁白音频，
两者都是本机素材，不入库。

## 发布到博客的那一份

`aiv/` 在仓库根，不在 `docs/` 下面，而 `sync-hexo.py` 只扫 `docs/`——
所以上面那些**文档**在 `docs/life/aiv/` 另存一份，博客上发的就是那一份。

改完 `aiv/` 里的文档后跑：

```bash
python3 aiv/scripts/sync_publish_docs.py
```

`pipeline/tests/test_publish_copy.py` 盯着两份是否一致：漂了会红，
线上内容不会悄悄落后于仓库里的规范。

发布目录里**只有**这些文档。`pipeline/` 下的内部设计、实施计划与测试夹具
留在仓库里，不进博客——测试夹具尤其不能发，其中一份是故意写坏的样本。

# Growdu 背景音乐库

**规范见 [`../背景音乐规范.md`](../背景音乐规范.md)。**

曲库下载的背景音乐放这里，**音频不入库**（媒体产物留本机），
**授权台账入库**（`library.json`）——台账是事实，不是产物。

```
music/
├── library.json            授权台账（入库）：逐首登记来源、授权、指纹、角色
├── tracks/                 音频成品（不入库）
│   └── <id>.wav            已转规格、已归一化到 -20 LUFS
└── scripts/
    └── fetch_music.py      按台账下载 → 转规格 → 归一化 → 校验指纹
```

## 台账

`library.json` 是这台机器与这个仓库之间唯一的曲库事实来源。
一条记录长这样：

```json
{
  "id": "series-motif-01",
  "title": "Deep Blue Signal",
  "artist": "Some Artist",
  "source": "pixabay",
  "source_url": "https://pixabay.com/music/…",
  "license": "CC0-1.0",
  "attribution_required": false,
  "attribution_text": "",
  "series_role": "motif",
  "local_path": "music/tracks/series-motif-01.wav",
  "bpm": 84,
  "duration_s": 138.2,
  "sha256": "…",
  "downloaded_at": "2026-11-11",
  "notes": "系列主题动机，片头片尾都从这首里挑 3 秒"
}
```

字段说明见规范 §2.2。要点：

- **`license` 必须在白名单里**（规范 §2.1），非商用、CC-BY-NC、CC-BY-SA 一律不用。
- **需要署名的必须写 `attribution_text`**，出片时带到简介里。
- **`sha256` 是必须的**：文件被动过（换源、重新转码），授权记录就不可信了。
- **`series_role` 决定它在系列里的位置**（规范 §6）：`motif` 全系列只能有 1 首。

## 查台账

```bash
cd aiv/pipeline
python -m pyv.cli bgm library          # 台账自洽性（授权、指纹、角色）
python -m pyv.cli bgm check --music <文件>   # 判单条曲子合不合格
```

## 当前曲库

| id | 曲名 | 艺人 | 角色 | 时长 | 授权 |
| --- | --- | --- | --- | --- | --- |
| `series-motif-01` | The Deep End | Ocoeur | `motif` | 291.0 s | CC0-1.0 |
| `series-bed-01` | Subdued | Jason Van Wyk | `bed` | 209.2 s | CC0-1.0 |

两首都出自 [archive.org](https://archive.org/)（`connections-raw-wav`、
`threads-raw-wav`，均为 vinyl rip，licenseurl 指向 CC0 1.0），免署名。

选曲过程：**机器判据是门槛，风格靠人听**。候选 12 轨里有 2 轨没过机器判据
（1~4 kHz 超标、真峰值超标），其余按《背景音乐规范》§3.1 的人工清单挑——
自动评分会偏好「几乎没有低频」的曲子，而规范要求低频是律动，不能反过来让分数选曲。

`series-bed-01` 的低频占 31.7%，是 `series-motif-01`（15.3%）的两倍：
铺底要「托着」，动机只要「点一下」。

## 下载

```bash
cd aiv/music
python3 scripts/fetch_music.py --list
python3 scripts/fetch_music.py --id series-motif-01
python3 scripts/fetch_music.py --all
```

脚本只做四件事：**下载 → 转规格（48 kHz 立体声）→ 归一化到 -20 LUFS →
校验 sha256 并落盘**。它不替你判断授权——台账里没有的曲子不会被下载。

**下载源按站点分适配器**（`scripts/fetch_music.py` 的 `SOURCES`）。
各站点的页面结构不同，接的时候一个站点写一个适配器；
没接的站点会直接报错，不会去猜 URL。

已接：**archive.org**（取 `/metadata/<id>` 里的文件级直链与时长，
按曲名前缀/后缀匹配文件）。ccMixter 与 Pixabay 也留了位置，
但它们的 CC0 曲目太少 / 直链需要额外签名，没当成主源。

**归一化跑两遍。** loudnorm 是两遍式算法，只跑一遍的话增益用的是第一遍的
估计，落不到 -20（实测只到 -18.5 ~ -19.1 LUFS）。差 1.5 dB 不是小数目：
《背景音乐规范》§5.1 的整条混音推导都是从 -20 算出来的。

## 验收成片

曲子入库只是第一步，混完之后还要量一遍成片：

```bash
cd aiv/pipeline
python -m pyv.cli bgm verify \
    --video ../out/pg-parallel-decode.mp4 \
    --narration ../narration_pg-parallel-decode.mp3 \
    --music ../music/tracks/series-bed-01.wav \
    --storyboard ../storyboard.json
```

量四件事：稳态 duck 深度、旁白活跃段与 BGM 的电平差、成片真峰值、
旁白在成片里的增益偏差。判据见《背景音乐规范》§5.7。

## 落盘规格

| 项 | 值 |
| --- | --- |
| 格式 | 16 bit PCM wav |
| 采样率 | 48 kHz |
| 声道 | 立体声 |
| 响度 | -20 LUFS（两遍 loudnorm） |
| 真峰值 | ≤ -3.0 dBTP |

归一化不是可选项：曲库母版的响度差能到 10 dB 以上，
不拉平就没法用固定增益混音（规范 §4.1）。

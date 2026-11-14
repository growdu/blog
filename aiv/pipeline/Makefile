# 出片流水线（按期可切）
#
#   make test      跑全部测试
#   make doctor    环境自检：这台机器缺什么、怎么补（先跑这个）
#   make validate  校验 storyboard 契约（时间码、字幕宽度、禁止词、字体）
#   make align     重新按旁白对齐生成 storyboard
#   make brand     套上品牌片头/片尾（brand/clips/*.mp4）
#   make render    渲染各场景片段（预览用，与成片同样烧字幕）
#   make compose   拼接 + 混音 + 出片
#   make persona   按《人格规范》检查口播稿
#   make topics    按《选题库》的规则检查选题
#   make bgm       按《背景音乐规范》检查曲库台账
#   make mix-verify 成片级混音验收（规范 §5.7）
#   make all       validate → brand → render → compose
#   make nobrand   无品牌导流版（抖音这一档用）：nobrand → render → compose
#                  胸口铭牌也是品牌标识：make EP=<期号> nobrand NOBADGE=1
#                  换成无标牌形象（默认保留铭牌，等实投结果再定）
#   make vertical  竖版 9:16（抖音那一档）：align --canvas vertical → nobrand
#                  → render → compose
#
# align 是手工步骤，需要在 all 之前单独跑。
# 片段是增量渲染的：build/ 里未过期的片段会被直接复用。
#
# 换一期：make EP=<期号> ...，例如
#   make EP=csn-total-ordering align
#
# 一期 = 一个 EP 号，它决定契约 / 旁白 / 时间轴 / 片段目录 / 成片的文件名。
# **口播稿按主题命名，不按 EP 号**——所以在下面按 EP 显式登记，
# 换期时忘了换稿会当场报错，而不是静悄悄地拿上一期的稿子出片。

ROOT := ..
# Python 解释器：Linux 上常常只有 python3，没有 python。
# 想指定别的解释器就 `make PY=/path/to/python3 ...`。
PY ?= $(shell command -v python3 >/dev/null 2>&1 && echo python3 || echo python)

EP ?= pg-parallel-decode

ifeq ($(EP),pg-parallel-decode)
SCRIPT := $(ROOT)/字幕-并行解码.md
else ifeq ($(EP),csn-total-ordering)
SCRIPT := $(ROOT)/字幕-CSN全序.md
else ifeq ($(EP),wal-interleave)
SCRIPT := $(ROOT)/字幕-WAL顺序.md
else ifeq ($(EP),parallel-apply)
SCRIPT := $(ROOT)/字幕-并行apply.md
else ifeq ($(EP),structured-ddl)
SCRIPT := $(ROOT)/字幕-结构化DDL.md
else ifeq ($(EP),row-lock)
SCRIPT := $(ROOT)/字幕-行锁.md
else
$(error 未知 EP「$(EP)」：在 Makefile 里登记这一期的口播稿路径)
endif

STORYBOARD := $(ROOT)/storyboard_$(EP).json
NARRATION := $(ROOT)/narration_$(EP).mp3
CONTRACT := $(ROOT)/contracts/$(EP).json
# 正文铺底（曲库台账里 series_role=bed 的那首）
BGM := $(ROOT)/music/tracks/series-bed-01.wav
# 片段目录按期分开：各期的段 id 会重名（s01…），共用一个目录会互相覆盖。
BUILD := $(ROOT)/build/$(EP)
OUT := $(ROOT)/out/$(EP).mp4

# 无品牌导流版：抖音这一档用。去掉品牌片头/片尾，落版标签也不带品牌名——
# 抖音禁「过度营销信息」与站外引流，片头整屏字标与片尾的 growdu.cn 胶囊
# 正好撞上（规格 §6.6.4）。
#
# **片段目录与成片都另起一份**：不跟带品牌的版本共用，否则增量渲染会把
# 带品牌片的片段当成可复用的（成片的 sha256 变了才发现，已经晚了）。
NOBRAND_STORYBOARD := $(ROOT)/storyboard_$(EP)__nobrand.json
NOBRAND_BUILD := $(ROOT)/build/$(EP)__nobrand
NOBRAND_OUT := $(ROOT)/out/$(EP)__nobrand.mp4

# 无标牌形象（抖音这一档备用）：胸口那枚 growdu 铭牌也是品牌标识，
# 被判「过度营销信息」时用它重出片。**默认不换**——铭牌占比极小，
# 先按保留投一条看审核结果（规格 §十四 第 16 条）。
#
#   make EP=row-lock nobrand NOBADGE=1
NOBADGE_CHAR := $(ROOT)/character/growdu_character_2k_nobg_nobadge.png
CHARACTER_FLAG := $(if $(NOBADGE),--character $(NOBADGE_CHAR))

# 竖版画布（抖音那一档）：9:16。**不套品牌片**——品牌片素材是横版的，
# 贴到竖版画布上会被拉变形（`pyv.cli brand` 会直接拒绝）。
# 竖版这一档同时也是无品牌版：片头片尾本来就不该有。
VERTICAL_ALIGNED := $(ROOT)/storyboard_$(EP)__vertical_aligned.json
VERTICAL_STORYBOARD := $(ROOT)/storyboard_$(EP)__vertical.json
VERTICAL_BUILD := $(ROOT)/build/$(EP)__vertical
VERTICAL_OUT := $(ROOT)/out/$(EP)__vertical.mp4

.PHONY: all test doctor validate align brand render compose nobrand vertical probe persona bgm mix-verify topics pronunciation clean

all: validate brand render compose

test:
	$(PY) -m pytest tests/ -q

# 环境自检：缺什么报什么，并给出可执行的修复命令
doctor:
	$(PY) -m pyv.cli doctor

validate:
	$(PY) -m pyv.cli validate --storyboard $(STORYBOARD)

align:
	$(PY) -m pyv.cli align --audio $(NARRATION) --script $(SCRIPT) \
		--scenes $(CONTRACT) --out $(STORYBOARD)

brand:
	$(PY) -m pyv.cli brand --storyboard $(STORYBOARD) --out $(STORYBOARD) \
		--build $(BUILD)

render:
	$(PY) -m pyv.cli render --storyboard $(STORYBOARD) --out $(BUILD)

compose:
	$(PY) -m pyv.cli compose --storyboard $(STORYBOARD) --build $(BUILD) \
		--out $(OUT) --narration $(NARRATION) --bgm $(BGM)

# 无品牌导流版（抖音这一档用）
nobrand:
	$(PY) -m pyv.cli nobrand --storyboard $(STORYBOARD) \
		--out $(NOBRAND_STORYBOARD)
	$(PY) -m pyv.cli render --storyboard $(NOBRAND_STORYBOARD) \
		--out $(NOBRAND_BUILD) $(CHARACTER_FLAG)
	$(PY) -m pyv.cli compose --storyboard $(NOBRAND_STORYBOARD) \
		--build $(NOBRAND_BUILD) --out $(NOBRAND_OUT) \
		--narration $(NARRATION) --bgm $(BGM)

# 竖版（抖音那一档）：9:16
# align 直接产出竖版画布的 storyboard，再走 nobrand（竖版不要品牌片，
# 也不要落版上的品牌名）。
vertical:
	$(PY) -m pyv.cli align --audio $(NARRATION) --script $(SCRIPT) \
		--scenes $(CONTRACT) --canvas vertical --out $(VERTICAL_ALIGNED)
	$(PY) -m pyv.cli nobrand --storyboard $(VERTICAL_ALIGNED) \
		--out $(VERTICAL_STORYBOARD)
	$(PY) -m pyv.cli render --storyboard $(VERTICAL_STORYBOARD) \
		--out $(VERTICAL_BUILD) $(CHARACTER_FLAG)
	$(PY) -m pyv.cli compose --storyboard $(VERTICAL_STORYBOARD) \
		--build $(VERTICAL_BUILD) --out $(VERTICAL_OUT) \
		--narration $(NARRATION) --bgm $(BGM)

persona:
	$(PY) -m pyv.cli persona check --script $(SCRIPT)

bgm:
	$(PY) -m pyv.cli bgm library

# 选题库检查：结构、口径、句数字数、数字出处
topics:
	$(PY) -m pyv.cli topics check

# 多音字读音验收：确认「行锁」确实念 xíng、「航锁」确实念 háng
# （要联网合成探针；判据见 voice/scripts/pronunciation.py）
pronunciation:
	$(PY) ../voice/scripts/check_pronunciation.py --calibrate

# 成片级验收：稳态 duck 深度、旁白/BGM 电平差、真峰值、旁白增益（规范 §5.7）
mix-verify:
	$(PY) -m pyv.cli bgm verify --video $(OUT) --narration $(NARRATION) \
		--music $(BGM) --storyboard $(STORYBOARD)

probe:
	ffprobe -v error -show_entries format=duration \
		-show_entries stream=width,height,codec_type,codec_name,pix_fmt \
		-of default=noprint_wrappers=1 $(OUT)

clean:
	rm -rf $(BUILD) $(ROOT)/out/$(EP).mp4

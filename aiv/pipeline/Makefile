# 并行逻辑解码讲解片：出片流水线
#
#   make test      跑全部测试
#   make validate  校验 storyboard 契约（时间码、字幕宽度、禁止词、字体）
#   make align     重新按旁白对齐生成 storyboard.json
#   make brand     套上品牌片头/片尾（brand/clips/*.mp4）
#   make render    渲染各场景片段（预览用，与成片同样烧字幕）
#   make compose   拼接 + 混音 + 出片
#   make persona   按《人格规范》检查口播稿
#   make bgm       按《背景音乐规范》检查曲库台账
#   make all       validate → brand → render → compose
#
# align 是手工步骤，需要在 all 之前单独跑。
# 片段是增量渲染的：build/ 里未过期的片段会被直接复用。

ROOT := ..
PY := python

STORYBOARD := $(ROOT)/storyboard.json
SCRIPT := $(ROOT)/字幕-并行解码.md
NARRATION := $(ROOT)/pa_decode_v2.mp3
BUILD := $(ROOT)/build
OUT := $(ROOT)/out/pg-parallel-decode.mp4

.PHONY: all test validate align brand render compose probe persona bgm clean

all: validate brand render compose

test:
	$(PY) -m pytest tests/ -q

validate:
	$(PY) -m pyv.cli validate --storyboard $(STORYBOARD)

align:
	$(PY) -m pyv.cli align --audio $(NARRATION) --script $(SCRIPT) \
		--out $(STORYBOARD)

brand:
	$(PY) -m pyv.cli brand --storyboard $(STORYBOARD) --out $(STORYBOARD) \
		--build $(BUILD)

render:
	$(PY) -m pyv.cli render --storyboard $(STORYBOARD) --out $(BUILD)

compose:
	$(PY) -m pyv.cli compose --storyboard $(STORYBOARD) --build $(BUILD) \
		--out $(OUT) --narration $(NARRATION)

persona:
	$(PY) -m pyv.cli persona check --script $(SCRIPT)

bgm:
	$(PY) -m pyv.cli bgm library

probe:
	ffprobe -v error -show_entries format=duration \
		-show_entries stream=width,height,codec_type,codec_name,pix_fmt \
		-of default=noprint_wrappers=1 $(OUT)

clean:
	rm -rf $(BUILD) $(ROOT)/out

#!/usr/bin/env bash
# 生成与片头/片尾画面匹配的音频：中文旁白 + 环境氛围配乐 + 提示音
#
# ⚠️ **macOS 专有**：依赖 macOS 自带的 `say`（合成中文童声）。
#    Linux 上跑不了——这不是出片链路的必需步骤：
#    现行做法是 `make_audio_brand.py`（纯 ffmpeg，跨平台），
#    它切 `brand/brand_windows.json` 里的 motif 窗口混音，
#    旁白用已入库的 `brand/audio/voice_intro.mp3` / `voice_outro.mp3`。
#    本脚本只用于「重新做一套 macOS 童声版旁白」，属于历史路径。
#
# 产物（model/audio/ 下）：
#   intro_voice.wav  片头旁白
#   outro_voice.wav  片尾旁白
#   intro_mix.wav    片头成品音轨（旁白 + 配乐）
#   outro_mix.wav    片尾成品音轨（旁白 + 配乐）
#
# 依赖：macOS 自带 say（中文语音）、FFmpeg。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/audio"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"

VOICE="${VOICE:-Sandy (中文（中国大陆）)}"   # macOS 童声，作为「小男孩」音色
PITCH="${PITCH:-1.5}"                        # 升调半音数，让童声更像小男孩
INTRO_LINE="深入数据库，分享技术之美。Growdu，与你一起探索数据库的无边世界。"
OUTRO_LINE="感谢观看。访问 growdu.cn，订阅关注，点赞支持。"

# ---------------------------------------------------------------- 旁白
say -v "$VOICE" -r 185 -o "$TMP/intro_voice_raw.aiff" "$INTRO_LINE"
say -v "$VOICE" -r 170 -o "$TMP/outro_voice_raw.aiff" "$OUTRO_LINE"

# 升调（asetrate 变速变调后用 atempo 补回语速）
pitch() {  # $1=输入 $2=输出
  local r t
  r=$(python3 -c "print(int(round(44100 * 2 ** ($PITCH / 12.0))))")
  t=$(python3 -c "print(round(1 / 2 ** ($PITCH / 12.0), 4))")
  ffmpeg -y -v error -i "$1" -ac 2 \
    -af "aresample=44100,asetrate=$r,aresample=44100,atempo=$t" -ac 2 -ar 48000 "$2"
}

pitch "$TMP/intro_voice_raw.aiff" "$TMP/intro_voice.aiff"
pitch "$TMP/outro_voice_raw.aiff" "$TMP/outro_voice.aiff"

# ---------------------------------------------------------------- 配乐
# A 小调铺底 + 缓慢起伏的高频微光，制造科技感但不抢旁白
pad='0.20*sin(2*PI*110*t)+0.15*sin(2*PI*164.81*t)+0.10*sin(2*PI*220*t)+0.055*sin(2*PI*329.63*t)+0.03*sin(2*PI*440*t)+0.018*sin(2*PI*1760*t)*(0.5+0.5*sin(2*PI*0.35*t))'
chime='0.30*sin(2*PI*659.25*t)*exp(-2.2*t)+0.22*sin(2*PI*987.77*t)*exp(-3.2*t)+0.12*sin(2*PI*1318.51*t)*exp(-4.5*t)'

bgm() {  # $1=输出 $2=提示音出现时间(毫秒)
  ffmpeg -y -v error \
    -f lavfi -i "aevalsrc=$pad:d=8:s=48000" \
    -f lavfi -i "aevalsrc=$chime:d=4:s=48000" \
    -filter_complex "[0:a]tremolo=f=0.25:d=0.35,lowpass=f=2600,aecho=0.85:0.9:900|1500|2400:0.4|0.28|0.18,afade=t=in:st=0:d=2.2,afade=t=out:st=6:d=2[bg];\
[1:a]atrim=0:4,adelay=$2|$2,afade=t=out:st=1.6:d=2.4[ch];\
[bg][ch]amix=inputs=2:duration=first:weights=1 0.55,volume=-8dB,alimiter=limit=0.9" \
    -ac 2 -ar 48000 "$1"
}

bgm "$TMP/intro_bgm.wav" 300    # 片头：提示音紧跟片头字标亮起
bgm "$TMP/outro_bgm.wav" 5700   # 片尾：提示音落在「点赞支持」收尾处

# ---------------------------------------------------------------- 混音
mix() {  # $1=旁白 $2=配乐 $3=输出
  ffmpeg -y -v error -i "$1" -i "$2" \
    -filter_complex "[0:a]volume=1.0,adelay=120|120,apad=pad_dur=8[vo];\
[1:a]apad=whole_dur=8,volume=1.0[bg];\
[vo][bg]amix=inputs=2:duration=first:weights=1 0.55,volume=3dB,alimiter=limit=0.95,\
afade=t=in:st=0:d=0.6,afade=t=out:st=7.2:d=0.8,aformat=channel_layouts=stereo" \
    -t 8 -ac 2 -ar 48000 "$3"
}

mix "$TMP/intro_voice.aiff" "$TMP/intro_bgm.wav" "$OUT/intro_mix.wav"
mix "$TMP/outro_voice.aiff" "$TMP/outro_bgm.wav" "$OUT/outro_mix.wav"

# 单独留一份纯旁白，方便后期重新配乐
ffmpeg -y -v error -i "$TMP/intro_voice.aiff" -ar 48000 -ac 2 "$OUT/intro_voice.wav"
ffmpeg -y -v error -i "$TMP/outro_voice.aiff" -ar 48000 -ac 2 "$OUT/outro_voice.wav"

for f in intro_voice intro_mix outro_voice outro_mix; do
  printf '  %-16s %s 秒\n' "$f.wav" \
    "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$f.wav")"
done
echo "音频已生成于 $OUT"

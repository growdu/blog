#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/video"

# 从静态底板渲染 8 秒 Ken Burns 片段；若 audio/ 下存在成品音轨则一并封装
render() {
  local input="$1" output="$2" audio="$3"
  local tmp="$output.tmp.mp4"
  ffmpeg -y -loop 1 -i "$input" -t 8 \
    -vf "scale=2200:1238:force_original_aspect_ratio=increase,crop=2200:1238,zoompan=z='min(zoom+0.00025,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,fade=t=in:st=0:d=0.7,fade=t=out:st=7.3:d=0.7,format=yuv420p" \
    -an -c:v libx264 -preset medium -crf 19 -movflags +faststart "$tmp"
  if [ -f "$audio" ]; then
    ffmpeg -y -i "$tmp" -i "$audio" -map 0:v:0 -map 1:a:0 \
      -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest -movflags +faststart "$output"
    rm -f "$tmp"
  else
    mv "$tmp" "$output"
  fi
}

render "$ROOT/assets/plates/growdu_intro_1080p.png" "$ROOT/video/growdu_intro_8s_1080p.mp4" "$ROOT/audio/intro_mix.wav"
render "$ROOT/assets/plates/growdu_outro_1080p.png" "$ROOT/video/growdu_outro_8s_1080p.mp4" "$ROOT/audio/outro_mix.wav"
echo "Rendered Growdu intro/outro."

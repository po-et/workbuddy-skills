#!/usr/bin/env bash
# 生成 Buddy 应用图片资源（依赖 macOS qlmanage + ImageMagick 7）
# 规格来源：官方 buddy-app.zip 设计规范：头像 256×256；精选场景底图 1000×910，
# 底图上部 670px，叠两层 670px 灰蒙层（日 #F2F2F2 / 夜 #242424，0%→100%），
# 再叠一层 910px 全局蒙层（日 #FFFFFF / 夜 #242424，0%→100%）。
set -euo pipefail
cd "$(dirname "$0")"
TMP=$(mktemp -d)

# 1) 头像
qlmanage -t -s 512 -o "$TMP" src/avatar.svg >/dev/null 2>&1
magick "$TMP/avatar.svg.png" -resize 256x256 -strip PNG32:icon-256.png

# 2) 精选场景底图：不用外部照片（无授权），用自绘的抽象"提交图/看板"图层
art() { # $1=grid色 $2=块色A $3=块色B $4=折线色 $5=out
  local g=$1 a=$2 b=$3 l=$4 out=$5 d=""
  for x in $(seq 0 60 1000); do d="$d line $x,0 $x,670"; done
  for y in $(seq 0 60 670); do d="$d line 0,$y 1000,$y"; done
  magick -size 1000x670 xc:none \
    -stroke "$g" -strokewidth 1 -fill none -draw "$d" \
    -stroke none -fill "$a" -draw "roundrectangle 80,110 430,290 24,24" \
    -fill "$b" -draw "roundrectangle 470,170 920,370 24,24" \
    -fill "$a" -draw "roundrectangle 80,330 300,450 24,24" \
    -stroke "$l" -strokewidth 6 -fill none -draw "polyline 60,560 220,500 380,530 540,420 700,450 860,340" \
    -stroke none -fill "$l" \
    -draw "circle 220,500 220,510" -draw "circle 540,420 540,430" -draw "circle 860,340 860,350" \
    "$out"
}
scene() { # $1=name $2=day|night $3=grid $4=blockA $5=blockB $6=line
  local name=$1 mode=$2
  if [ "$mode" = day ]; then base='#F2F2F2'; mask='#F2F2F2'; glob='#FFFFFF'; else base='#242424'; mask='#242424'; glob='#242424'; fi
  art "$3" "$4" "$5" "$6" "$TMP/art.png"
  magick -size 1000x910 xc:"$base" "$TMP/art.png" -geometry +0+0 -composite \
    \( -size 1000x670 gradient:"${mask}00-${mask}FF" \) -geometry +0+0 -composite \
    \( -size 1000x670 gradient:"${mask}00-${mask}FF" \) -geometry +0+0 -composite \
    \( -size 1000x910 gradient:"${glob}00-${glob}FF" \) -geometry +0+0 -composite \
    -strip "PNG24:scene-${name}-${mode}.png"
}
# 三个精选场景各一套配色（mint / sky / amber）
scene report   day   '#D9DEE5' '#34D39955' '#0EA5E933' '#34D399'
scene report   night '#3A3F47' '#34D39955' '#0EA5E944' '#34D399'
scene release  day   '#D9DEE5' '#38BDF855' '#34D39933' '#0EA5E9'
scene release  night '#3A3F47' '#38BDF855' '#34D39944' '#38BDF8'
scene incident day   '#D9DEE5' '#FBBF2455' '#F8717133' '#F59E0B'
scene incident night '#3A3F47' '#FBBF2455' '#F8717144' '#FBBF24'
rm -rf "$TMP"
magick identify -format "%f %wx%h %[channels] %b\n" icon-256.png scene-*.png

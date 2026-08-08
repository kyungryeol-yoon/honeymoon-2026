#!/usr/bin/env bash
# icons/*.svg → PNG
#
# ImageMagick 내장 SVG 렌더러는 stroke 와 H/V path 명령을 빠뜨리므로
# Chrome 헤드리스로 렌더링합니다. (magick 은 리사이즈/8bit 축소에만 사용)
set -euo pipefail

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ICONS="$ROOT/icons"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

render () { # $1=svg  $2=size  $3=out
  cat > "$TMP/w.html" <<HTML
<!doctype html><meta charset="utf-8">
<style>html,body{margin:0;padding:0;background:transparent}
img{display:block;width:${2}px;height:${2}px}</style>
<img src="file://$ICONS/$1">
HTML
  "$CHROME" --headless --disable-gpu --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=1 --default-background-color=00000000 \
    --window-size="$2,$2" --screenshot="$TMP/$3" "file://$TMP/w.html" 2>/dev/null
  magick "$TMP/$3" -depth 8 -strip "$ICONS/$3"
  echo "  $3  (${2}x${2})"
}

echo "rendering icons…"
render icon.svg          512 icon-512.png
render icon.svg          192 icon-192.png
render icon-maskable.svg 512 icon-maskable-512.png
render icon-maskable.svg 192 icon-maskable-192.png
render icon.svg          180 apple-touch-icon.png

# 애플 아이콘은 투명 대신 배경색으로 채웁니다
magick "$ICONS/apple-touch-icon.png" -background "#12151F" -flatten -depth 8 -strip \
       "$ICONS/apple-touch-icon.png"
echo "done."

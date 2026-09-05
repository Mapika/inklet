#!/usr/bin/env bash
# Render an SVG to PNG via headless Chrome at `zoom` times its physical size.
# Looking at the figure is the check the linter cannot perform.
#
# Chrome clips a standalone SVG when the window is exactly its intrinsic size,
# so we render into a deliberately oversized viewport and crop back.
set -euo pipefail
svg="$(realpath "$1")"; out="$(realpath "${2:-${1%.svg}.png}")"; zoom="${3:-3}"
read -r W H < <(python3 -c "
import pathlib
t = pathlib.Path('$svg').read_text()
mm = lambda k: float(t.split(k+'=\"')[1].split('mm\"')[0])
print(round(mm('width') * 96 / 25.4), round(mm('height') * 96 / 25.4))")
google-chrome --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --default-background-color=FFFFFFFF --disable-lcd-text --font-render-hinting=none --force-device-scale-factor="$zoom" \
  --screenshot="$out" --window-size="$((W + 200)),$((H + 200))" \
  "file://$svg" >/dev/null 2>&1
convert "$out" -crop "$((W * zoom))x$((H * zoom))+0+0" +repage "$out"
echo "$out $(identify -format '%wx%h' "$out")"

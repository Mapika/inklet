"""Build the inklet-versus-matplotlib comparison gallery.

Runs every `examples/compare/<name>/{inklet,matplotlib}_version.py`, then for
each pair records lines of code, inklet's lint status and the physical size of
both PNGs, writes `gallery/compare/<name>-side-by-side.png` and
`gallery/compare/summary.json`.

    python tools/compare_gallery.py            # all figures
    python tools/compare_gallery.py volcano    # one or more by name
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'examples' / 'compare'
OUT = ROOT / 'gallery' / 'compare'
DPI = 200

FIGURES = {
    'time_course': 'Time course with 95% CI bands',
    'grouped_bars': 'Grouped bars with error bars and points',
    'dose_response': 'Dose-response with fitted curves',
    'distributions': 'Violin and strip, four groups',
    'volcano': 'Volcano plot with labelled hits',
    'survival': 'Kaplan-Meier curves with number at risk',
    'heatmap': 'Correlation heatmap',
    'multi_panel': 'Four-panel double-column figure',
}

FONT_FILES = ('LiberationSans-Bold.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf')


def lines_of_code(path: Path) -> int:
    """Non-blank lines that are not comments."""
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines()
               if line.strip() and not line.strip().startswith('#'))


def run(script: Path) -> tuple[str, float]:
    started = time.perf_counter()
    result = subprocess.run([sys.executable, str(script)], cwd=ROOT, capture_output=True,
                            text=True, check=False)
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise SystemExit(f'{script.relative_to(ROOT)} failed:\n{result.stderr}')
    return result.stdout, elapsed


def size_mm(png: Path) -> list[float]:
    with Image.open(png) as image:
        return [round(pixels / DPI * 25.4, 1) for pixels in image.size]


def font(size: int):
    for name in FONT_FILES:
        for folder in ('/usr/share/fonts/truetype/liberation', '/usr/share/fonts/truetype/dejavu',
                       '/Library/Fonts', 'C:/Windows/Fonts'):
            candidate = Path(folder) / name
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def side_by_side(name: str, record: dict) -> Path:
    left = Image.open(OUT / f'{name}-inklet.png').convert('RGB')
    right = Image.open(OUT / f'{name}-matplotlib.png').convert('RGB')
    gap, header, pad = 40, 64, 24
    width = left.width + right.width + gap + 2 * pad
    height = max(left.height, right.height) + header + pad
    sheet = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(sheet)
    title, detail = font(26), font(20)
    for x, image, tool in ((pad, left, 'inklet'), (pad + left.width + gap, right, 'matplotlib')):
        draw.text((x, 12), tool, fill='#1a1a1a', font=title)
        note = f"{record['loc'][tool]} lines of code"
        draw.text((x + draw.textlength(tool, font=title) + 16, 18), note, fill='#525a65', font=detail)
        sheet.paste(image, (x, header))
        draw.rectangle((x - 1, header - 1, x + image.width, header + image.height), outline='#dedee3')
    target = OUT / f'{name}-side-by-side.png'
    sheet.save(target)
    return target


def main(names: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() and names else {}
    summary.setdefault('figures', {})
    summary['shared'] = {
        'data.py': lines_of_code(SOURCE / 'data.py'),
        'journal.mplstyle': lines_of_code(SOURCE / 'journal.mplstyle'),
    }
    for name in names or list(FIGURES):
        folder = SOURCE / name
        record = {'title': FIGURES.get(name, name), 'loc': {}, 'seconds': {}, 'size_mm': {}}
        for tool in ('inklet', 'matplotlib'):
            script = folder / f'{tool}_version.py'
            stdout, elapsed = run(script)
            record['loc'][tool] = lines_of_code(script)
            record['seconds'][tool] = round(elapsed, 2)
            record['size_mm'][tool] = size_mm(OUT / f'{name}-{tool}.png')
            if tool == 'inklet':
                lines = stdout.strip().splitlines()
                record['inklet_lint'] = lines[0] if lines else ''
        record['side_by_side'] = str(side_by_side(name, record).relative_to(ROOT))
        summary['figures'][name] = record
        print(f"{name:14} inklet {record['loc']['inklet']:3} lines  matplotlib "
              f"{record['loc']['matplotlib']:3} lines  {record['size_mm']['inklet']} vs "
              f"{record['size_mm']['matplotlib']} mm  {record['inklet_lint']}")
    totals = {tool: sum(r['loc'][tool] for r in summary['figures'].values())
              for tool in ('inklet', 'matplotlib')}
    summary['total_loc'] = totals
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n')
    print(f"total          inklet {totals['inklet']:3} lines  matplotlib {totals['matplotlib']:3} lines")


if __name__ == '__main__':
    main(sys.argv[1:])

"""Render the homepage detail from Inklet's original scientific SVG.

Run with the render extra installed: python tools/docs_hero.py
The viewBox includes panels A–E and their legends, without changing geometry.
The full figure, recipe and attribution remain in docs/scientific-gallery.md.
"""
from pathlib import Path
import re
import base64
from io import BytesIO
from tempfile import TemporaryDirectory

from fontTools.ttLib import TTFont

import resvg_py

ROOT = Path(__file__).resolve().parents[1]


def main():
    svg = (ROOT / 'docs/assets/scientific/olfactory.svg').read_text()
    match = re.search(r'<svg\b[^>]*>', svg)
    header = re.sub(r'width="[^"]+"', 'width="1920"', match[0], count=1)
    header = re.sub(r'height="[^"]+"', 'height="928"', header, count=1)
    header = re.sub(r'viewBox="[^"]+"', 'viewBox="0 16 240 116"', header, count=1)
    svg = svg[:match.start()] + header + svg[match.end():]
    target = ROOT / 'docs/assets/scientific/olfactory-detail.png'
    # resvg does not load CSS data-URL fonts. Supply the exact embedded fonts
    # as SFNT files, retaining the SVG's family aliases rather than substituting.
    with TemporaryDirectory() as directory:
        fonts = []
        for family, encoded in re.findall(
            r"font-family:([^;]+);[^}]*src:url\(data:font/woff;base64,([^)]*)\)", svg
        ):
            font = TTFont(BytesIO(base64.b64decode(encoded)))
            font.flavor = None
            for record in font['name'].names:
                if record.nameID in (1, 4, 6, 16):
                    record.string = family.encode(record.getEncoding())
            path = Path(directory) / f'{family}.ttf'
            font.save(path)
            font.close()
            fonts.append(str(path))
        if not fonts:
            raise ValueError('Scientific SVG must contain embedded fonts')
        target.write_bytes(resvg_py.svg_to_bytes(
            svg_string=svg, dpi=96, skip_system_fonts=True, font_files=fonts))
    print(target.relative_to(ROOT))


if __name__ == '__main__':
    main()

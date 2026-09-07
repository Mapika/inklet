"""Render guide previews from their actual Python snippets.

Run ``python tools/docs_previews.py`` with the render and volume extras installed.
The manifest identifies a 1-based Python block and the object to export there.
Blocks run in page order in a temporary directory; no example output enters the
checkout. Generated PNGs are committed so hosted docs need no render dependency.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r'^```python\n(.*?)^```', re.MULTILINE | re.DOTALL)


def main():
    import inklet as i
    from inklet.plot import Panel

    entries = json.loads((ROOT/'tools/docs_previews.json').read_text())
    pages = dict.fromkeys(entry['page'] for entry in entries)
    previous = Path.cwd()
    original_theme = i.current_theme()
    try:
        for page in pages:
            selected = [entry for entry in entries if entry['page'] == page]
            last = max(entry['block'] for entry in selected)
            blocks = BLOCK.findall((ROOT/'docs'/page).read_text())
            if any(not 1 <= entry['block'] <= len(blocks) for entry in selected):
                raise ValueError(f'{page}: preview refers to a missing Python block')
            namespace = {'__name__': 'docs_preview'}
            with tempfile.TemporaryDirectory(prefix='inklet-doc-preview-') as directory:
                os.chdir(directory)
                i.use_theme('nature')
                for number, code in enumerate(blocks, 1):
                    if number > last:
                        break
                    exec(compile(code, f'{page}:block{number}', 'exec'), namespace)
                    for entry in selected:
                        if entry['block'] != number:
                            continue
                        drawing = eval(entry['object'], namespace)
                        if hasattr(drawing, 'add_to'):
                            figure = i.figure(width=drawing.width + 10)
                            drawing.add_to(figure)
                            drawing = figure
                        if isinstance(drawing, Panel):
                            drawing = drawing.build()
                        if isinstance(drawing, i.Diagram):
                            figure = i.figure(width=drawing.width + 10)
                            figure.add(drawing)
                            drawing = figure
                        if hasattr(drawing, 'compile'):
                            drawing = drawing.compile()
                        path = ROOT/'docs/assets/guides'/entry['image']
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(drawing.to_png(dpi=160))
                        print(f'{page}:{number} → {entry["image"]}', flush=True)
    finally:
        os.chdir(previous)
        i.use_theme(original_theme)


if __name__ == '__main__':
    main()

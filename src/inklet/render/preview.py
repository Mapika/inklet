"""Optional preview renderers used by visual checks and export bundles."""
from __future__ import annotations

import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from ..core import DiagramError


def _run(args, timeout=60):
    try:
        subprocess.run(args, check=True, capture_output=True, timeout=timeout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise DiagramError(f'preview renderer failed: {args[0]} ({type(error).__name__})') from error


def svg_png(source, target, *, dpi=150):
    """Render an Inklet SVG with Chrome/Chromium and crop to its physical page."""
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError('preview dpi must be finite and positive')
    try:
        from PIL import Image
    except ImportError:
        raise DiagramError('PNG previews require Pillow; install inklet[images]') from None
    browser = next((p for name in ('google-chrome', 'chromium', 'chromium-browser')
                    if (p := shutil.which(name))), None)
    if browser is None:
        raise DiagramError('SVG previews require Chrome or Chromium on PATH')
    source, target = Path(source).resolve(), Path(target).resolve()
    root = ET.parse(source).getroot()
    try:
        width, height = (float(root.attrib[k].removesuffix('mm')) for k in ('width','height'))
    except (KeyError, ValueError):
        raise DiagramError('preview expects an Inklet SVG with physical dimensions in mm') from None
    pixels = (max(1, round(width*dpi/25.4)), max(1, round(height*dpi/25.4)))
    if pixels[0]*pixels[1] > 40_000_000:
        raise DiagramError('preview exceeds 40 million pixels; reduce dpi')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='inklet-preview-') as scratch:
        capture = Path(scratch)/'capture.png'
        _run([browser, '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
              '--allow-file-access-from-files', '--default-background-color=FFFFFFFF',
              '--disable-lcd-text', '--font-render-hinting=none', '--virtual-time-budget=500',
              f'--user-data-dir={scratch}/profile', f'--force-device-scale-factor={dpi/96}',
              f'--window-size={math.ceil(width*96/25.4)+100},{math.ceil(height*96/25.4)+100}',
              f'--screenshot={capture}', source.as_uri()])
        with Image.open(capture) as im:
            im.crop((0,0,*pixels)).save(target)
    return target


def pdf_png(source, target, *, dpi=150):
    """Render the first PDF page with Poppler for an independent backend check."""
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError('preview dpi must be finite and positive')
    executable = shutil.which('pdftoppm')
    if executable is None:
        raise DiagramError('PDF previews require Poppler (pdftoppm) on PATH')
    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='inklet-pdf-preview-') as scratch:
        stem = Path(scratch)/'page'
        _run([executable, '-r', str(dpi), '-png', '-singlefile', '-f', '1', '-l', '1',
              str(Path(source).resolve()), str(stem)])
        shutil.copyfile(stem.with_suffix('.png'), target)
    return target

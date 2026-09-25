"""Write small WebP previews for gallery cards and the homepage showcase.

Run ``python tools/docs_thumbnails.py`` after changing a gallery image or
tools/docs_gallery.json. It needs Pillow, which the docs build does not
install, so the previews and their manifest are committed under
docs/assets/thumbs/. Each file name carries a hash of its source image, so a
browser never keeps a preview of an older figure.

The docs hook (tools/docs_site.py) reads the manifest and adds ``srcset`` to
cards whose source image still matches the recorded hash. A card whose source
has changed since the last run shows the full-size image until this script
runs again. Full-size images remain the target of the lightbox and the "Full
size" link.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs'
OUT = DOCS/'assets/thumbs'
MANIFEST = OUT/'manifest.json'
CARD_WIDTHS = (480, 960)
# The homepage hero spans the content column, up to about 1100 CSS pixels.
HERO = 'assets/scientific/olfactory-detail.png'
HERO_WIDTHS = (960, 1600)


def source_path(image):
    """Return the file behind a site-relative image path."""
    return ROOT/image if image.startswith('gallery/') else DOCS/image


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def images():
    gallery = json.loads((ROOT/'tools/docs_gallery.json').read_text())
    wanted = {entry['image']: CARD_WIDTHS for entry in gallery}
    wanted[HERO] = HERO_WIDTHS
    wanted.update({image: CARD_WIDTHS for image in section_card_images()})
    return wanted


def section_card_images():
    """Card images on section overview pages (front matter ``layout: section``)."""
    import yaml

    found = []
    for page in sorted(DOCS.rglob('*.md')):
        text = page.read_text()
        if not text.startswith('---\n'):
            continue
        meta = yaml.safe_load(text[4:text.index('\n---', 4)]) or {}
        if meta.get('layout') != 'section':
            continue
        found += [card['image'] for group in meta.get('groups', [])
                  for card in group['cards'] if card.get('image')]
    return found


def main():
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for image, widths in images().items():
        path = source_path(image)
        sha = digest(path)
        stem = image.removesuffix('.png').replace('/', '-')
        with Image.open(path) as source:
            source.load()
            if source.mode not in ('RGB', 'RGBA'):
                source = source.convert('RGBA')
            files = []
            for width in sorted({min(width, source.width) for width in widths}):
                height = round(source.height*width/source.width)
                name = f'{stem}-{width}-{sha[:10]}.webp'
                if not (OUT/name).exists():
                    preview = source.resize((width, height), Image.LANCZOS)
                    preview.save(OUT/name, 'WEBP', quality=86, method=6)
                files.append({'path': f'assets/thumbs/{name}', 'width': width})
        manifest[image] = {'sha256': sha, 'width': source.width,
                           'height': source.height, 'files': files}
        print(f'{image} -> {", ".join(item["path"] for item in files)}')
    keep = {Path(item['path']).name for entry in manifest.values() for item in entry['files']}
    for old in OUT.glob('*.webp'):
        if old.name not in keep:
            old.unlink()
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()

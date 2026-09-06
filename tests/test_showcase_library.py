"""Showcase portability, download integrity and catalogue links."""
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]


def builder():
    spec=importlib.util.spec_from_file_location('showcase_builder',ROOT/'tools/showcase_gallery.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_asset_download_is_opt_in_and_does_not_replace_on_hash_failure(tmp_path,monkeypatch):
    module=builder();monkeypatch.setattr(module,'ROOT',tmp_path)
    source=tmp_path/'examples/showcase';source.mkdir(parents=True)
    body=b'fixture asset'
    lock={'id':'chair','files':[{'path':'modern_arm_chair_01_1k.blend',
        'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),'url':'https://example.invalid/chair.blend'}]}
    (source/'assets.lock.json').write_text(json.dumps(lock))
    with pytest.raises(ValueError,match='download-assets'):module.asset_files(tmp_path/'out')
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *a,**k:BytesIO(body))
    path,_=module.asset_files(tmp_path/'out',download=True)
    assert path.read_bytes()==body
    path.write_bytes(b'old file')
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *a,**k:BytesIO(b'wrong'))
    with pytest.raises(ValueError,match='checksum'):module.asset_files(tmp_path/'out',download=True)
    assert path.read_bytes()==b'old file'


def test_gallery_has_unique_entries_and_portable_scene_links():
    module=builder();entries=module.recipes().CATALOG
    assert len(entries)==len({entry['id'] for entry in entries})==8
    records=[dict(entry,scene='scenes/architecture.blend' if entry['category']=='Architecture' else None)
             for entry in entries]
    page=module.gallery_page(records)
    assert page.count('<article ')==8
    assert 'href="scenes/architecture.blend" download' in page
    assert '<select id="category">' in page
    assert '<option>Architecture</option>' in page
    assert all(entry['origin'] for entry in entries)


def test_wave_packet_foreground_peak_occludes_the_next_trace():
    pytest.importorskip('resvg_py')
    Image=pytest.importorskip('PIL.Image')
    import inklet as i
    from inklet.draw.coords import plot_area

    art=builder().recipes().wave_packets()
    area=plot_area(art);box=art.bbox
    image=Image.open(BytesIO(i.to_png(art,dpi=200))).convert('RGBA')
    # This point lies inside both trace 0's peak and trace 1's fill.
    # The visible colour must belong to the foreground (trace 0).
    x=-2.475;y=1.1
    px=area.x0+(x+5)/10*area.width
    py=area.y1-(y+.1/.52)/(10.1/.52)*area.height
    pixel=image.getpixel((round((px-box.x0)/box.width*image.width),
                          round((py-box.y0)/box.height*image.height)))
    assert pixel==(180,196,207,255)

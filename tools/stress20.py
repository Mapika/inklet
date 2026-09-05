"""Build the twenty-panel plate and exercise edits, caching and physical resizing.

Run with Inklet's image extras, Chrome/Chromium and Poppler installed.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'examples'), str(ROOT/'src')]
from stress20 import make_case, PANEL_NAMES, SEED
import inklet as i
from inklet.core import TextPrim, ImagePrim, PathPrim


def check_snapshot(compiled):
    root, placements = compiled.build()
    assert set(PANEL_NAMES).issubset(compiled.cells), 'a panel is missing'
    ids = [n.attrib['id'] for n in ET.fromstring(compiled.to_svg()).iter() if 'id' in n.attrib]
    assert len(ids) == len(set(ids)), 'export contains duplicate IDs'
    problems = [d for d in compiled.diagnostics if d.severity in ('error', 'warning')]
    assert not problems, compiled.report()
    return dict(page_mm=[root.width, root.height], compilation=dict(compiled.stats),
                diagnostics=dict(Counter(d.code for d in compiled.diagnostics)),
                image_layers=sum(isinstance(p.diagram.prim, ImagePrim) for p in placements.values()),
                vector_paths=sum(isinstance(p.diagram.prim, PathPrim) for p in placements.values()))


def font_sizes(compiled):
    return sorted({p.diagram.prim.font_size for p in compiled.build()[1].values()
                   if isinstance(p.diagram.prim, TextPrim)})


def backend_comparison(files):
    """Compare independent rasterizations; discard only a rounding edge pixel.

    Chrome rounds page dimensions and Poppler rounds up. Crop their shared
    origin without resampling; retain both original dimensions in the report.
    This measures backend differences, not agreement with a reference image.
    """
    from PIL import Image, ImageChops, ImageStat
    with Image.open(files['png']) as svg, Image.open(files['pdf_png']) as pdf:
        dimensions = [svg.size, pdf.size]
        assert max(abs(a-b) for a,b in zip(svg.size,pdf.size)) <= 1
        box = (0, 0, min(svg.width,pdf.width), min(svg.height,pdf.height))
        diff = ImageChops.difference(svg.convert('RGB').crop(box), pdf.convert('RGB').crop(box))
        channels = diff.split()
        mask = ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
        changed = sum(mask.histogram()[26:])/(diff.width*diff.height)
        mean = sum(ImageStat.Stat(diff).mean)/(3*255)
        diff.point(lambda value:min(255,value*5)).save(files['png'].with_name('backend-difference.png'))
    return dict(dimensions_px=dimensions, compared_px=box[2:],
                fraction_over_25_rgb=changed, mean_absolute_rgb_fraction=mean)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/stress20')
    args = parser.parse_args()
    out = args.output.resolve()
    case = make_case()
    started = time.perf_counter()
    first = case.document.compile()
    cold_seconds = time.perf_counter()-started
    baseline = check_snapshot(first)
    baseline['seconds'] = cold_seconds
    svg = first.to_svg()
    started = time.perf_counter()
    assert case.document.compile() is first
    baseline['cached_seconds'] = time.perf_counter()-started
    assert baseline['image_layers'] == 2, 'only the cloud and scalar field should be rasterized'
    started = time.perf_counter()
    files = first.export(out,name='stress20')
    baseline['export_seconds'] = time.perf_counter()-started
    baseline['files_bytes'] = {kind:path.stat().st_size for kind,path in files.items()}
    baseline['backend_comparison'] = backend_comparison(files)
    print(json.dumps(dict(stage='baseline',**baseline)),flush=True)

    # Shared data must update the main trace and its inset. Other plot types
    # exercise independent dependency paths; the compiled original is immutable.
    case.response.update(**{key:[v*.86 for v in case.response.columns[key]]
                            for key in ('mean','lower','upper')})
    case.document['response']['body'].replace('adaptation',5,case.response.columns['upper'][100],
                                              'Adaptation',side='nw',size=2.5)
    case.cloud.update(x=[v+.25 for v in case.cloud.columns['x']])
    case.outcomes.update(value=[2.8,4.7,5.9,7.5])
    case.document['architecture']['body']['input'].configure(label='Batch')
    started = time.perf_counter()
    edited = case.document.compile()
    edit_seconds = time.perf_counter()-started
    edits = check_snapshot(edited)
    edits['seconds'] = edit_seconds
    assert edited.to_svg() != svg and first.to_svg() == svg
    assert edited.stats['cache_hits'] > 0
    changed_panels = {'response','cloud','bars','architecture'}
    for name in PANEL_NAMES:
        node_id = f'cell-{name}/cell-body'
        original = i.to_svg(first.build()[1][node_id].diagram)
        revised = i.to_svg(edited.build()[1][node_id].diagram)
        assert (original != revised) == (name in changed_panels), f'unexpected edit result in {name}'
    before = {d['name']:d for d in first.metadata['datasets']}
    after = {d['name']:d for d in edited.metadata['datasets']}
    assert len(after) == 3
    assert all(after[name]['revision']==1 and after[name]['data_sha256']!=before[name]['data_sha256']
               for name in before)
    edited.export(out/'edited',name='stress20',compare_to=files['manifest'])
    print(json.dumps(dict(stage='edited',**edits)),flush=True)

    resized = []
    for width in (320,400):
        case.document.configure(width=width)
        started = time.perf_counter()
        figure = case.document.compile()
        resize_seconds = time.perf_counter()-started
        record = check_snapshot(figure)
        record['seconds'] = resize_seconds
        assert figure.root.width == width
        assert font_sizes(figure) == font_sizes(first), 'resize changed physical font sizes'
        figure.export(out/f'width-{width}',name='stress20')
        resized.append(record)
        print(json.dumps(dict(stage=f'width-{width}',**record)),flush=True)

    report = dict(seed=SEED,load=case.load,baseline=baseline,edited=edits,resized=resized,
                  checks=dict(unique_ids=True,twenty_panels=True,exactly_two_raster_layers=True,
                              cached_snapshot_reused=True,data_revisions_updated=True,
                              only_edited_panels_changed=True,
                              original_snapshot_unchanged=True,resize_preserves_type=True,
                              no_errors_or_warnings=True))
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Review: {files["review"]}',flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

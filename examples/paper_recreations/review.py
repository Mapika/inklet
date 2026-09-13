"""Verify source/output invariants and build the local side-by-side review."""
from pathlib import Path
import argparse
import hashlib
import html
import json
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE.parents[1] / 'out/paper-recreations')
    args = parser.parse_args()
    out = args.output
    sources = json.loads((HERE / 'sources.json').read_text())
    for item in sources['files']:
        assert hashlib.sha256((out / 'references' / item['filename']).read_bytes()).hexdigest() == item['sha256']
    reports = {name: json.loads((out / f'{name}.json').read_text())
               for name in ('immune', 'sample', 'quantum')}
    assert [reports[n]['measurements']['axes'] for n in reports] == [22, 15, 6]
    assert reports['sample']['measurements']['sequences'] == 1352
    maps = reports['quantum']['measurements']['maps']
    assert {p['panel'] for p in maps} == set('abcdef')
    assert sum(p['rows'] * p['columns'] for p in maps) == 240000
    assert [round(p['maximum_percent'], 2) for p in maps] == [48.27, 8.13, 6.25, 8.57, .73, 1.22]
    for name, report in reports.items():
        assert len(report['panels']) == report['measurements']['axes']
        root = ET.parse(out / f'{name}.svg').getroot()
        assert not any(n.tag.rsplit('}', 1)[-1] == 'image' for n in root.iter())
        assert (out / f'{name}.pdf').read_bytes().startswith(b'%PDF')
        assert (out / f'{name}.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    parts = ['''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inklet — published figure stress test</title><style>
body{font:16px system-ui;margin:32px;color:#20262e;background:#f5f6f8}h1{font-size:28px}
a{color:#235ba8}section{margin:36px 0;padding:24px;background:white;border-radius:12px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pair img{width:100%;height:auto}
figure{margin:0}figcaption{font-weight:600;margin:12px 0}.toolbar{position:sticky;top:0;background:#f5f6f8;padding:12px;z-index:1}
body.wide .pair{min-width:2600px}p{max-width:1000px;line-height:1.5}
@media(max-width:700px){.pair{grid-template-columns:1fr}body{margin:12px}}
</style><h1>Three published figures, recreated in Inklet</h1>
<p>43 plotting axes; released numerical data; native vector marks. Originals are shown only for comparison.
These are reproductions, not original Inklet research or publisher-endorsed figures.
See <a href="REPORT.md">the fidelity and capability report</a> for remaining differences.</p>
<div class="toolbar"><button onclick="document.body.classList.toggle('wide')">Toggle large comparison</button>
 <a href="#immune">Viral evolution</a> · <a href="#sample">Protein engineering</a> · <a href="#quantum">Quantum response maps</a></div>''']
    for paper in sources['papers']:
        name = paper['id']
        bundle=(f' · <a href="{name}-review/index.html">Native provenance/diagnostic review</a>'
                if (out/f'{name}-review/index.html').exists() else '')
        parts.append(f'''<section id="{name}"><h2>{html.escape(paper['title'])}</h2>
<p>{html.escape(paper['authors'])}, {paper['journal']}, Figure {paper['figure']}.
<a href="{paper['url']}/figures/{paper['figure']}">Published figure</a> ·
<a href="{paper['license']}">CC BY 4.0</a> ·
Inklet: <a href="{name}.svg">SVG</a> / <a href="{name}.pdf">PDF</a> / <a href="{name}.png">PNG</a> /
<a href="{name}.json">Measurements</a>{bundle}</p>
<div class="pair"><figure><figcaption>Published original</figcaption>
<a href="references/{name}-original.png"><img src="references/{name}-original.png" alt="Published {name} figure"></a></figure>
<figure><figcaption>Inklet recreation from released data</figcaption>
<a href="{name}.png"><img src="{name}.png" alt="Inklet {name} recreation"></a></figure></div></section>''')
    parts.append('</html>')
    (out / 'index.html').write_text('\n'.join(parts))
    (out / 'verification.json').write_text(json.dumps({
        'status': 'passed', 'source_hashes': len(sources['files']), 'axes': 43,
        'map_samples': 240000, 'embedded_images': 0,
        'scope': 'Source hashes, panel/sample counts, maxima, SVG structure and export signatures; visual fidelity reviewed separately.'
    }, indent=2) + '\n')
    print('Verified 43 axes, 240,000 map samples, source hashes and native exports.')
    print(out / 'index.html')


if __name__ == '__main__':
    main()

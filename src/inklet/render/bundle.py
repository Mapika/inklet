"""Export a figure and a local review page from one authoring operation."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import tempfile

from .preview import svg_png, pdf_png


def component_paths(root):
    """Map target IDs to their named authoring components, without merging findings."""
    paths = {}
    def visit(node, parents):
        if node.name and node.kind != 'page' and (not parents or parents[-1] != node.name):
            parents = (*parents, node.name)
        paths[node.id] = ' / '.join(parents)
        for child in node.children:
            visit(child, parents)
    visit(root, ())
    return paths


def validate_options(name, dpi, text):
    if not math.isfinite(dpi) or dpi <= 0:
        raise ValueError('export dpi must be finite and positive')
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('export name must start with a letter or digit and contain only letters, digits, dots, underscores or hyphens')
    if text not in ('embed', 'outline'):
        raise ValueError("export text must be 'embed' or 'outline' for both SVG and PDF")


def export_bundle(figure, directory, *, name='figure', dpi=150, text='embed', compare_pdf=True, compare_to=None):
    validate_options(name, dpi, text)
    directory = Path(directory).resolve()
    directory.parent.mkdir(parents=True, exist_ok=True)
    files = {'svg':f'{name}.svg', 'pdf':f'{name}.pdf', 'png':f'{name}.png',
             'review':f'{name}.html', 'diagnostics':f'{name}-diagnostics.txt',
             'manifest':f'{name}-manifest.json', 'diagnostics_json':f'{name}-diagnostics.json'}
    if compare_pdf:
        files['pdf_png'] = f'{name}-pdf.png'
    # Finish every render before replacing an existing bundle.
    with tempfile.TemporaryDirectory(prefix='.inklet-export-', dir=directory.parent) as scratch:
        stage = Path(scratch)
        figure.save(stage/files['svg'], stage/files['pdf'], text=text)
        svg_png(stage/files['svg'], stage/files['png'], dpi=dpi)
        if compare_pdf:
            pdf_png(stage/files['pdf'], stage/files['pdf_png'], dpi=dpi)
        from dataclasses import asdict
        root, _ = figure.build()
        paths = component_paths(root)
        diagnostics = [dict(asdict(d), components=list(dict.fromkeys(
            paths[target] for target in d.targets if paths.get(target)))) for d in figure.lint()]
        (stage/files['diagnostics_json']).write_text(json.dumps(diagnostics,indent=2)+'\n',encoding='utf-8')
        report = figure.report()
        (stage/files['diagnostics']).write_text(report+'\n', encoding='utf-8')
        metadata = {'name':name, 'dpi':dpi, 'text':text,
                    'width_mm':root.bbox.width, 'height_mm':root.bbox.height,
                    'files':files}
        if hasattr(figure, 'metadata'):
            metadata['document'] = dict(figure.metadata)
            metadata['compilation'] = dict(figure.stats)
        if compare_to is not None:
            from .revision import stage_revision
            stage_revision(compare_to,stage,files,metadata,name)
        (stage/files['manifest']).write_text(json.dumps(metadata,indent=2)+'\n', encoding='utf-8')
        from .review import review_page
        page=review_page(metadata,diagnostics,report,(stage/files['svg']).read_text(encoding='utf-8'))
        (stage/files['review']).write_text(page, encoding='utf-8')
        directory.mkdir(parents=True, exist_ok=True)
        for filename in files.values():
            (stage/filename).replace(directory/filename)
    return {key:directory/filename for key,filename in files.items()}

"""Prepare local docs previews/downloads; does not deploy or publish a site."""
from pathlib import Path
import json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    source=ROOT/'out/scientific-gallery';dest=ROOT/'docs/assets/scientific';dest.mkdir(parents=True,exist_ok=True)
    for name in ['olfactory','communities']:
        for suffix in ['png','svg','pdf']:shutil.copy2(source/f'{name}.{suffix}',dest/f'{name}.{suffix}')
    for name in ['provenance.json','validation.json','verification.json','review.md']:shutil.copy2(source/name,dest/('review.txt' if name=='review.md' else name))
    files=[ROOT/p for p in ['pyproject.toml','README.md','LICENSE','THIRD_PARTY_NOTICES.md','docs/scientific-authoring.md','docs/scientific-gallery.md','examples/inspo/anatomy.py','examples/inspo/fly_data.py','examples/inspo/requirements.txt','examples/scientific_layout.py','tests/test_figure_annotations.py','tests/test_anatomy_sections.py','tests/test_scientific_release.py','tests/test_scientific_recipes.py','tests/test_scientific_authoring.py']]
    files.extend(p for p in (ROOT/'src/inklet').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
    files.extend(p for p in (ROOT/'examples/scientific_gallery').iterdir() if p.is_file())
    with zipfile.ZipFile(dest/'scientific-gallery-source.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in files:archive.write(p,str(p.relative_to(ROOT)))
        for name in ['provenance.json','validation.json','verification.json','measurements.npz','orn-counts.json','skeleton-metrics.json','source-cache/synapse-sampling.json','review.md']:
            archive.write(source/name,'out/scientific-gallery/'+name)
    print(f'Prepared docs assets: {dest}')

if __name__=='__main__':main()

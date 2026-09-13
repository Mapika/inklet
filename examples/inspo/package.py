"""Package figures, selected real anatomy, and the Inklet source they require."""
import argparse,json,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/inspo-native')
    parser.add_argument('--data',type=Path,default=ROOT/'out/inspo-recreated/data')
    args=parser.parse_args();out=args.output;data=args.data
    target=out/'inklet-native-figures.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.write(out/'README.md','README.md')
        for f in (ROOT/'examples/inspo').iterdir():
            if f.is_file():z.write(f,'source/'+f.name)
        for f in out.rglob('*'):
            if f.is_file() and f.suffix!='.zip':z.write(f,'figures/'+str(f.relative_to(out)))
        for f in data.iterdir():
            if f.is_file() and (f.suffix in ['.npz','.ply'] or f.name in ['manifest.json','selected-neurons.feather','communities.feather','JRCFIB2022M_plotting_landmarks.csv','gustatory-partners-v2.json']):z.write(f,'data/'+f.name)
        for folder in ['skeletons','projected','licenses']:
            for f in (data/folder).rglob('*'):
                if f.is_file():z.write(f,'data/'+str(f.relative_to(data)))
        # Include the unreleased APIs rather than requiring an unavailable PyPI version.
        for f in (ROOT/'src').rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc':z.write(f,'library/'+str(f.relative_to(ROOT)))
        for name in ['pyproject.toml','README.md','LICENSE','THIRD_PARTY_NOTICES.md','CHANGELOG.md','docs/scientific-authoring.md','examples/scientific_authoring.py','tests/test_scientific_authoring.py','tests/test_scientific_recipes.py']:
            z.write(ROOT/name,'library/'+name)
    with zipfile.ZipFile(target) as z:
        assert not any(n.endswith(('.jpg','.jpeg')) or 'trace-cache' in n for n in z.namelist())
        assert z.testzip() is None
        print(json.dumps({'files':len(z.namelist()),'MiB':round(target.stat().st_size/2**20,1),'reference_images':0,'integrity':'passed'}))

if __name__=='__main__':main()

"""Export the dense native review as an offline compiled-scene browser viewer."""
import argparse
from pathlib import Path
from dense_scatter_review import make_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/compiled-scene-viewer'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    compiled=make_document().compile()
    if any(d.severity=='error' for d in compiled.diagnostics):raise RuntimeError(compiled.report())
    (args.output/'index.html').write_text(compiled.scene.to_html(title='Packed vector observations'),encoding='utf-8')
    compiled.save(args.output/'native.svg',args.output/'native.pdf',args.output/'native.png')
    print(args.output/'index.html')


if __name__=='__main__':main()

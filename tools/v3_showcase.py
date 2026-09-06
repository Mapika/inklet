"""Build a reusable Blender scene and a complete mixed-rendering figure."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from inklet.three.blender import find_blender


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/v3')
    parser.add_argument('--rebuild-scene',action='store_true',help='Regenerate the authored laboratory scene')
    parser.add_argument('--scene',type=Path,help='Use an existing copy of the laboratory scene')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    scene=args.scene.resolve() if args.scene else output/'lab.blend'
    if not args.scene and (args.rebuild_scene or not scene.is_file()):
        subprocess.run([str(find_blender().path),'--background','--factory-startup',
                        '--python',str(ROOT/'examples/blender/lab_scene.py'),'--',str(scene)],
                       check=True,timeout=60,capture_output=True)
    spec=importlib.util.spec_from_file_location('v3_example',ROOT/'examples/v3_rendering.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    compiled=module.make_document(scene).compile()
    errors=[d for d in compiled.diagnostics if d.severity=='error']
    if errors:raise RuntimeError(errors)
    files=compiled.export(output/'showcase')
    print(compiled.report());print(files['review']);return 0


if __name__=='__main__':raise SystemExit(main())

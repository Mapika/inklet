"""Install a wheel's render extra and exercise browser-free exports in isolation."""
import argparse
from pathlib import Path
import os
import subprocess
import tempfile
import venv

SCRIPT='''from io import BytesIO
from pathlib import Path
import sys
from PIL import Image
import inklet as i
assert Path(i.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
doc=i.document(width=89)
doc.add('paint',i.paint(i.circle(width=25,height=25),i.LinearGradient(((0,'white'),(1,'#245b8a')))))
doc.add('label',i.component(i.text,'Installed render wheel'))
fig=doc.compile()
fig.save('figure.svg','figure.pdf')
png=fig.to_png(dpi=254)
assert Image.open(BytesIO(png)).width==890
assert b'/ShadingType 2' in Path('figure.pdf').read_bytes()
assert 'Installed render wheel' in Path('figure.svg').read_text()
fig.export('bundle',compare_pdf=False)
if len(sys.argv)>1:
    result=i.render_blend(sys.argv[1],width=50,camera='Overview',dpi=60,samples=2,
                          engine='CYCLES',landmarks={'connector':'Connector'},cache='cache')
    assert result.diagram.prim.data.startswith(b'\\x89PNG')
    assert result.metadata['landmarks']['connector']['in_frame']
print('Installed render extra: PNG, SVG, PDF, review and optional Blender scene passed',i.__version__)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    parser.add_argument('--scene',type=Path,help='Optional generated laboratory .blend file')
    args=parser.parse_args();wheel=args.wheel.resolve()
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','VIRTUAL_ENV')}
    with tempfile.TemporaryDirectory(prefix='inklet-render-wheel-') as scratch:
        root=Path(scratch);venv.EnvBuilder().create(root/'env')
        python=root/'env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        subprocess.run(['uv','pip','install','--python',str(python),str(wheel)+'[render]'],check=True,env=env,cwd=root,timeout=180)
        (root/'author.py').write_text(SCRIPT)
        subprocess.run([str(python),'author.py',*([str(args.scene.resolve())] if args.scene else [])],
                       check=True,env=env,cwd=root,timeout=300)
    return 0


if __name__=='__main__':raise SystemExit(main())

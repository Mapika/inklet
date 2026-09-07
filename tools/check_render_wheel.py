"""Install a wheel's render extra and exercise browser-free exports in isolation."""
import argparse
from pathlib import Path
import os
import shutil
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
if len(sys.argv)>1 and sys.argv[1]!='--templates':
    inventory=i.inspect_blend(sys.argv[1])
    assert inventory['scenes']
    result=i.render_blend(sys.argv[1],width=50,camera='Overview',dpi=60,samples=2,
                          engine='CYCLES',landmarks={'connector':'Connector'},cache='cache',
                          passes=('depth','normal','object_id'),quality='draft')
    assert result.diagram.prim.data.startswith(b'\\x89PNG')
    assert result.metadata['landmarks']['connector']['in_frame']
    assert result.passes['depth'].value(0,0) > 0
    assert result.passes['normal'].channels == 3
    assert result.metadata['sampling']['denoise'] is True
    assert result.metadata['execution']['requested']=='AUTO'
    world=result.metadata['landmarks']['connector']['world']
    projected=result.project(world)
    assert projected.in_frame
    path=result.path3d([world,[world[0]+1,world[1],world[2]]],hidden='dash',stroke='red')
    assert '<image' not in i.to_svg(path)
    assert i.to_pdf(path).startswith(b'%PDF')
    label=result.annotate3d(world,'Connector',hidden='show',side='e',clear=5)
    measure=result.dimension3d(world,[world[0]+.2,world[1],world[2]],hidden='show',scale=100,unit='mm')
    assert abs(measure.notes['scene_annotation']['value']-20)<1e-8
    assert '<image' not in i.to_svg(label)
    assert i.to_pdf(measure).startswith(b'%PDF')
    with i.RenderQueue(max_workers=2) as queue:
        jobs=[queue.submit(sys.argv[1],width=50,camera='Overview',dpi=60,samples=2,
            engine='CYCLES',cache='queue-cache') for _ in range(2)]
        snapshots=[job.result() for job in jobs]
    assert sorted(r.cache_hit for r in snapshots)==[False,True]
if '--templates' in sys.argv:
    for name,definition in i.scene_templates().items():
        path=i.create_scene(name,name+'.blend')
        result=i.render_blend(path,width=40,dpi=60,samples=2,camera='Overview',
            landmarks=definition['landmarks'])
        assert result.metadata['template']['name']==name
        assert result.diagram.prim.data.startswith(b'\\x89PNG')
print('Installed render extra: PNG, SVG, PDF, review and optional Blender scene passed',i.__version__)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    parser.add_argument('--scene',type=Path,help='Optional generated laboratory .blend file')
    parser.add_argument('--templates',action='store_true',help='Create and render packaged templates with Blender')
    args=parser.parse_args();wheel=args.wheel.resolve()
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','VIRTUAL_ENV')}
    with tempfile.TemporaryDirectory(prefix='inklet-render-wheel-') as scratch:
        root=Path(scratch);uv=shutil.which('uv')
        venv.EnvBuilder(with_pip=uv is None).create(root/'env')
        python=root/'env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        install=([uv,'pip','install','--python',str(python)] if uv else
                 [str(python),'-m','pip','install','--disable-pip-version-check'])
        subprocess.run([*install,str(wheel)+'[render]'],check=True,env=env,cwd=root,timeout=180)
        (root/'author.py').write_text(SCRIPT)
        subprocess.run([str(python),'author.py',*([str(args.scene.resolve())] if args.scene else []),
                        *(['--templates'] if args.templates else [])],
                       check=True,env=env,cwd=root,timeout=300)
    return 0


if __name__=='__main__':raise SystemExit(main())

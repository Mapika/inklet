"""Install a wheel with core dependencies and exercise public authoring/export APIs."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv

SCRIPT = '''from importlib.metadata import version
from importlib.util import find_spec
from pathlib import Path
import sys
import inklet as i
assert i.__version__ == version("inklet")
assert Path(i.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert find_spec("PIL") is None and find_spec("numpy") is None
assert find_spec("resvg_py") is None
import struct
depth = i.ScenePass('depth', (1, 1), 1, 10, 10, struct.pack('<f', 2.5))
assert depth.value(0, 0) == 2.5
assert i.render_quality('final').samples == 256
try:
    depth.to_numpy()
except i.DiagramError as error:
    assert 'inklet[images]' in str(error)
else:
    raise AssertionError('Pass arrays unexpectedly imported NumPy')
def make_document():
    data = i.dataset({"x": [0, 1, 2], "y": [1, 3, 2]}, name="wheel smoke")
    p = i.plot_spec(x=(0, 2), y=i.shared_scale(data.column("y")))
    p.line(data.points("x", "y")).axes(x="Time", y="Value")
    panels = i.subfigure().letters()
    panels.add("response", p)
    art = i.composition(100, 25)
    art.add("input", i.module("Input"), x=2, y=3)
    x, y = art.point("input", "out")
    art.add("output", i.module("Output"), x=x+10, y=3)
    art.link("input:out", "output:in")
    doc = i.publication("single-column", width=110).document()
    doc.add("architecture", art, min_height=30)
    doc.add("panels", panels)
    return doc
if __name__ == "__main__":
    compiled = make_document().compile()
    compiled.save("smoke.svg", "smoke.pdf")
    assert Path("smoke.pdf").read_bytes().startswith(b"%PDF")
    assert "<svg" in Path("smoke.svg").read_text()
    assert compiled.metadata["datasets"][0]["name"] == "wheel smoke"
    preset_doc = i.preset("educational.textbook").document()
    preset_doc.add("plot", i.plot_spec(x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)]).axes())
    before = preset_doc.compile()
    preset_doc.use_preset("marketing.report")
    after = preset_doc.compile()
    assert before.to_svg() != after.to_svg()
    assert after.metadata["preset"]["name"] == "marketing.report"
    assert after.to_pdf().startswith(b"%PDF")
    brush = i.LinearGradient(((0, "white"), (1, "#245b8a")))
    painted = i.paint(i.circle(width=15, height=15), brush)
    assert "linearGradient" in i.to_svg(painted)
    assert b"/ShadingType 2" in i.to_pdf(painted)
    try:
        i.to_png(painted)
    except i.DiagramError as error:
        assert "inklet[render]" in str(error)
    else:
        raise AssertionError("PNG unexpectedly works without its optional renderer")
    with i.RenderQueue(max_workers=1): pass
    assert i.RenderProgress('queued','Waiting').fraction is None
    print("Installed wheel API passed", i.__version__)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    args=parser.parse_args();wheel=args.wheel.resolve()
    if not wheel.is_file():parser.error(f'wheel not found: {wheel}')
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP','VIRTUAL_ENV')}
    with tempfile.TemporaryDirectory(prefix='inklet-wheel-') as scratch:
        root=Path(scratch);uv=shutil.which('uv')
        venv.EnvBuilder(with_pip=uv is None).create(root/'env')
        python=root/'env'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        def run(*args):
            subprocess.run([str(python),*map(str,args)],cwd=root,env=env,check=True,timeout=180)
        if uv:
            subprocess.run([uv,'pip','install','--python',str(python),str(wheel)],
                           cwd=root,env=env,check=True,timeout=180)
        else:
            run('-m','pip','install','--disable-pip-version-check',wheel)
        (root/'author.py').write_text(SCRIPT)
        run('author.py')
        run('-m','inklet','doctor')
        run('-m','inklet','build','author.py','--vectors-only','--output','review')
        assert (root/'review/figure.svg').is_file() and (root/'review/figure.pdf').is_file()
    return 0


if __name__=='__main__':raise SystemExit(main())

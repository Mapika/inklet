"""Create a deterministic dense scene for per-marker browser culling studies."""
import argparse
from pathlib import Path
import random
import inklet as i


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=250_000)
    parser.add_argument('--output',type=Path,default=Path('out/culling-review'))
    parser.add_argument('--runtime',type=Path,help='Reference runtime.js for a before/after comparison')
    args=parser.parse_args()
    if args.count<256:parser.error('--count must be at least 256')
    rng=random.Random(3412)
    p=i.panel(80,60,x=(-100,100),y=(-100,100))
    points=[(rng.uniform(-100,100),rng.uniform(-100,100)) for _ in range(args.count)]
    p.scatter(points,size=[rng.uniform(.08,.22) for _ in points],color=['#245b8a' if k%2 else '#c87942' for k in range(args.count)],stroke='none',fill_opacity=.3)
    p.axes(x='Coordinate x',y='Coordinate y')
    figure=i.figure(width=100);figure.add(p.build())
    scene=i.compile_scene(figure.build()[0])
    page=scene.to_html(title=f'{args.count:,} simulated observations')
    if args.runtime:
        import inklet.experimental.scene_viewer as viewer
        current=(Path(viewer.__file__).parent/'runtime.js').read_text()
        assert page.count(current)==1
        page=page.replace(current,args.runtime.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'index.html').write_text(page,encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()

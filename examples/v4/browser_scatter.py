"""Build an offline scatter-renderer study; restore browser view JSON in Python."""
import argparse
import json
import math
from pathlib import Path
import random

from inklet.experimental.selection import KeyedTable
from inklet.experimental.browser import BrowserScatter, ScatterView


def make_scene(count=3000):
    if not 1<=count<=50000: raise ValueError('count must be between 1 and 50000')
    rng=random.Random(20260908)
    x=[rng.uniform(-.5,10.5) for _ in range(count)]
    y=[math.sin(v)+rng.gauss(0,.2) for v in x]
    z=[math.cos(v)+rng.gauss(0,.2) for v in x]
    # Deliberate outside-domain and missing observations exercise clipping.
    if count>=4:x[:4]=[0,10,-.03,10.03];y[:4]=[0,.5,0,.5]
    if count>=5:y[4]=None
    table=KeyedTable('scatter-study',dict(id=[f'row-{n:05d}' for n in range(count)],x=x,signal=y,response=z))
    return BrowserScatter(table,[
        ScatterView('signal','x','signal',(0,10),(-1.5,1.5),'Input / s','Signal / a.u.'),
        ScatterView('response','x','response',(0,10),(-1.5,1.5),'Input / s','Response / a.u.')])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=3000)
    parser.add_argument('--output',type=Path,default=Path('out/v4-browser'))
    parser.add_argument('--state',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    scene=make_scene(args.count)
    state=json.loads(args.state.read_text(encoding='utf-8')) if args.state else scene.state()
    (args.output/'figure.svg').write_text(scene.to_svg(state),encoding='utf-8')
    (args.output/'view.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8')
    (args.output/'index.html').write_text(scene.to_html(title='Linked observations',backend='hybrid'),encoding='utf-8')
    (args.output/'scene.json').write_text(json.dumps(scene.payload(),separators=(',',':')),encoding='utf-8')
    print(args.output/'index.html')


if __name__=='__main__':main()

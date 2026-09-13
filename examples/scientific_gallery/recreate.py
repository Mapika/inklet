"""Rebuild two original scientific plates from released connectome data."""
from pathlib import Path
import argparse,json
import inklet as i
from inklet.render.raster import save_png
from inklet.render.scene import compile_scene
from data import Data,ROOT

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,default=ROOT/'out/inspo-recreated/data');parser.add_argument('--output',type=Path,default=ROOT/'out/scientific-gallery');parser.add_argument('--dpi',type=int,default=180);parser.add_argument('--page',choices=['all','olfactory','communities'],default='all');args=parser.parse_args()
    d=Data(args.data,args.output);records=[]
    previous=args.output/'validation.json'
    if args.page!='all' and previous.exists():records=[r for r in json.loads(previous.read_text()) if r['name']!=args.page]
    from dense import olfactory,communities
    for name,build in [('olfactory',olfactory),('communities',communities)]:
        if args.page not in ('all',name):continue
        print('Building '+name,flush=True);node=build(d);scene=compile_scene(node)
        svg=i.to_svg(scene,text='embed',width=240,height=312,background='white',precision=4)
        assert '<image' not in svg
        (args.output/(name+'.svg')).write_text(svg)
        i.save_pdf(scene,str(args.output/(name+'.pdf')),text='embed',width=240,height=312,background='white')
        save_png(scene,args.output/(name+'.png'),dpi=args.dpi,width=240,height=312,background='white')
        records.append({'name':name,'native_text_elements':svg.count('<text'),'embedded_images':svg.count('<image'),'panels':node.notes['panel_mosaic']})
        print('Saved '+name,flush=True)
    (args.output/'validation.json').write_text(json.dumps(records,indent=2))

if __name__=='__main__':main()

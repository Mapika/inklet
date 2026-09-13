"""Build both pages entirely from authored Inklet marks and released anatomy.

Reference JPEGs and screenshot contours are never loaded by this program.
"""
import argparse,json
from pathlib import Path
import inklet as i
from inklet.render.raster import save_png
from anatomy import Anatomy
from canvas import Page
from anatomical_panels import draw_chemosensory,draw_dimorphism
from authored_charts import furniture,chemosensory,dimorphism,TRANSCRIBED
from chart_data import prepare
from layout import PANELS

ROOT=Path(__file__).resolve().parents[2]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/inspo-native')
    parser.add_argument('--data',type=Path,default=ROOT/'out/inspo-recreated/data')
    parser.add_argument('--page',choices=['all','chemosensory','dimorphism'],default='all')
    parser.add_argument('--dpi',type=int,default=180)
    parser.add_argument('--width',type=float,default=210)
    args=parser.parse_args();args.output.mkdir(exist_ok=True,parents=True)
    if args.width<=0 or args.dpi<=0:parser.error('width and dpi must be positive')
    from refined_data import ensure_rois, ensure_example_types
    ensure_rois(args.data)
    ensure_example_types(args.data)
    a=Anatomy(args.data);d=prepare(args.data,args.output/'chart-data')
    (args.output/'chart-data/reference-transcription.json').write_text(json.dumps({'method':'Manual approximate reading of labels and numerical marks; never pixel contours. These values are illustrative reconstructions, not recovered raw measurements.','values':TRANSCRIBED},indent=2))
    records=[]
    for name,anatomical,charts in [('chemosensory',draw_chemosensory,chemosensory),('dimorphism',draw_dimorphism,dimorphism)]:
        if args.page not in ['all',name]:continue
        print('Building '+name,flush=True)
        p=Page(name,args.output);anatomical(p,a);charts(p,a,d);furniture(p)
        node=p.root(args.width);opts=dict(width=args.width,height=args.width*p.height/p.width,background='white',precision=5)
        for fmt,fn in [('svg',i.save_svg),('pdf',i.save_pdf)]:
            fn(node,str(args.output/(name+'.'+fmt)),text='embed',title='Independently drawn Inklet / '+name,**opts);print('Saved '+fmt,flush=True)
        save_png(node,args.output/(name+'.png'),dpi=args.dpi,**opts);print('Saved png',flush=True)
        records.append(dict(name=name,panels=len(PANELS[name]),native_labels=p.labels,source_image_reads=0))
    if args.page!='all' and (args.output/'recreation.json').exists():
        previous=json.loads((args.output/'recreation.json').read_text()).get('pages',[])
        records += [v for v in previous if v['name']!=args.page]
        records.sort(key=lambda v:v['name'])
    evidence={'pages':records,'method':'All charts, text, schematic insects, axes and diagrams are authored as native Inklet objects. Anatomy derives from released SWCs and meshes. No reference images or reference contour caches are used.',
      'data':'chart-data/computed-provenance.json and chart-data/reference-transcription.json',
      'limitations':['Manual chart readings are approximate; this is a visual reconstruction, not a reproduction of every original scientific analysis.',
      'The synapse comparison uses observed male locations colored by signed male/female edge-weight contrast. It does not reconstruct the female spatial density.',
      'The hierarchy diagram uses illustrative intermediate partitions with actual final community sizes; it is not the original inferred SBM hierarchy.',
      'Adjacency and graph panels aggregate released connections by community; camera choices, sensory display subsets and recomputed downstream partners can differ from the paper.']}
    (args.output/'recreation.json').write_text(json.dumps(evidence,indent=2))
    from panel_review import write
    write(args.output)
if __name__=='__main__':main()

"""Rebuild published figures as native Inklet marks, never reference screenshots."""
from pathlib import Path
import argparse,importlib,json,time
import inklet as i
ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--figure',choices=['immune','sample','quantum'],action='append')
    parser.add_argument('--references',type=Path,default=ROOT/'out/paper-recreations/references');parser.add_argument('--output',type=Path,default=ROOT/'out/paper-recreations');parser.add_argument('--dpi',type=int,default=220)
    parser.add_argument('--review-bundle',action='store_true',help='Export native diagnostic/provenance comparisons beside each figure')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    for name in args.figure or ['immune','sample','quantum']:
        start=time.perf_counter();print('Building',name,flush=True)
        i.use_theme('nature')
        page,measurements=importlib.import_module(name).build(args.references)
        art=page.build();scene=i.compile_scene(art);svg=scene.to_svg(text='embed',background='white');assert '<image' not in svg
        (args.output/f'{name}.svg').write_text(svg)
        (args.output/f'{name}.pdf').write_bytes(scene.to_pdf(text='embed'))
        (args.output/f'{name}.png').write_bytes(i.to_png(scene,dpi=args.dpi,background='white'))
        report={'name':name,'measurements':measurements,'panels':page.panels,'native_text_elements':svg.count('<text'),'embedded_images':0,'scene_stats':dict(scene.stats),'seconds':time.perf_counter()-start}
        (args.output/f'{name}.json').write_text(json.dumps(report,indent=2));print('Saved',name,round(report['seconds'],2),flush=True)
        if args.review_bundle:
            sources=json.loads((Path(__file__).parent/'sources.json').read_text())
            paper=next(p for p in sources['papers'] if p['id']==name)
            evidence=[{**item,'path':args.references/item['filename'],'license':paper['license'] if 'springernature' in item['url'] else 'See author repository license'}
                      for item in sources['files'] if item['filename'].startswith(name+'-')]
            i.review_figure(art,rules=['OFF_CANVAS','TINY_TEXT'],
                            page=page.area).save_bundle(
                args.output/f'{name}-review',reference=args.references/f'{name}-original.png',
                sources=evidence,panels=page.panel_nodes,dpi=args.dpi,
                reference_regions={key:[box[0]/page.width,box[1]/page.height,
                                       (box[0]+box[2])/page.width,(box[1]+box[3])/page.height]
                                   for key,record in page.panels.items() for box in [record['box']]},
                caption=f"{paper['authors']}, {paper['journal']}, Figure {paper['figure']} — Inklet reproduction")


if __name__=='__main__':main()

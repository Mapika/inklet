"""Compare point, sampled-region and crossing-aware plans across four scenes.

A small deterministic experiment, not a perceptual-quality benchmark. Geometry
comes from original Inklet templates and the original complex laboratory.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time

import inklet as i
from inklet.experimental.figure_planner import Region, SlotLock, Target, View, plan
from inklet.three.blender import find_blender
from research_figure_planner import build_scene, render_views, targets_for
from v3_complex_scene import create_lab

ROOT = Path(__file__).resolve().parents[1]


def front_samples(x, y, z, half_width, half_height):
    return tuple((x+half_width*u/2, y, z+half_height*v) for u in range(-2,3) for v in (-1,0,1))


def template_targets(name, views):
    world = views[0].render.metadata['landmarks']
    targets = [Target(key,key.title(),world[key]['world']) for key in world if not key.startswith('width_')]
    if name == 'laboratory':
        # Controller x follows the recipe's radius-dependent offset.
        x = world['controller']['world'][0]
        samples = front_samples(x,-.5825,.9,.25,.10)
        regions = {'controller': Region(samples,.7,8)}
    elif name == 'product':
        regions = {'display': Region(front_samples(-2.8*.16,-.9925,.28+1.1*.6,.45,.14),.7,8)}
    else:
        samples = tuple((x,-4.2*.24+y,.521) for x in (-.65,-.325,0,.325,.65) for y in (-.22,0,.22))
        regions = {'table': Region(samples,.7,8)}
        # Choose actual exposed surfaces; the template's table point is under
        # the book, and its window point lies inside the centre mullion.
        targets = [replace(t,world=(-.5,-4.2*.24,.521)) if t.id == 'table' else
                   replace(t,world=(0,4.2/2-.01,t.world[2])) if t.id == 'window' else t for t in targets]
    return tuple(replace(t,region=regions.get(t.id)) for t in targets)


def build_cases(output, blender, quality):
    catalog = i.scene_templates()
    for name in ('laboratory','product','architecture'):
        path = output/(name+'.blend')
        if not path.exists():
            i.create_scene(name,path,blender=blender)
        with i.RenderQueue(max_workers=2,max_gpu_jobs=1) as queue:
            jobs = {camera: queue.submit(path,camera=camera,width=120,height=87,
                quality=quality,dpi=330,engine='CYCLES',passes=('depth',),
                landmarks=catalog[name]['landmarks'],blender=blender) for camera in catalog[name]['cameras']}
            views = tuple(View(camera,job.result()) for camera,job in jobs.items())
        yield name, template_targets(name,views), views, .04, catalog[name]['metres_per_unit']
    path = output/'complex.blend'
    if not path.exists():
        source = output/'complex-source.blend'
        create_lab(source,blender)
        build_scene(source,path,'original',blender)
    views = render_views(path,blender,quality)
    targets = tuple(replace(t,region=Region(front_samples(2.3,1.6575,1.82,.36,.20),.7,8))
                    if t.id=='control-display' else t for t in targets_for(views))
    yield 'complex-laboratory', targets, views, .04, 1.


def crossing_revision(targets, views, output):
    """Deliberately crossed author preferences; no natural-case quality claim."""
    selected = tuple(t for t in targets if t.id in ('probe','controller'))
    front = tuple(v for v in views if v.id=='Front')
    options = dict(width=180,image_scales=(.8,),depth_bias=.04)
    prior = plan(selected,front,**options,locks=(SlotLock('probe','Front','e',10),
                                               SlotLock('controller','Front','e',2)))
    if not prior.feasible:
        raise RuntimeError('Controlled author slots are infeasible: '+str(prior.issues))
    results = {method: plan(selected,front,**options,previous=prior,move_penalty=1000,
        locks=(SlotLock('probe','Front','e',10),),crossing_penalty=penalty)
        for method,penalty in (('history-only',0),('crossing-penalty',5000))}
    if not all(p.feasible for p in results.values()):
        raise RuntimeError('The controlled revision could not be planned')
    doc=i.document(width=390,columns=2,margin=8,gap=12)
    doc.add('title',i.text('Controlled revision / preserving an author lock',size=i.pt(20)),colspan=2)
    for col,(method,result) in enumerate(results.items()):
        count=len(result.report()['crossing_pairs'])
        doc.add('heading-'+method,i.text(f'{method.replace("-"," ").title()} / {count} crossing {"pair" if count==1 else "pairs"}',size=i.pt(10)),row=1,column=col)
        doc.add(method,result.diagram(show_regions=True),row=2,column=col)
    doc.add('caption',i.text('Probe slot stays locked. The controller may move. Crossing and revision penalties are deliberately high.',size=i.pt(9)),colspan=2)
    doc.compile().export(output/'crossing-revision',dpi=150)
    return dict(description='Deliberately crossed prior slots; same scene and page. One hard probe lock.',
                prior=prior.report(),cases={name:p.report() for name,p in results.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/research-study')
    parser.add_argument('--blender',type=Path)
    parser.add_argument('--quality',choices=('draft','preview','final'),default='final')
    args = parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    blender = find_blender(args.blender).path
    records, examples, controlled = [], [], None
    for name, targets, views, bias, units in build_cases(args.output,blender,args.quality):
        print('Rendered',name,flush=True)
        if name=='laboratory':
            controlled=crossing_revision(targets,views,args.output)
        chosen = None
        for width in (120,180,240):
            for method in ('point','region','region+crossings'):
                required = () if name != 'complex-laboratory' else ('Overview',)
                selected_targets = tuple(replace(t,region=None) for t in targets) if method=='point' else targets
                start = time.perf_counter()
                result = plan(selected_targets,views,width=width,max_height=260,
                    max_views=2,depth_bias=bias,required_views=required,
                    crossing_penalty=25 if method=='region+crossings' else 0)
                elapsed = time.perf_counter()-start
                record = dict(scene=name,method=method,width_mm=width,planning_seconds=elapsed,
                    metres_per_unit=units,quality=args.quality,
                    renders={v.id: dict(blender=v.render.metadata['blender'],
                        execution=v.render.metadata['execution'],pixels=v.render.metadata['pixels']) for v in views},
                    plan=result.report())
                records.append(record)
                print(name,width,method,result.feasible,result.views,len(record['plan']['crossing_pairs']),flush=True)
                if method=='region+crossings' and result.feasible and (chosen is None or width==180):
                    if chosen is None or width<=180:
                        chosen=result
        if chosen:
            examples.append((name,chosen))
            doc=i.document(width=chosen.width+10,margin=5)
            doc.add('scene',chosen.diagram(show_regions=True));doc.compile().export(args.output/name,dpi=150)
    evidence=dict(schema='inklet.planner-study/0.1',inklet_version=i.__version__,
        description='Four original scenes, three page widths, three methods. No perceptual-quality claim.',
        controlled_revision=controlled,cases=records)
    (args.output/'study.json').write_text(json.dumps(evidence,indent=2)+'\n')
    doc=i.document(width=390,columns=2,margin=8,gap=12)
    doc.add('title',i.text('Research preview / sampled regions',size=i.pt(22)),colspan=2)
    doc.add('subtitle',i.text('Four scenes, three page widths, explicit visibility and projected-size requirements.',size=i.pt(9)),colspan=2)
    for index,(name,result) in enumerate(examples):
        row,col=2+(index//2)*3,index%2
        doc.add('heading-'+name,i.text(name.replace('-',' ').title(),size=i.pt(12)),row=row,column=col)
        doc.add(name,result.diagram(show_regions=True),row=row+1,column=col)
        stats=result.report()
        doc.add('stats-'+name,i.text(f'{len(result.placements)} labels / {len(result.views)} {"view" if len(result.views)==1 else "views"} / {len(stats["crossing_pairs"])} crossing pairs',size=i.pt(8)),row=row+2,column=col)
    doc.add('caption',i.text('Sample markers: teal visible, amber hidden. Sample coverage does not establish object recognition.',size=i.pt(9)),colspan=2)
    figure=doc.compile();print(figure.report());figure.export(args.output,dpi=150)


if __name__=='__main__':main()

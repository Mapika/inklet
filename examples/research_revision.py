"""Controlled page revision with soft and hard physical label-movement controls."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

import inklet as i
from inklet.experimental.figure_planner import SlotLock, View, plan
from research_planner_study import template_targets

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/research-revision')
    parser.add_argument('--scene',type=Path)
    parser.add_argument('--blender',type=Path)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    source=args.scene or args.output/'laboratory.blend'
    if not source.exists(): i.create_scene('laboratory',source,blender=args.blender)
    rendered=i.render_blend(source,camera='Front',width=120,height=87,dpi=330,
        quality='final',engine='CYCLES',passes=('depth',),
        landmarks=i.scene_templates()['laboratory']['landmarks'],blender=args.blender)
    views=(View('Front',rendered),)
    targets=tuple(t for t in template_targets('laboratory',views) if t.id in ('probe','controller'))
    targets=tuple(replace(t,region=replace(t.region,min_span_mm=6)) if t.region else t for t in targets)
    prior=plan(targets,views,width=180,image_scales=(.8,),depth_bias=.04,
        locks=(SlotLock('probe','Front','e',10),SlotLock('controller','Front','e',2)))
    if not prior.feasible: raise RuntimeError(str(prior.issues))
    options=dict(width=170,image_scales=(.8,),depth_bias=.04,previous=prior,move_penalty=0,
                 locks=(SlotLock('probe','Front','e',10),))
    cases={name:plan(targets,views,**options,**controls) for name,controls in (
        ('free',{}),('movement-cost',dict(displacement_penalty=10)),
        ('limit-15-mm',dict(max_displacement_mm=15)),('zero-limit',dict(max_displacement_mm=0)))}
    doc=i.document(width=390,columns=2,margin=8,gap=12)
    doc.add('title',i.text('Page revision / control movement in millimetres',size=i.pt(20)),colspan=2)
    for index,(name,result) in enumerate([('prior',prior)]+list(cases.items())[:3]):
        if not result.feasible: raise RuntimeError(name+': '+str(result.issues))
        row,col=1+(index//2)*3,index%2
        distances=result.report()['constraints']['revision_displacement_mm']
        doc.add(name+'-title',i.text({'prior':'Prior author slots','free':'Free revision','movement-cost':'Movement cost / 10 per mm','limit-15-mm':'Hard limit / 15 mm'}[name],size=i.pt(11)),row=row,column=col)
        doc.add(name,result.diagram(show_regions=True),row=row+1,column=col)
        caption=f'{result.width:g} mm page / '+('Author-specified starting slots' if not distances else
            f'Maximum label movement: {max(distances.values()):.2f} mm')
        doc.add(name+'-stats',i.text(caption,size=i.pt(8)),row=row+2,column=col)
    doc.add('caption',i.text('Controlled prior preferences; page narrows from 180 to 170 mm. Probe slot remains locked. '
        'A zero-movement limit rejects this revision.',size=i.pt(8)),colspan=2)
    figure=doc.compile();print(figure.report());figure.export(args.output,dpi=150)
    record=dict(schema='inklet.revision-study/0.1',inklet_version=i.__version__,
        description='Controlled prior slots, unchanged scene, narrower page. No typical-case quality claim.',
        render=dict(blender=rendered.metadata['blender'],execution=rendered.metadata['execution']),
        prior=prior.report(),cases={name:p.report() for name,p in cases.items()})
    (args.output/'revision.json').write_text(json.dumps(record,indent=2)+'\n')
    for name,p in cases.items(): print(name,p.feasible,p.report()['constraints'].get('revision_displacement_mm'))
    if cases['zero-limit'].feasible: raise RuntimeError('Zero movement unexpectedly feasible')


if __name__=='__main__':main()

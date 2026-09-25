"""Original simulated cross-content project: edit, bundle, reopen and revise."""
from pathlib import Path
import argparse
import json

import inklet as i
from inklet.project import AssetManifest, EntityMap, FigureProject
from inklet.selection import KeyedTable
from inklet.experimental.measurement import LabelImage
from inklet.experimental.browser import BrowserFigure, ScatterView, DrawingView, DrawingItem, LabelImageView


def write_inputs(root, *, revised=False, remove=False):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    records = [dict(id='sample-a', entity='a', value=4 if revised else 2),
               dict(id='sample-b', entity='b', value=3)]
    if remove:
        records.pop()
    (root/'measurements.json').write_text(json.dumps(records)+'\n')
    (root/'calibration.json').write_text(json.dumps(dict(spacing_yx=[1.,1.],unit='um'))+'\n')
    return root


def inputs(root):
    records = json.loads((Path(root)/'measurements.json').read_text())
    calibration = json.loads((Path(root)/'calibration.json').read_text())
    entities = [r['entity'] for r in records]
    table = KeyedTable('measurements', dict(id=[r['id'] for r in records], value=[r['value'] for r in records]))
    image = LabelImage(tuple((r['value'], r['value']+1) for r in records),
                       tuple((n+1,n+1) for n in range(len(records))),
                       tuple((f'region-{e}',n+1) for n,e in enumerate(entities)), tuple(calibration['spacing_yx']), calibration['unit'])
    identities = EntityMap(entities, {
        'measurements': {r['id']:r['entity'] for r in records},
        'image': {f'region-{e}':e for e in entities},
        'objects': {f'object-{e}':e for e in entities},
        'composition': {f'/{kind}/{e}':e for kind in ('diagram','mesh') for e in entities},
    })
    return table, image, identities


def recipe(root):
    table, image, identities = inputs(root)
    result = i.composition(160,105)
    plot = i.plot_spec(x=(0,3), y=(0,6)).line([(n+1,v) for n,v in enumerate(table.columns['value'])],key='response').axes(x='Sample',y='Supplied value')
    result.add('plot',plot,x=12,y=9,anchor='area-nw',width=result.page_width/2-20,height=32)
    diagram = i.composition(65,30)
    mesh = i.composition(65,30)
    for n,entity in enumerate(identities.entities):
        diagram.add(entity,i.module(f'Part {entity}',min_width=20),x=5+n*28,y=10)
        mesh.add(entity,i.component(i.solid,'cube',width=16,height=16,style='shaded'),x=14+n*28,y=15)
    result.add('diagram',diagram,x=result.page_width/2+4,y=10)
    result.add('image',i.panel(28,28*image.extent[1]/image.extent[0]).matrix(image.intensity,ramp=i.ramp(['#eef4ee','#245b8a']),scale=i.linear((0,6))).build(),x=20,y=70)
    result.add('mesh',mesh,x=result.page_width/2+4,y=62)
    for key,label,x,y in [('diagram','Diagram objects',result.page_width/2+4,4),('image','Source pixels (simulated)',6,49),('mesh','Native models',result.page_width/2+4,57)]:
        result.add(key+'_title',i.component(i.text,label,size=2.5),x=x,y=y)
    return result


def manifest(root):
    return AssetManifest.capture(root,[dict(id='measurements',path='measurements.json',
        source='Original simulated Inklet acceptance fixture',license='MIT',unit='arbitrary',role='measurements'),
        dict(id='calibration',path='calibration.json',source='Declared simulated pixel spacing',
             license='MIT',unit='um',role='calibration')])


def project(root):
    return FigureProject('Mixed content study',recipe(root),assets=manifest(root),identities=inputs(root)[2])


def linked(root, *, width=190):
    table,image,identities = inputs(root)
    objects = KeyedTable('objects',dict(id=list(identities.sources['objects']),size=[1]*len(identities.entities)))
    joined = identities.joined_table('study',{'measurements':table,'image':image.table(),'objects':objects})
    def drawing(table,w,h):
        return [DrawingItem((key,),i.box(f'Part {identities.sources["objects"][key]}',width=20,height=10).translated((n+.5)*w/len(table.row_ids),20))
                for n,key in enumerate(table.row_ids)]
    return BrowserFigure(joined,[
        ScatterView('response','image__area','measurements__value',(0,4),(0,6)),
        identities.view('image',image.table(),LabelImageView('pixels',image,(0,6),1)),
        identities.view('objects',objects,DrawingView('parts',drawing))],width=width)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('out/project-workflow'))
    args=parser.parse_args();root=write_inputs(args.output/'inputs')
    study=project(root)
    study.editor.command('edit',{'path':'/diagram/a','placement':{'x':8}})
    study.editor.command('edit',{'path':'/mesh/a','cameras':{'view':{'kind':'native-orbit','azimuth':20}}})
    study.select('image',['region-a'])
    bundle=study.save(args.output/'bundle',asset_root=root)
    reopened=FigureProject.open(bundle,recipe)
    assert reopened.editor.figure.to_svg()==study.editor.figure.to_svg()
    scene=linked(bundle)
    (args.output/'linked.html').write_text(scene.to_html(state=reopened.state_for(scene),title='Cross-content project'))
    (args.output/'linked.svg').write_text(scene.to_svg(reopened.state_for(scene)))
    revised_root=write_inputs(args.output/'revised-inputs',revised=True)
    revised,report=reopened.revise(recipe(revised_root),assets=manifest(revised_root),identities=inputs(revised_root)[2])
    revised.save(args.output/'revised-bundle',asset_root=revised_root)
    (args.output/'revision.json').write_text(json.dumps(report,indent=2)+'\n')
    print(bundle)


if __name__=='__main__':main()

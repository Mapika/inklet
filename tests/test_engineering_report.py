"""Geometry measurements and complete mixed drawing/plot revision workflow."""
import base64
from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path

import pytest
import inklet as i
from inklet.experimental.browser import BrowserFigure,DrawingItem,DrawingView,RevisionOption
from inklet.experimental.engineering import BoxAssembly,BoxComponent
from inklet.experimental.selection import KeyedTable,SelectionState

RECIPE=Path(__file__).resolve().parents[1]/'examples/v4/engineering_report.py'
spec=importlib.util.spec_from_file_location('engineering_report',RECIPE)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


def test_box_measurements_closed_sections_and_snapshot():
    source=json.loads(recipe.FIXTURE.read_text());assembly=BoxAssembly.from_dict(source)
    source['components'][0]['size'][0]=900
    assert assembly.size==(80,40,35)
    assert assembly.distance('sensor','support')==pytest.approx(45.89117562233506)
    assert assembly.section('y',0)==(('base',(-40,0,40,5)),('support',(-30,5,-20,35)),('sensor',(10,5,30,17)))
    assert assembly.section('z',35)==(('support',(-30,-5,-20,5)),)
    assert assembly.section('z',35.00001)==()
    with pytest.raises(FrozenInstanceError):assembly.unit='m'
    assert recipe.make_assembly('resized').size==(80,40,41)
    assert recipe.make_assembly('removed').ids==('base','sensor')
    assert recipe.make_assembly('resized').report()['geometry_digest']!=assembly.report()['geometry_digest']


@pytest.mark.parametrize('size,center',[(None,[0,0,0]),([0,1,1],[0,0,0]),([1,1,1],[0,False,0]),
    ([1,1,1],[0,float('nan'),0]),([1,1,1],[1e100,0,0]),([1,1],[0,0,0])])
def test_invalid_boxes(size,center):
    with pytest.raises(ValueError):BoxComponent('part',size,center)


def test_unsupported_geometry_and_missing_correspondences():
    source=json.loads(recipe.FIXTURE.read_text());source['components'][0]['shape']='sphere'
    with pytest.raises(ValueError,match='axis-aligned'):BoxAssembly.from_dict(source)
    box=BoxComponent('a',[1,2,3],[0,0,0])
    with pytest.raises(ValueError,match='duplicate'):BoxAssembly([box,box],'mm')
    with pytest.raises(ValueError,match='unit'):BoxAssembly([box],'pixels')
    with pytest.raises(ValueError):BoxAssembly([box],'mm').distance('a','missing')
    with pytest.raises(ValueError):BoxAssembly([box],'mm').section('yz',0)


def test_drawings_resolve_text_paint_and_stable_ids_without_shrinking_type():
    a=recipe.make_scene();b=recipe.make_scene()
    assert a.payload()==b.payload()
    state=a.state(SelectionState.for_table(a.table,selected=['sensor']))
    assert a.to_svg(state)==b.to_svg(state)
    layers=a.payload()['layers'];assert len(layers)==4
    # Dimension plate and node body colors must not leak into their text.
    import xml.etree.ElementTree as ET
    for mark in (layers[0]['marks'][-2],layers[2]['marks'][-1]):
        root=ET.fromstring(base64.b64decode(mark['href'].split(',')[1]))
        uses=[e for e in root.iter() if e.tag.endswith('use')]
        assert uses
        assert f'fill="{i.figure().theme.ink}"' in ET.tostring(root,encoding='unicode')
    smaller=recipe.make_scene(width=170)
    # Native typography is re-laid out at the smaller width, not globally scaled.
    for figure in (a,smaller):
        for layer in figure.payload()['layers'][:3]:
            for mark in layer['marks']:
                assert 'transform="scale(' not in base64.b64decode(mark['href'].split(',')[1]).decode()


def test_revision_preserves_labels_selection_responses_and_old_scene():
    labels=recipe.read_labels();labels['sensor']=(5,-9)
    original=recipe.make_scene(labels=labels);before=original.payload()
    state=original.state(SelectionState.for_table(original.table,selected=['sensor','support']))
    assembly=recipe.make_assembly('resized');table=recipe.make_table(assembly)
    revised=original.replace_data(table,views=recipe.make_views(assembly,labels),state=state)
    assert revised.report()['changed_ids']==['sensor','support']
    assert revised.figure.table.columns['at_30N']==original.table.columns['at_30N']
    assert revised.figure.payload()['layers'][0]['marks']!=before['layers'][0]['marks']
    assert original.payload()==before
    removed=recipe.make_assembly('removed');removed_table=recipe.make_table(removed)
    with pytest.raises(ValueError):original.replace_data(removed_table,views=recipe.make_views(removed,labels),state=state)
    revision=original.replace_data(removed_table,views=recipe.make_views(removed,labels),state=state,missing='drop')
    assert revision.figure.validate_state(revision.state())[0].selected_ids==('sensor',)
    for width in (170,210):
        export=revision.figure.replace_data(removed_table,state=revision.state(),width=width)
        assert export.figure.payload()['width']==width


def test_drawing_bounds_ids_and_empty_view():
    table=KeyedTable('t',dict(id=['part']))
    def check(items):return BrowserFigure(table,[DrawingView('drawing',lambda t,w,h:items)])
    with pytest.raises(ValueError,match='ID mismatch'):check([DrawingItem(('unknown',),i.box(width=5,height=5).translated(10,10))])
    with pytest.raises(ValueError,match='exceeds'):check([DrawingItem(('part',),i.box(width=5,height=5))])
    with pytest.raises(ValueError,match='hit box'):check([DrawingItem(('part',),i.box(width=5,height=5).translated(10,10),(-1,0,10,10))])
    layer=check([]).payload()['layers'][0]
    assert layer['marks']==[] and layer['drawing']['omitted_ids']==['part']


CHECKS=r'''
(async()=>{
 await inkletDocument.ready;let r=inklet;const ok=(c,m)=>{if(!c)throw Error(m);},exports=[];
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);r.select(['sensor']);
  for(const layer of r.scene.layers.slice(0,3)){
   const mark=layer.marks.find(m=>m.ids[0]==='sensor'&&m.pickable),b=mark.bounds;
   const hit=r.pick((b[0]+b[2])/2,(b[1]+b[3])/2,0);ok(hit?.id==='sensor','component picking in '+layer.name);
   ok(r.pick(layer.clip[0]-.01,layer.clip[1],0)===null,'out-of-panel picking');
   const p=new DOMPoint((b[0]+b[2])/2,(b[1]+b[3])/2).matrixTransform(r.svg.getScreenCTM());
   document.getElementById('stage').dispatchEvent(new PointerEvent('pointermove',{clientX:p.x,clientY:p.y,bubbles:true}));
   ok(document.getElementById('hover').textContent.includes('sensor'),'drawing hover');
  }
  ok([...r.drawings.values()].every(image=>image.complete&&image.naturalWidth>0),'native assets not ready');
  ok(r.selectedItems().filter(m=>m.kind==='image').length===3,'annotations duplicate selection boxes');
  exports.push({state:r.state(),svg:r.exportSVG()});
  r.setVisible(['sensor']);exports.push({state:r.state(),svg:r.exportSVG()});
 }
 r.setVisible(null);r.select(['sensor','support']);
 await inkletDocument.switchRevision(1);r=inklet;
 ok(r.scene.columns.height_mm[r.rowIndex.get('support')]===36,'dimension revision');
 let rejected=false;try{await inkletDocument.switchRevision(2);}catch(e){rejected=true;}
 ok(rejected,'removed component silently accepted');
 await inkletDocument.switchRevision(2,{missing:'drop'});r=inklet;
 ok(r.selected.has('sensor')&&!r.selected.has('support'),'removed ID reconciliation');
 r.setViewport([3,2,r.scene.width/1.3,r.scene.height/1.3]);const saved=r.state();r.select([]);r.loadState(saved);
 return {exports,revised:{state:r.state(),svg:r.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def test_browser_linked_native_drawings_revisions_and_pixels(tmp_path):
    from test_browser_series import browser_result
    from test_browser_statistics import svg_geometry
    original=recipe.make_scene();removed=recipe.make_scene('removed')
    report=browser_result(tmp_path,original,CHECKS,revisions=[
        RevisionOption('Resized',recipe.make_scene('resized'),recipe.CREDIT),
        RevisionOption('Removed',removed,recipe.CREDIT)])
    assert len(report['exports'])==6
    for export in report['exports']:
        assert svg_geometry(original.to_svg(export['state']))==svg_geometry(export['svg'])
    Image=pytest.importorskip('PIL.Image')
    from PIL import ImageChops
    from inklet.render.preview import svg_png,svg_pdf,pdf_png
    chosen=report['revised']
    for name,svg in [('python',removed.to_svg(chosen['state'])),('browser',chosen['svg'])]:
        path=tmp_path/(name+'.svg');path.write_text(svg);svg_png(path,path.with_suffix('.png'),dpi=150)
    a,b=(Image.open(tmp_path/(name+'.png')).convert('RGB') for name in ('python','browser'))
    assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None
    # Vector embedding must survive PDF conversion without rasterizing labels.
    import shutil,subprocess
    if shutil.which('pdfimages'):
        svg_pdf(tmp_path/'python.svg',tmp_path/'figure.pdf')
        images=subprocess.check_output(['pdfimages','-list',str(tmp_path/'figure.pdf')],text=True).strip().splitlines()
        assert len(images)==2


def test_report_cli_reopens_and_reports_orphaned_labels(tmp_path):
    import subprocess,sys
    labels=recipe.read_labels();labels['sensor']=[5,-9]
    path=tmp_path/'labels.json';path.write_text(json.dumps(labels))
    figure=recipe.make_scene(labels=labels)
    state=figure.state(SelectionState.for_table(figure.table,selected=['support','sensor']))
    saved=tmp_path/'view.json';saved.write_text(json.dumps(state))
    command=[sys.executable,str(RECIPE),'--labels',str(path),'--state',str(saved),'--output',str(tmp_path/'reopen')]
    result=subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'reopen/figure.svg').read_text()==figure.to_svg(state)
    result=subprocess.run([sys.executable,str(RECIPE),'--labels',str(path),'--revision','removed',
        '--rebase-state',str(saved),'--missing','drop','--output',str(tmp_path/'removed')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'removed/assembly.json').read_text())['orphaned_labels']==['support']
    assert json.loads((tmp_path/'removed/labels.json').read_text())['sensor']==[5,-9]
    assert json.loads((tmp_path/'removed/view.json').read_text())['selection']['selected_ids']==['sensor']


@pytest.mark.parametrize('ids,options', [('a',{}),([['a']],{}),(['a','a'],{}),(['a'],{'highlight':1}),
                                       (['a'],{'pickable':'yes'}),(['a'],{'hit_box':(0,0,0,10)})])
def test_invalid_drawing_identity_and_options(ids,options):
    with pytest.raises(ValueError):DrawingItem(ids,i.box(width=5,height=5),**options)


def test_native_snapshot_includes_thick_strokes_outside_layout_envelope():
    table=KeyedTable('parts',dict(id=['a']))
    def build(t,w,h):
        return [DrawingItem(('a',),i.box(width=10,height=10,pad=0,radius=0,
            fill='none',stroke='#123456',stroke_width=3,stroke_linejoin='miter').translated(w/2,h/2))]
    layer=BrowserFigure(table,[DrawingView('native',build)]).payload()['layers'][0]
    # Conservative miter bounds extend beyond the box's 10 mm layout extent.
    assert layer['marks'][0]['geometry'][2]>=23
    assert layer['marks'][0]['geometry'][3]>=23

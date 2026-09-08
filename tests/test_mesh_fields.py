"""Independent geometry, field correspondence and browser interaction checks."""
from dataclasses import FrozenInstanceError,replace
import importlib.util
import json
from pathlib import Path

import pytest
from inklet.experimental.fields import MeshField
from inklet.experimental.browser import BrowserFigure,MeshFieldView,RevisionOption
from inklet.experimental.selection import KeyedTable,SelectionState

RECIPE=Path(__file__).resolve().parents[1]/'examples/v4/mesh_fields.py'
spec=importlib.util.spec_from_file_location('mesh_fields',RECIPE)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


def field():
    return MeshField([[0,0,0],[2,0,0],[0,2,0],[2,2,2]],[[0,1,2],[1,3,2]],
                     ['a','b'],[1,None],[[3,4,12],None])


def test_snapshot_and_independent_measurements():
    f=field();data=f.table().columns
    assert data['area']==pytest.approx([2,12**.5])
    assert data['x']==pytest.approx([2/3,4/3])
    assert data['z']==pytest.approx([0,2/3])
    assert data['magnitude']==(13,None)
    source=json.loads(json.dumps(f.source()));copy=MeshField.from_dict(source);before=copy.digest
    source['vertices'][0][0]=100;source['vectors'][0][0]=99
    assert copy.digest==before==f.digest
    with pytest.raises(FrozenInstanceError):copy.unit='m'
    assert copy.mesh().groups==('a','b')


@pytest.mark.parametrize('changes',[
    {'vertices':[]},{'vertices':[[0,0,False],[2,0,0],[0,2,0],[2,2,2]]},
    {'faces':[[0,0,1],[1,2,3]]},{'faces':[[0,1,99],[1,2,3]]},
    {'faces':[[0,1,True],[1,2,3]]},{'ids':['a','a']},{'ids':['a']},
    {'scalars':[float('nan'),None]},{'scalars':[True,None]},
    {'vectors':[[1,2],None]},{'vectors':[[1.7e308]*3,None]},
    {'unit':'pixels'},{'scalar_unit':''},
])
def test_invalid_sources(changes):
    with pytest.raises(ValueError):replace(field(),**changes)


def test_measurement_join_reordering_and_stale_values():
    f=field();table=f.table()
    reorder=KeyedTable(table.name,{key:tuple(reversed(v)) for key,v in table.columns.items()})
    scene=BrowserFigure(reorder,[MeshFieldView('plan',f)])
    assert [m['ids'][0] for m in scene.payload()['layers'][0]['marks']]==['a','b']
    stale=KeyedTable(table.name,dict(table.columns)|dict(area=[2,3]))
    with pytest.raises(ValueError,match='measurement mismatch'):BrowserFigure(stale,[MeshFieldView('plan',f)])
    with pytest.raises(ValueError,match='ID mismatch'):
        f.validate_table(KeyedTable(table.name,dict(id=['other'])))


@pytest.mark.parametrize('kwargs',[{'breaks':(1,1)},{'colors':['red']},{'vectors':1},
    {'vector_scale':0},{'vector_scale':float('inf')},{'scale_bar':-1}])
def test_invalid_views(kwargs):
    with pytest.raises(ValueError):MeshFieldView('plan',field(),**kwargs)


def test_vertical_face_rejected_in_plan_but_valid_as_3d_source():
    f=MeshField([[0,0,0],[0,1,0],[0,0,1]],[[0,1,2]],['a'],[1],[None])
    assert f.table().columns['area']==(.5,)
    with pytest.raises(ValueError,match='XY projection'):MeshFieldView('plan',f)


def test_arrow_direction_scale_and_missing_zero_vectors():
    f=field();view=MeshFieldView('plan',f,vectors=True,vector_scale=.1)
    layer=BrowserFigure(f.table(),[view]).payload()['layers'][0]
    lines=[m for m in layer['marks'] if m['kind']=='line']
    assert len(lines)==3 and all(m['ids']==['a','a'] for m in lines)
    x,y,ex,ey=lines[0]['geometry'];scale=layer['field']['scale_mm_per_unit']
    assert (ex-x,ey-y)==pytest.approx((.3*scale,-.4*scale))
    assert lines[0]['pickable'] is False
    zero=replace(f,vectors=[(0,0,7),None])
    layer=BrowserFigure(zero.table(),[replace(view,field=zero)]).payload()['layers'][0]
    assert not any(m['kind']=='line' for m in layer['marks'])
    assert zero.table().columns['magnitude']==(7,None)


def test_geometry_revision_rebuild_and_selection_reconciliation():
    original=recipe.make_scene();before=original.payload();deformed=recipe.make_field('deformed')
    assert deformed.table().columns['scalar']==original.table.columns['scalar']
    assert deformed.table().columns['area']!=original.table.columns['area']
    state=original.state(SelectionState.for_table(original.table,selected=['face-19']))
    revised=original.replace_data(deformed.table(),views=recipe.make_views(deformed),state=state,width=170)
    assert revised.state()['selection']['selected_ids']==['face-19']
    assert original.payload()==before
    assert revised.figure.payload()['layers'][0]['field']['source_digest']==deformed.digest
    removed=recipe.make_field('removed')
    with pytest.raises(ValueError):original.replace_data(removed.table(),views=recipe.make_views(removed),state=state)
    assert original.replace_data(removed.table(),views=recipe.make_views(removed),state=state,missing='drop').state()['selection']['selected_ids']==[]


CHECKS=r'''
(async()=>{
 await inklet.ready;let r=inklet;const ok=(c,m)=>{if(!c)throw Error(m);},exports=[];let queries=0;
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);
  for(let panel=0;panel<2;panel++){
   const layer=r.scene.layers[panel],f=layer.field,[left,bottom,right,top]=f.extent,[ox,oy]=f.origin_mm,s=f.scale_mm_per_unit;
   for(let iy=0;iy<16;iy++)for(let ix=0;ix<24;ix++){
    const x=(ix+.37)/4,y=(iy+.61)/4,cx=Math.floor(x),cy=Math.floor(y),side=(y-cy)>(x-cx)?1:0;
    const expected='face-'+String(cy*12+cx*2+side).padStart(2,'0');
    const hit=r.pick(ox+(x-left)*s,oy+(top-y)*s,0);
    ok(hit?.id===expected,'triangle picking '+backend+' '+expected+' '+hit?.id);queries++;
   }
  }
  r.select(['face-19']);r.setVisible(['face-19']);
  ok(r.selectedItems().filter(m=>m.kind==='polygon').length===2,'linked triangle highlight');
  ok(r.items.filter(m=>m.kind==='image'&&m.reference).every(m=>r.markShown(m)),'fixed references hidden');
  exports.push({state:r.state(),svg:r.exportSVG()});
 }
 r.setVisible(null);const old=r;await inkletDocument.switchRevision(1);r=inklet;
 ok(old.disposed,'old resources not disposed');
 ok(r.scene.layers[0].field.source_digest!==old.scene.layers[0].field.source_digest,'geometry digest stale');
 r.setViewport([3,2,r.scene.width/1.3,r.scene.height/1.3]);
 return {queries,exports,revised:{state:r.state(),svg:r.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def test_browser_triangle_oracle_backends_and_export(tmp_path):
    from test_browser_series import browser_result
    from inklet.render.preview import svg_png
    from PIL import Image,ImageChops
    original=recipe.make_scene();revised=recipe.make_scene('deformed')
    result=browser_result(tmp_path,original,CHECKS,revisions=[RevisionOption('Deformed',revised,recipe.CREDIT)])
    assert result['queries']==16*24*2*3
    # Pixel comparison includes polygon fills, arrows, selection, native 3D and text.
    for n,(scene,export) in enumerate([(original,result['exports'][0]),(revised,result['revised'])]):
        for name,svg in [('python',scene.to_svg(export['state'])),('browser',export['svg'])]:
            path=tmp_path/f'{n}-{name}.svg';path.write_text(svg);svg_png(path,path.with_suffix('.png'),dpi=100)
        a,b=(Image.open(tmp_path/f'{n}-{name}.png').convert('RGB') for name in ('python','browser'))
        assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None


def test_cli_restoration_replacement_and_two_widths(tmp_path):
    import subprocess,sys
    scene=recipe.make_scene();state=scene.state(SelectionState.for_table(scene.table,selected=['face-19']))
    saved=tmp_path/'state.json';saved.write_text(json.dumps(state))
    for args,directory in [(['--state',str(saved)],'original'),
            (['--rebase-state',str(saved),'--revision','removed','--missing','drop'],'removed'),
            (['--json',str(tmp_path/'original/input.json')],'supplied')]:
        result=subprocess.run([sys.executable,str(RECIPE),'--output',str(tmp_path/directory),*args],capture_output=True,text=True,timeout=45)
        assert result.returncode==0,result.stderr
        assert (tmp_path/directory/'figure-170mm.svg').exists()
    assert (tmp_path/'original/figure.svg').read_text()==scene.to_svg(state)
    assert json.loads((tmp_path/'removed/view.json').read_text())['selection']['selected_ids']==[]
    assert json.loads((tmp_path/'supplied/field.json').read_text())['source_digest']==recipe.make_field().digest


@pytest.mark.parametrize('scale',[1e75,1e-75])
def test_representable_area_avoids_squared_norm_overflow_underflow(scale):
    f=MeshField([(0,0,0),(2*scale,0,0),(0,2*scale,0)],[(0,1,2)],['a'],[1],[None])
    assert f.table().columns['area'][0]/(2*scale*scale)==pytest.approx(1)


def test_shared_edges_overlap_filtering_and_removed_face_hole(tmp_path):
    from test_browser_series import browser_result
    f=MeshField([(0,0,0),(2,0,0),(0,2,0)],[(0,1,2),(0,1,2)],['a','b'],[1,2],[None,None])
    original=BrowserFigure(f.table(),[MeshFieldView('plan',f)])
    removed=recipe.make_scene('removed')
    checks=r"""
    (async()=>{
      await inklet.ready;const r=inklet,g=r.scene.layers[0].marks[0].geometry[0];
      const center=[(g[0][0]+g[1][0]+g[2][0])/3,(g[0][1]+g[1][1]+g[2][1])/3];
      const top=r.pick(...center,0)?.id;r.setVisible(['a']);const filtered=r.pick(...center,0)?.id;
      const edge=r.pick((g[0][0]+g[1][0])/2,(g[0][1]+g[1][1])/2,0)?.id;
      const outside=r.pick(g[1][0]-.01,g[2][1]+.01,0);
      await inkletDocument.switchRevision(1,{missing:'drop'});inklet.setVisible(null);const l=inklet.scene.layers[0],f=l.field,s=f.scale_mm_per_unit;
      // Removed face-19 is upper-left half of grid square x=3, y=1.
      const hit=inklet.pick(f.origin_mm[0]+(3.2-f.extent[0])*s,f.origin_mm[1]+(f.extent[3]-1.8)*s,0);
      return {top,filtered,edge,outside:outside?.id??null,hole:hit?.id??null};
    })().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
    .catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
    """
    # Revision switching requires one table identity. Use a separate document
    # for the removed mesh after testing the overlapping two-face source.
    removed_table=KeyedTable(original.table.name,dict(removed.table.columns))
    removed=BrowserFigure(removed_table,recipe.make_views(recipe.make_field('removed')))
    result=browser_result(tmp_path,original,checks,revisions=[RevisionOption('Removed',removed,recipe.CREDIT)])
    assert result==dict(top='b',filtered='a',edge='a',outside=None,hole=None)


@pytest.mark.parametrize('width',[170,210])
def test_paired_plans_keep_identical_physical_scales_at_both_widths(width):
    scene=recipe.make_scene(width=width);a,b=scene.payload()['layers'][:2]
    assert a['clip'][2:]==b['clip'][2:]
    assert a['field']['scale_mm_per_unit']==b['field']['scale_mm_per_unit']
    assert a['marks'][0]['geometry'][0][1][0]-a['marks'][0]['geometry'][0][0][0]==pytest.approx(
        b['marks'][0]['geometry'][0][1][0]-b['marks'][0]['geometry'][0][0][0])



def test_imported_obj_requires_explicit_triangle_correspondence(tmp_path):
    from inklet.three.parse import load
    path=tmp_path/'surface.obj'
    path.write_text('v 0 0 0\nv 2 0 0\nv 0 2 0\nf 1 2 3\n')
    mesh=load(path)
    f=MeshField.from_mesh(mesh,ids=['measured-face'],scalars=[4],vectors=[(0,0,2)])
    assert f.table().columns['area']==(2,)
    assert f.table().columns['magnitude']==(2,)
    assert f.ids==('measured-face',)
    with pytest.raises(ValueError):MeshField.from_mesh(mesh,ids=[],scalars=[4],vectors=[None])


def test_direction_only_revision_changes_scene_even_when_magnitude_is_unchanged():
    f=field();flipped=replace(f,vectors=[(-3,-4,-12),None])
    assert f.table().digest==flipped.table().digest and f.digest!=flipped.digest
    original=BrowserFigure(f.table(),[MeshFieldView('plan',f,vectors=True)])
    revised=original.replace_data(flipped.table(),views=[MeshFieldView('plan',flipped,vectors=True)])
    assert original.payload()['scene_digest']!=revised.figure.payload()['scene_digest']
    assert revised.report()['changed_ids']==[]

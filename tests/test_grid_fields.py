"""Analytic contour/ODE oracles and the linked grid workflow contract."""
from dataclasses import FrozenInstanceError,replace
import importlib.util
import json
import math
from pathlib import Path

import pytest
from inklet.experimental.grid import GridField,Streamline
from inklet.experimental.browser import BrowserFigure,GridFieldView,RevisionOption
from inklet.experimental.selection import KeyedTable,SelectionState

RECIPE=Path(__file__).resolve().parents[1]/'examples/v4/contours_streamlines.py'
spec=importlib.util.spec_from_file_location('contours_streamlines',RECIPE)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


def affine():
    axis=(0.,1.,2.)
    return GridField(axis,axis,('a','b','c','d'),tuple(tuple(x+2*y for x in axis) for y in axis),(((1.,0.),)*3,)*3)


def test_snapshot_corner_means_and_linear_triangle_not_bilinear():
    f=GridField([0,2],[0,2],['a'],[[0,0],[0,4]],[[[1,0],[1,0]],[[1,0],[1,0]]])
    assert f.sample((1,1))==2  # Fixed diagonal: bilinear would give 1.
    assert f.table().columns['scalar']==(1,) and f.table().columns['area']==(4,)
    source=json.loads(json.dumps(f.source()));copied=GridField.from_dict(source);before=copied.digest
    source['scalars'][0][0]=42;source['vectors'][0][0][0]=99
    assert copied.digest==before==f.digest
    with pytest.raises(FrozenInstanceError):copied.unit='m'
    p=[[0,0],[1,0]];line=Streamline('a',p,'length','length');p[0][0]=42
    assert line.points[0]==(0,0)


@pytest.mark.parametrize('change',[{'x':[0,0,2]},{'y':[0,float('inf'),2]},{'ids':['a']},
    {'ids':['a','b','c','c']},{'scalars':[[1]]},{'vectors':[[[1,2,3]]]*3},
    {'scalar_unit':''},{'unit':'pixels'},{'x':[False,1,2]}])
def test_invalid_grid_sources(change):
    with pytest.raises(ValueError):replace(affine(),**change)


def test_affine_contours_exact_on_nonuniform_grid_and_equal_vertices():
    x=(0,.4,2);y=(-1,.3,1)
    f=GridField(x,y,('a','b','c','d'),tuple(tuple(a+2*b for a in x) for b in y),(((1,0),)*3,)*3)
    segments=f.contours((-1,0,1,2))
    assert segments
    for segment in segments:
        for a,b in segment.points:
            assert a+2*b==pytest.approx(segment.level,abs=1e-12)
    segments=affine().contours((2,))
    assert len({tuple(sorted(v.points)) for v in segments})==len(segments)
    plateau=replace(affine(),scalars=((2,)*3,)*3)
    assert plateau.contours((2,))==()  # Flat plateaus do not invent isolines.


def test_radial_contours_have_bounded_interpolation_error():
    f=recipe.make_field()
    for segment in f.contours(recipe.LEVELS):
        for x,y in segment.points:
            assert abs(f.sample((x,y))-segment.level)<1e-12
            assert -1e-12<=segment.level-x*x-y*y<=f.min_spacing**2/2+1e-12


def test_missing_corner_masks_whole_cell_and_fields_independently():
    f=affine();source=json.loads(json.dumps(f.source()));source['scalars'][0][0]=None
    masked=GridField.from_dict(source)
    assert masked.sample((.8,.2)) is None and masked.sample((.8,.2),'vectors')==(1,0)
    assert masked.table().columns['scalar'][0] is None
    assert all(s.cell_id!='a' for s in masked.contours((1,2,3)))
    source['vectors'][1][1]=None;masked=GridField.from_dict(source)
    assert masked.sample((1.5,1.5),'vectors') is None
    line=masked.streamlines([('seed',(.5,.5))],step=.1,max_length=3).lines[0]
    assert line.forward==line.backward=='missing' and len(line.points)==1


def test_uniform_flow_boundary_length_steps_and_stagnation():
    f=affine();line=f.streamlines([('s',(.5,.5))],step=.1,max_length=4).lines[0]
    assert line.forward==line.backward=='boundary'
    assert all(y==pytest.approx(.5) for x,y in line.points)
    assert line.points[0][0]<.0002 and line.points[-1][0]>1.9998
    limited=f.streamlines([('s',(1,.5))],step=.1,max_length=.3).lines[0]
    assert limited.forward==limited.backward=='length'
    assert limited.points[0][0]==pytest.approx(.7) and limited.points[-1][0]==pytest.approx(1.3)
    limited=f.streamlines([('s',(1,.5))],step=.1,max_length=2,max_steps=2).lines[0]
    assert limited.forward==limited.backward=='steps'
    zero=replace(f,vectors=(((0,0),)*3,)*3)
    assert zero.streamlines([('s',(1,1))],step=.1,max_length=2).lines[0].forward=='stagnation'
    assert f.streamlines([('s',(-1,1))],step=.1,max_length=2).lines[0].forward=='boundary'


def test_rotational_flow_closed_once_orientation_and_step_convergence():
    f=recipe.make_field();errors=[]
    for step in (.06,.03):
        line=f.streamlines([('circle',(1.4,0))],step=step,max_length=8).lines[0]
        assert line.closed and line.forward=='loop' and line.backward=='not traced: forward loop'
        assert line.points[0]==line.points[-1] and line.points[1][1]>0
        errors.append(max(abs(math.hypot(x-.5,y)-.9) for x,y in line.points))
    assert errors[1]<errors[0]/8 and errors[0]<1e-6
    reverse=recipe.make_field('reversed').streamlines([('circle',(1.4,0))],step=.03,max_length=8).lines[0]
    assert reverse.closed and reverse.points[1][1]<0


def test_masked_trajectories_never_cross_missing_cells():
    f=recipe.make_field('masked');traces=recipe.make_views(f)[1].streamlines
    assert any('missing' in (line.forward,line.backward) for line in traces.lines)
    for line in traces.lines:
        for a,b in zip(line.points,line.points[1:]):
            for key,p,q in f.split_segment(a,b):
                assert f.sample(tuple((x+y)/2 for x,y in zip(p,q)),'vectors') is not None


@pytest.mark.parametrize('kwargs',[{'step':0},{'step':.3},{'max_length':0},{'max_steps':0},{'max_steps':True},{'min_speed':-1}])
def test_invalid_tracing_options(kwargs):
    options=dict(step=.1,max_length=2);options.update(kwargs)
    with pytest.raises(ValueError):affine().streamlines([('s',(1,1))],**options)


def test_strict_measurement_and_trace_revision_correspondence():
    original=recipe.make_scene();field=recipe.make_field('updated')
    with pytest.raises(ValueError,match='measurement mismatch'):BrowserFigure(original.table,recipe.make_views(field))
    with pytest.raises(ValueError,match='exact field'):GridFieldView('stale',field,streamlines=recipe.make_views(recipe.make_field())[1].streamlines)
    state=original.state(SelectionState.for_table(original.table,selected=['cell-133']))
    revision=original.replace_data(field.table(),views=recipe.make_views(field),state=state,width=170)
    assert revision.state()['selection']['selected_ids']==['cell-133']
    assert revision.figure.payload()['layers'][0]['grid']['source_digest']==field.digest
    a,b=revision.figure.payload()['layers'][:2]
    assert a['grid']['scale_mm_per_unit']==b['grid']['scale_mm_per_unit']


CHECKS=r'''
(async()=>{
 await inklet.ready;let r=inklet;const ok=(c,m)=>{if(!c)throw Error(m);},exports=[];let queries=0;
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);
  for(let panel=0;panel<3;panel++){
   const g=r.scene.layers[panel].grid,s=g.scale_mm_per_unit;
   for(let iy=0;iy<16;iy++)for(let ix=0;ix<16;ix++){
    const x=-2+(ix+.37)/4,y=-2+(iy+.61)/4;
    const hit=r.pick(g.origin_mm[0]+(x-g.extent[0])*s,g.origin_mm[1]+(g.extent[3]-y)*s,0);
    ok(hit?.id==='cell-'+String(iy*16+ix).padStart(3,'0'),'cell picking');queries++;
   }
  }
  r.select(['cell-133']);r.setVisible(['cell-133']);
  ok(r.items.filter(m=>m.kind==='line'&&r.markShown(m)).every(m=>m.ids[0]==='cell-133'),'filtered curves bridge cells');
  exports.push({state:r.state(),svg:r.exportSVG()});
 }
 r.setVisible(null);const old=r;await inkletDocument.switchRevision(1);r=inklet;
 ok(old.disposed,'old scene resources retained');ok(r.scene.layers[1].grid.source_digest!==old.scene.layers[1].grid.source_digest,'stale source');
 r.setViewport([3,2,r.scene.width/1.3,r.scene.height/1.3]);return {queries,exports,revised:{state:r.state(),svg:r.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def test_browser_cell_oracle_and_export_parity(tmp_path):
    from test_browser_series import browser_result
    from inklet.render.preview import svg_png
    from PIL import Image,ImageChops
    original=recipe.make_scene();masked=recipe.make_scene('masked')
    result=browser_result(tmp_path,original,CHECKS,revisions=[RevisionOption('Masked',masked,recipe.CREDIT)])
    assert result['queries']==16*16*3*3
    for n,(scene,export) in enumerate([(original,result['exports'][0]),(masked,result['revised'])]):
        for name,svg in [('python',scene.to_svg(export['state'])),('browser',export['svg'])]:
            path=tmp_path/f'{n}-{name}.svg';path.write_text(svg);svg_png(path,path.with_suffix('.png'),dpi=100)
        a,b=(Image.open(tmp_path/f'{n}-{name}.png').convert('RGB') for name in ('python','browser'))
        assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None


def test_cli_saved_state_json_and_two_widths(tmp_path):
    import subprocess,sys
    scene=recipe.make_scene();state=scene.state(SelectionState.for_table(scene.table,selected=['cell-133']))
    saved=tmp_path/'state.json';saved.write_text(json.dumps(state))
    for directory,args in [('original',['--state',str(saved)]),
            ('masked',['--revision','masked','--rebase-state',str(saved)]),
            ('supplied',['--json',str(tmp_path/'original/input.json')])]:
        result=subprocess.run([sys.executable,str(RECIPE),'--output',str(tmp_path/directory),*args],capture_output=True,text=True,timeout=40)
        assert result.returncode==0,result.stderr
        assert (tmp_path/directory/'figure-170mm.svg').exists()
    assert (tmp_path/'original/figure.svg').read_text()==scene.to_svg(state)
    assert json.loads((tmp_path/'masked/view.json').read_text())['selection']['selected_ids']==['cell-133']



@pytest.mark.parametrize('seeds',[[],[('a',(1,1)),('a',(1,0))],[('',(1,1))],[('a',(float('nan'),0))]])
def test_invalid_seed_identity(seeds):
    with pytest.raises(ValueError):affine().streamlines(seeds,step=.1,max_length=1)


def test_near_loop_does_not_exceed_requested_length():
    f=recipe.make_field();limit=2*math.pi*.9-.01
    line=f.streamlines([('near',(1.4,0))],step=.06,max_length=limit).lines[0]
    assert not line.closed and line.forward==line.backward=='length'
    assert sum(math.dist(a,b) for a,b in zip(line.points,line.points[1:]))<=2*limit+1e-12


@pytest.mark.parametrize('value',[1.7976931348623157e308,1e-320,-1.7976931348623157e308])
def test_constant_interpolants_remain_finite_at_numeric_extremes(value):
    f=replace(affine(),scalars=((value,)*3,)*3)
    for point in ((.37,.71),(.71,.37),(1.999,1.333)):
        assert f.sample(point)==value


def test_source_grid_bounds_and_arrow_pieces_respect_masks():
    f=recipe.make_field('masked');layer=recipe.make_scene('masked').payload()['layers'][1]
    meta=layer['grid'];ox,oy=meta['origin_mm'];scale=meta['scale_mm_per_unit'];left,bottom,right,top=meta['extent']
    for mark in layer['marks']:
        if mark['kind']!='line':continue
        x1,y1,x2,y2=mark['geometry'];mid=(left+((x1+x2)/2-ox)/scale,top-((y1+y2)/2-oy)/scale)
        assert f.sample(mid,'vectors') is not None
        assert f.ids[f.locate(mid)[1]*16+f.locate(mid)[0]]==mark['ids'][0]



def test_explicit_table_names_survive_derived_column_construction():
    field=affine()
    assert field.table().name=='grid-cells'
    first=field.table('supplied-field');second=field.table('another-field')
    assert first.name=='supplied-field' and second.name=='another-field'
    assert first.digest!=second.digest
    view=GridFieldView('contours',field)
    assert BrowserFigure(first,[view]).table.name=='supplied-field'
    field.validate_table(first)

"""Source-pixel measurement oracles and linked scientific workflow acceptance."""
import base64
from dataclasses import FrozenInstanceError,replace
import importlib.util
import io
import json
from pathlib import Path

import pytest
from inklet.experimental.measurement import LabelImage
from inklet.experimental.browser import BrowserFigure,LabelImageView,RevisionOption
from inklet.experimental.selection import KeyedTable,SelectionState

RECIPE=Path(__file__).resolve().parents[1]/'examples/v4/scientific_report.py'
spec=importlib.util.spec_from_file_location('scientific_report',RECIPE)
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)


def fixture():
    return json.loads((RECIPE.parent/'fixtures/measurement.json').read_text())


def test_original_fixture_measurements_and_immutable_source():
    source=fixture();image=LabelImage.from_dict(source);before=image.digest
    source['intensity'][0][0]=999;source['labels'][0][0]=0
    assert image.digest==before and image.shape==(2,4) and image.extent==(2,1)
    data=image.table().columns
    assert data['pixels']==(4,4) and data['area']==(1,1) and data['mean']==(2.5,6.5)
    assert data['minimum']==(1,5) and data['maximum']==(4,8)
    with pytest.raises(FrozenInstanceError):image.unit='mm'


@pytest.mark.parametrize('change', ['ragged','empty','shape','nan','boolean_value','float_label','negative_label',
                                    'unsafe_label','unmapped','absent','duplicate_label','duplicate_id',
                                    'spacing','boolean_spacing','area_underflow','extent_overflow','unit'])
def test_invalid_image_contract(change):
    source=fixture()
    if change=='ragged':source['intensity'][1].pop()
    elif change=='empty':source['intensity']=[]
    elif change=='shape':source['labels'].pop()
    elif change=='nan':source['intensity'][0][0]=float('nan')
    elif change=='boolean_value':source['intensity'][0][0]=True
    elif change=='float_label':source['labels'][0][0]=1.0
    elif change=='negative_label':source['labels'][0][0]=-1
    elif change=='unsafe_label':source['labels'][0][0]=2**53
    elif change=='unmapped':source['labels'][0][0]=3
    elif change=='absent':source['regions'].append(dict(id='third',label=3))
    elif change=='duplicate_label':source['regions'][1]['label']=1
    elif change=='duplicate_id':source['regions'][1]['id']='region-1'
    elif change=='spacing':source['spacing_yx']=[0,1]
    elif change=='boolean_spacing':source['spacing_yx']=[True,1]
    elif change=='area_underflow':source['spacing_yx']=[1e-200,1e-200]
    elif change=='extent_overflow':source['spacing_yx']=[1,1e308]
    elif change=='unit':source['unit']='pixels'
    with pytest.raises(ValueError):LabelImage.from_dict(source)


def test_missing_intensity_preserves_area_and_empty_regions_do_not_invent_statistics():
    image=LabelImage([[None,2,None,None]],[[1,1,2,2]],[('a',1),('b',2)],(.5,.4),'um')
    data=image.table().columns
    assert data['pixels']==(2,2) and data['valid_pixels']==(1,0) and data['missing_pixels']==(1,2)
    assert data['area']==(.4,.4) and data['mean']==(2,None) and data['minimum']==(2,None)
    empty=LabelImage([[1,2]],[[0,0]],[],(1,1),'mm')
    scene=BrowserFigure(empty.table(),[LabelImageView('image',empty,(0,3),1)])
    assert scene.table.row_ids==() and all(m['reference'] for m in scene.payload()['layers'][0]['marks'])


@pytest.mark.parametrize('value',[1e308,-1e308,1e-320,-1e-320,0])
def test_representable_constant_mean_survives_sum_overflow_and_small_values(value):
    image=LabelImage([[value]*8],[[1]*8],[('a',1)],(1,1),'mm')
    assert image.table().columns['mean']==(value,)


def test_calibration_changes_area_and_aspect_but_not_intensity():
    original=recipe.make_image();changed=recipe.make_image('calibrated')
    a,b=original.table(),changed.table()
    assert a.columns['mean']==b.columns['mean'] and a.columns['pixels']==b.columns['pixels']
    assert b.columns['area']==pytest.approx([v*1.5 for v in a.columns['area']])
    for image in (original,changed):
        scene=recipe.make_scene(image=image);layer=scene.payload()['layers'][0]
        box=layer['image']['image_box'];px,py=layer['image']['pixel_size_mm']
        assert box[2]/box[3]==pytest.approx(image.extent[0]/image.extent[1])
        assert py/px==pytest.approx(image.spacing_yx[0]/image.spacing_yx[1])
        assert layer['marks'][0]['preserve_aspect'] is False and layer['marks'][0]['smooth'] is False
    with pytest.raises(ValueError,match='measurement mismatch'):
        BrowserFigure(a,[LabelImageView('image',changed,(0,100),5)])


def test_source_png_is_lossless_and_row_reordering_preserves_measurements():
    Image=pytest.importorskip('PIL.Image')
    source=LabelImage([[0,100,None]],[[1,1,0]],[('a',1)],(1,2),'mm')
    layer=BrowserFigure(source.table(),[LabelImageView('image',source,(0,100),1)]).payload()['layers'][0]
    decoded=Image.open(io.BytesIO(base64.b64decode(layer['marks'][0]['href'].split(',')[1])))
    assert decoded.size==(3,1) and [decoded.getpixel((x,0)) for x in range(3)]==[(0,0,0),(255,255,255),(225,214,225)]
    image=LabelImage.from_dict(fixture());table=image.table()
    reordered=KeyedTable(table.name,{key:tuple(reversed(v)) for key,v in table.columns.items()})
    assert BrowserFigure(reordered,[LabelImageView('image',image,(0,8),.5)]).table.row_ids==('region-2','region-1')


def test_input_replacement_rebuilds_statistics_and_preserves_old_snapshot():
    original=recipe.make_scene();before=original.payload()
    state=original.state(SelectionState.for_table(original.table,selected=['region-3','region-8']))
    updated=recipe.make_image('updated')
    revised=original.replace_data(updated.table(original.table.name),views=recipe.make_views(updated),state=state)
    assert 'region-8' in revised.report()['changed_ids']
    assert revised.figure.table.columns['valid_pixels'][-1]>0
    removed=recipe.make_image('relabeled')
    with pytest.raises(ValueError):original.replace_data(removed.table(original.table.name),views=recipe.make_views(removed),state=state)
    revision=original.replace_data(removed.table(original.table.name),views=recipe.make_views(removed),state=state,missing='drop')
    assert revision.state()['selection']['selected_ids']==['region-3']
    for width in (170,210):
        export=revision.figure.replace_data(revision.figure.table,state=revision.state(),width=width)
        assert export.figure.payload()['width']==width
    assert original.payload()==before


CHECKS=r'''
(async()=>{
 await inkletDocument.ready;let r=inklet;const ok=(c,m)=>{if(!c)throw Error(m);},exports=[];
 const vector=r.items.find(m=>m.kind==='image'&&m.href.startsWith('data:image/svg+xml;base64,'));
 ok(r.drawings.get(vector.href).naturalWidth>=vector.geometry[2]*8-1,'embedded vector label raster resolution');
 const raster=r.items.find(m=>m.kind==='image'&&m.href.startsWith('data:image/png;base64,'));
 ok(r.drawings.get(raster.href).naturalWidth===64,'source pixel grid was resampled');
 const ids=new Map(r.scene.columns.label.map((label,n)=>[label,r.scene.row_ids[n]]));
 let queries=0;
 for(const backend of ['svg','canvas','hybrid']){
  r.setBackend(backend);r.setVisible(null);r.select(['region-3']);
  for(const layer of r.scene.layers.slice(0,2)){
   const b=layer.image.image_box,[px,py]=layer.image.pixel_size_mm;
   for(let y=0;y<40;y++)for(let x=0;x<64;x++){
    const label=sourceLabels[y][x],hit=r.pick(b[0]+(x+.5)*px,b[1]+(y+.5)*py,0);
    ok((hit?.id??null)===(ids.get(label)??null),'pixel membership '+x+','+y);queries++;
   }
   ok(r.pick(b[0]+40.5*px,b[1]+9.5*py,0)===null,'ring hole selected');
   ok(r.pick(b[0]+40.5*px,b[1]+29.5*py,0)===null,'disconnected region gap selected');
  }
  exports.push({state:r.state(),svg:r.exportSVG()});
  r.setVisible(['region-3']);exports.push({state:r.state(),svg:r.exportSVG()});
  ok(r.items.filter(m=>m.kind==='image'&&m.reference).every(m=>r.markShown(m)),'filter hid source image');
 }
 r.setVisible(null);const old=r;await inkletDocument.switchRevision(1);r=inklet;
 ok(old.disposed&&old.drawings.size===0,'image resources retained after revision');
 ok(r.scene.layers[0].image.spacing_yx[0]===.6,'calibration switch');
 ok(!document.getElementById('image-status').hidden&&JSON.parse(document.getElementById('image-report').textContent)[0].spacing_yx[0]===.6,'calibration diagnostics');
 const area=r.scene.columns.area[r.rowIndex.get('region-3')];ok(area>originalArea,'area did not update');
 r.setViewport([4,3,r.scene.width/1.4,r.scene.height/1.4]);
 return {queries,exports,calibrated:{state:r.state(),svg:r.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def test_browser_exact_pixel_membership_and_calibrated_export(tmp_path):
    from test_browser_series import browser_result
    from test_browser_statistics import svg_geometry
    original=recipe.make_scene();calibrated=recipe.make_scene('calibrated')
    prefix='const sourceLabels='+json.dumps(recipe.make_image().labels)+';const originalArea='+str(original.table.columns['area'][2])+';'
    result=browser_result(tmp_path,original,prefix+CHECKS,revisions=[RevisionOption('Calibrated',calibrated,recipe.CREDIT)])
    assert result['queries']==40*64*2*3
    for export in result['exports']:
        assert svg_geometry(original.to_svg(export['state']))==svg_geometry(export['svg'])
    Image=pytest.importorskip('PIL.Image')
    from PIL import ImageChops
    from inklet.render.preview import svg_png
    export=result['calibrated']
    for name,svg in [('python',calibrated.to_svg(export['state'])),('browser',export['svg'])]:
        path=tmp_path/(name+'.svg');path.write_text(svg);svg_png(path,path.with_suffix('.png'),dpi=150)
    a,b=(Image.open(tmp_path/(name+'.png')).convert('RGB') for name in ('python','browser'))
    assert a.size==b.size and ImageChops.difference(a,b).getbbox() is None


def test_image_view_rejects_excessive_pixels_and_outline_work():
    too_wide=LabelImage([[0]*65537],[[0]*65537],[],(1,1),'mm')
    with pytest.raises(ValueError,match='65,536'):LabelImageView('image',too_wide,(0,1),1)
    labels=[[int((x+y)%2==0) for x in range(128)] for y in range(128)]
    fragmented=LabelImage(labels,labels,[('a',1)],(1,1),'mm')
    with pytest.raises(ValueError,match='20,000'):
        BrowserFigure(fragmented.table(),[LabelImageView('image',fragmented,(0,1),10)])


def test_cli_reopen_rebase_replacement_and_provenance(tmp_path):
    import subprocess,sys
    original=recipe.make_scene();state=original.state(SelectionState.for_table(original.table,selected=['region-3','region-8']))
    saved=tmp_path/'view.json';saved.write_text(json.dumps(state))
    result=subprocess.run([sys.executable,str(RECIPE),'--state',str(saved),'--output',str(tmp_path/'reopened')],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert (tmp_path/'reopened/figure.svg').read_text()==original.to_svg(state)
    result=subprocess.run([sys.executable,str(RECIPE),'--revision','relabeled','--rebase-state',str(saved),
        '--missing','drop','--output',str(tmp_path/'removed')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads((tmp_path/'removed/view.json').read_text())['selection']['selected_ids']==['region-3']
    result=subprocess.run([sys.executable,str(RECIPE),'--json',str(tmp_path/'reopened/input.json'),
        '--output',str(tmp_path/'supplied')],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    report=json.loads((tmp_path/'supplied/image.json').read_text())
    assert report['source_digest']==recipe.make_image().digest and 'User-supplied' in report['credit']


@pytest.mark.parametrize('kwargs',[{'window':(1,1)},{'window':(-1e308,1e308)}, {'scale_bar':0},
                                   {'mode':'automatic'},{'palette':['red']},{'scale_bar':1e20}])
def test_invalid_image_view_options(kwargs):
    options=dict(name='image',image=recipe.make_image(),window=(0,100),scale_bar=5);options.update(kwargs)
    with pytest.raises(ValueError):LabelImageView(**options)

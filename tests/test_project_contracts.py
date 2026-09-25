"""Asset integrity and explicit correspondence contracts, independent of rendering."""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from inklet.project import AssetManifest, EntityMap
from inklet.selection import KeyedTable


def manifest(root):
    return AssetManifest.capture(root,[dict(id='data',path='input.json',source='Simulated fixture',license='MIT')])


def test_manifest_is_portable_immutable_and_detects_changed_bytes(tmp_path):
    (tmp_path/'input.json').write_text('{"x":1}')
    original=manifest(tmp_path)
    restored=AssetManifest.from_dict(json.loads(json.dumps(original.to_dict())))
    assert restored==original and restored.verify(tmp_path)['data']==tmp_path/'input.json'
    with pytest.raises(FrozenInstanceError):original.assets[0].path='other.json'
    (tmp_path/'input.json').write_text('{"x":2}')
    with pytest.raises(ValueError,match='asset changed'):restored.verify(tmp_path)
    (tmp_path/'input.json').unlink()
    with pytest.raises(ValueError,match='missing asset'):restored.verify(tmp_path)


@pytest.mark.parametrize('path',['../input.json','/input.json','a/../input.json','a\\input.json','C:input.json','.inklet/project.json','./input.json','.'])
def test_manifest_rejects_unportable_and_reserved_paths(tmp_path,path):
    with pytest.raises(ValueError):
        AssetManifest.capture(tmp_path,[dict(id='a',path=path,source='fixture',license='MIT')])


def test_manifest_rejects_duplicate_names_and_escaping_symlinks(tmp_path):
    (tmp_path/'input.json').write_text('{}');m=manifest(tmp_path)
    with pytest.raises(ValueError,match='duplicate'):AssetManifest(m.assets+m.assets)
    root=tmp_path/'bundle';root.mkdir()
    try:(root/'input.json').symlink_to(tmp_path/'input.json')
    except OSError:pytest.skip('symlinks unavailable')
    with pytest.raises(ValueError,match='outside asset root'):m.verify(root)


def test_entity_selection_maps_multiple_objects_without_guessing_labels():
    sources={'rows':{'row-7':'a','row-9':'b'},'mesh':{'face-1':'a','face-2':'a','face-3':'b'}}
    mapping=EntityMap(['b','a'],sources);sources['rows']['row-7']='b'
    assert mapping.selected('rows',['row-7'])==('a',)
    assert mapping.targets(['a'])=={'mesh':('face-1','face-2'),'rows':('row-7',)}
    assert EntityMap.from_dict(json.loads(json.dumps(mapping.to_dict())))==mapping
    with pytest.raises(TypeError):mapping.sources['rows']['row-7']='b'
    with pytest.raises(ValueError,match='unmapped'):mapping.selected('rows',['a'])
    with pytest.raises(ValueError,match='unknown'):mapping.targets(['missing'])
    with pytest.raises(ValueError):EntityMap(['a','a'])
    with pytest.raises(ValueError):EntityMap(['a'],{'rows':{'x':'b'}})


def test_join_uses_entity_keys_preserves_missing_and_requires_explicit_aggregation():
    identities=EntityMap(['a','b','c'],{'x':{'r2':'b','r1':'a'},'y':{'q1':'a'}})
    x=KeyedTable('x',dict(id=['r2','r1'],value=[20,10]))
    y=KeyedTable('y',dict(id=['q1'],score=[None]))
    joined=identities.joined_table('joined',{'x':x,'y':y})
    assert joined.row_ids==('a','b','c') and joined.columns['x__value']==(10,20,None)
    assert joined.columns['y__score']==(None,None,None)
    reordered=KeyedTable('x',dict(id=['r1','r2'],value=[10,20]))
    assert identities.joined_table('joined',{'x':reordered,'y':y}).digest==joined.digest
    assert identities.selection_for('x',x,['a']).selected_ids==('r1',)
    with pytest.raises(ValueError,match='correspondence mismatch'):
        identities.joined_table('joined',{'x':KeyedTable('x',dict(id=['r1'],value=[10]))})
    with pytest.raises(ValueError,match='aggregate explicitly'):
        EntityMap(['a'],{'x':{'r1':'a','r2':'a'}}).joined_table('joined',{'x':x})


def test_reassignment_is_reported_even_when_the_entity_survives():
    before=EntityMap(['a','b'],{'mesh':{'face':'a','gone':'b'}})
    after=EntityMap(['a','b'],{'mesh':{'face':'b'}})
    assert before.changes(after)=={'removed_entities':[], 'changed_bindings':[
        {'source':'mesh','id':'face','before':'a','after':'b'},
        {'source':'mesh','id':'gone','before':'b','after':None}]}


def test_mapped_mesh_retains_face_geometry_units_legend_and_source_validation():
    from inklet.experimental.fields import MeshField
    from inklet.experimental.browser import BrowserFigure, MeshFieldView
    field=MeshField(((0,0,0),(1,0,0),(0,1,0)),((0,1,2),),('face-7',),(2.,),((0.,0.,0.),),scalar_unit='Pa')
    source=field.table();mapping=EntityMap(['part-a'],{'mesh':{'face-7':'part-a'}})
    joined=mapping.joined_table('assembly',{'mesh':source})
    view=MeshFieldView('stress',field,breaks=(1,3))
    scene=BrowserFigure(joined,[mapping.view('mesh',source,view)])
    layer=scene.payload()['layers'][0]
    face=next(m for m in layer['marks'] if m['kind']=='polygon')
    assert face['ids']==['part-a'] and face['source_ids']==['face-7']
    assert layer['field']['unit']=='mm' and layer['field']['scalar_unit']=='Pa'
    assert mapping.view('mesh',source,view).legend()==(view.legend(),'Scalar / Pa')
    bad=KeyedTable('assembly',{**dict(joined.columns),'mesh__scalar':[99]})
    with pytest.raises(ValueError,match='source data mismatch'):
        BrowserFigure(bad,[mapping.view('mesh',source,view)])

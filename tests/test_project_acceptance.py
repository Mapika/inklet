"""Complete project acceptance: inputs, identities, editing, reopen and revision."""
import importlib.util
import json
from pathlib import Path
import pytest
import inklet as i
from inklet.project import FigureProject
from inklet.project import ExportDriftWarning

spec=importlib.util.spec_from_file_location('project_recipe',Path(__file__).resolve().parents[1]/'examples/project_workflow.py')
recipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(recipe)
pytestmark=pytest.mark.acceptance


@pytest.mark.parametrize('width',[140,190])
def test_project_edit_bundle_reopen_replace_resize_and_exports(tmp_path,width):
    root=recipe.write_inputs(tmp_path/'inputs')
    project=recipe.project(root);original=project.editor.figure;svg=original.to_svg()
    project.editor.command('edit',{'path':'/diagram/a','placement':{'x':8},
                                   'labels':{'label':{'kind':'module-label','text':'Reviewed A'}}})
    project.editor.command('edit',{'path':'/mesh/a','cameras':{'view':{'kind':'native-orbit','azimuth':20}}})
    edited=project.editor.figure.to_svg();project.editor.command('undo');project.editor.command('redo')
    assert project.editor.figure.to_svg()==edited and original.to_svg()==svg
    targets=project.select('image',['region-a'])
    assert targets['composition']==('/diagram/a','/mesh/a') and targets['measurements']==('sample-a',)
    bundle=project.save(tmp_path/'bundle',asset_root=root)
    assert (bundle/'.inklet/figure.pdf').read_bytes().startswith(b'%PDF')
    reopened=FigureProject.open(bundle,recipe.recipe)
    assert reopened.editor.figure.to_svg()==edited and reopened.selected==('a',)
    linked=recipe.linked(bundle,width=width);state=reopened.state_for(linked)
    assert linked.validate_state(state)[0].selected_ids==('a',)
    restored=json.loads(json.dumps(state))
    assert linked.to_svg(restored)==linked.to_svg(state)
    # All pickable content uses canonical IDs, while provenance keeps local IDs.
    mapped=[l for l in linked.payload()['layers'] if 'correspondence' in l]
    assert len(mapped)==2 and {k for l in mapped for m in l['marks'] for k in m['ids']}=={'a','b'}
    newer_root=recipe.write_inputs(tmp_path/'revised',revised=True)
    newer,report=reopened.revise(recipe.recipe(newer_root),assets=recipe.manifest(newer_root),identities=recipe.inputs(newer_root)[2])
    assert report['removed_selection']==[] and newer.selected==('a',)
    assert newer.editor.figure.to_svg()!=edited and reopened.editor.figure.to_svg()==edited
    newer.editor.command('edit',{'path':'/','page':{'width':width}})
    assert newer.editor.figure.root.bbox.width==pytest.approx(width)
    saved=newer.save(tmp_path/'revised-bundle',asset_root=newer_root)
    assert FigureProject.open(saved,recipe.recipe).editor.figure.to_svg()==newer.editor.figure.to_svg()
    with pytest.raises(FileExistsError):newer.save(saved,asset_root=newer_root)


def test_removal_reports_identity_and_label_conflicts_without_mutating_old_project(tmp_path):
    root=recipe.write_inputs(tmp_path/'inputs');original=recipe.project(root)
    original.select('objects',['object-b']);before=original.editor.figure.to_svg()
    original.editor.command('edit',{'path':'/diagram/b','placement':{'x':36}})
    root2=recipe.write_inputs(tmp_path/'removed',remove=True)
    kwargs=dict(assets=recipe.manifest(root2),identities=recipe.inputs(root2)[2])
    with pytest.raises(ValueError,match='reconciliation'):original.revise(recipe.recipe(root2),**kwargs)
    revised,report=original.revise(recipe.recipe(root2),missing='drop',**kwargs)
    assert report['removed_entities']==report['removed_selection']==['b']
    assert '/diagram/b' in report['layout']['orphaned_targets']
    assert original.selected==('b',) and revised.selected==()
    assert all(e=='a' for bindings in revised.identities.sources.values() for e in bindings.values())


def test_corrupt_asset_is_rejected_before_factory_and_no_failed_bundle_is_left(tmp_path):
    root=recipe.write_inputs(tmp_path/'inputs');project=recipe.project(root)
    bundle=project.save(tmp_path/'bundle',asset_root=root)
    (bundle/'measurements.json').write_text('[]')
    called=[]
    with pytest.raises(ValueError,match='asset changed'):
        FigureProject.open(bundle,lambda p:called.append(p))
    assert called==[]
    (root/'measurements.json').write_text('[]')
    with pytest.raises(ValueError,match='asset changed'):project.save(tmp_path/'failed',asset_root=root)
    assert not (tmp_path/'failed').exists()


def test_wrong_recipe_is_detected_after_reconstruction(tmp_path):
    root=recipe.write_inputs(tmp_path/'inputs');project=recipe.project(root)
    bundle=project.save(tmp_path/'bundle',asset_root=root)
    def wrong(root):
        result=recipe.recipe(root);result.configure(width=190);return result
    with pytest.raises(ValueError,match='reconstructed figure differs'):
        FigureProject.open(bundle,wrong,verify_export='strict')


def test_export_drift_reopens_with_a_warning_and_a_recorded_report(tmp_path):
    root=recipe.write_inputs(tmp_path/'inputs');project=recipe.project(root)
    project.editor.command('edit',{'path':'/diagram/a','placement':{'x':8}})
    bundle=project.save(tmp_path/'bundle',asset_root=root)
    def wrong(root):
        result=recipe.recipe(root);result.configure(width=190);return result
    with pytest.warns(ExportDriftWarning,match='reconstructed figure differs'):
        reopened=FigureProject.open(bundle,wrong)
    report=reopened.open_report
    assert report['verify_export'] is True and report['export_drift'] is True
    assert report['saved_svg_sha256']!=report['svg_sha256']
    assert reopened.editor.overrides()==project.editor.overrides()
    assert issubclass(ExportDriftWarning,UserWarning)


def test_matching_and_unchecked_exports_are_recorded_without_warnings(tmp_path):
    import warnings
    root=recipe.write_inputs(tmp_path/'inputs');project=recipe.project(root)
    assert project.open_report is None
    bundle=project.save(tmp_path/'bundle',asset_root=root)
    with warnings.catch_warnings():
        warnings.simplefilter('error',ExportDriftWarning)
        for mode in (True,'strict'):
            report=FigureProject.open(bundle,recipe.recipe,verify_export=mode).open_report
            assert report['export_drift'] is False and report['svg_sha256']==report['saved_svg_sha256']
        report=FigureProject.open(bundle,recipe.recipe,verify_export=False).open_report
    assert report['export_drift'] is None and report['svg_sha256'] is None
    with pytest.raises(ValueError,match='verify_export'):
        FigureProject.open(bundle,recipe.recipe,verify_export='warn')


def test_joined_browser_picking_keyboard_selection_and_export(tmp_path):
    from browser_support import browser_result, assert_svg_pixels
    root=recipe.write_inputs(tmp_path/'inputs');project=recipe.project(root);scene=recipe.linked(root)
    checks=r'''
    (async()=>{
      await inklet.ready; const r=inklet;
      const mark=r.items.find(m=>m.source_ids&&m.source_ids.includes('region-a')&&m.kind==='rect');
      if(!mark) throw Error('missing mapped image target');
      const g=mark.geometry,hit=r.pick(g[0]+g[2]/2,g[1]+g[3]/2,0);
      if(hit.id!=='a') throw Error('image did not select shared entity');
      r.select(['a']);
      const saved=r.state();r.select([]);r.loadState(saved);
      if(!r.selected.has('a')) throw Error('selection was not restored');
      const buttons=[...document.querySelectorAll('button[aria-label="Select b"]')];
      if(!buttons.length) throw Error('missing accessible data-table selection');
      buttons[0].focus();buttons[0].click();
      if(!r.selected.has('b')) throw Error('data-table selection did not link');
      return {state:r.state(),svg:r.exportSVG()};
    })().then(value=>{const p=document.createElement('pre');p.id='test-result';p.textContent=JSON.stringify(value);document.body.append(p);})
    .catch(error=>{const p=document.createElement('pre');p.id='test-result';p.textContent=JSON.stringify({error:error.message});document.body.append(p);});
    '''
    result=browser_result(tmp_path,scene,checks)
    assert_svg_pixels(tmp_path,scene.to_svg(result['state']),result['svg'])
    targets=project.select_state(scene,result['state'])
    assert project.selected==('a','b') and targets['objects']==('object-a','object-b')

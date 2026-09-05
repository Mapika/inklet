import json
from pathlib import Path
import pytest
import inklet as i


@pytest.fixture
def renderers(monkeypatch):
    Image=pytest.importorskip('PIL.Image')
    import inklet.render.bundle as bundle
    state={'color':'white'}
    def render(source,target,**options): Image.new('RGB',(50,30),state['color']).save(target)
    monkeypatch.setattr(bundle,'svg_png',render)
    monkeypatch.setattr(bundle,'pdf_png',render)
    return state


def figure(width=50):
    doc=i.document(width=width,height=30)
    doc.add('small',i.component(i.text,'Small',size=1))
    return doc.compile()


def test_revision_diff_filters_and_in_place_previous_snapshot(tmp_path,renderers):
    first=figure().export(tmp_path,name='review')
    old_png=first['png'].read_bytes()
    renderers['color']='black'
    current=figure().export(tmp_path,name='review',compare_to=first['manifest'])
    manifest=json.loads(current['manifest'].read_text())
    assert manifest['revision']['changed_fraction']==1
    assert current['previous_png'].read_bytes()==old_png
    assert current['revision_diff'].exists()
    snapshot=json.loads(current['previous_manifest'].read_text())
    assert snapshot['files']['png']==current['previous_png'].name
    page=current['review'].read_text()
    assert 'revision-opacity' in page and 'panel-filter' in page and 'severity-filter' in page
    assert 'data-severity="error"' in page and 'Small' in page
    assert 'value="small"' in page


def test_dimension_and_dpi_changes_do_not_produce_misleading_pixel_scores(tmp_path,renderers):
    prior=figure().export(tmp_path/'before',name='figure')
    after=figure(60).export(tmp_path/'after',compare_to=tmp_path/'before')
    revision=json.loads(after['manifest'].read_text())['revision']
    assert not revision['pixel_comparable'] and 'changed_fraction' not in revision
    assert 'revision_diff' not in after
    after=figure().export(tmp_path/'resolution',dpi=300,compare_to=prior['manifest'])
    assert not json.loads(after['manifest'].read_text())['revision']['pixel_comparable']


def test_invalid_prior_revision_preserves_completed_bundle(tmp_path,renderers):
    paths=figure().export(tmp_path/'out')
    before={key:path.read_bytes() for key,path in paths.items()}
    invalid=tmp_path/'invalid.json';invalid.write_text('{"files":{"png":"../secret.png"}}')
    with pytest.raises(ValueError,match='local filename'):
        figure().export(tmp_path/'out',compare_to=invalid)
    assert before=={key:path.read_bytes() for key,path in paths.items()}
    with pytest.raises(FileNotFoundError):figure().export(tmp_path/'out',compare_to=tmp_path/'missing.json')
    assert before=={key:path.read_bytes() for key,path in paths.items()}


def test_review_escapes_names_components_and_messages():
    from inklet.render.review import review_page
    metadata=dict(name='<script>bad</script>',width_mm=10,height_mm=10,dpi=150,text='embed',
                  files={key:'safe.'+key for key in ('svg','pdf','png','manifest')})
    diagnostics=[dict(components=['a / <img src=x onerror=bad>'],severity='error',
                      code='TEST',message='<script>bad</script>',where=None)]
    page=review_page(metadata,diagnostics,'<script>bad</script>','<svg viewBox="0 0 10 10"></svg>')
    assert '<script>bad</script>' not in page and '<img src=x onerror=bad>' not in page
    assert '&lt;script&gt;bad&lt;/script&gt;' in page


def test_cli_profile_and_comparison_options(tmp_path,renderers,capsys):
    from inklet.cli import main
    script=tmp_path/'author.py'
    script.write_text("import inklet as i\ndef make_document():\n d=i.publication(dpi=240).document(height=30)\n d.add('label',i.component(i.text,'Ready'))\n return d\n")
    out=tmp_path/'out'
    assert main(['build',str(script),'--output',str(out)])==0
    assert json.loads((out/'figure-manifest.json').read_text())['dpi']==240
    assert main(['build',str(script),'--output',str(out),'--compare-to',str(out)])==0
    assert (out/'figure-previous.png').exists()
    assert main(['build',str(script),'--vectors-only','--compare-to',str(out)])==1
    assert '--compare-to requires' in capsys.readouterr().err

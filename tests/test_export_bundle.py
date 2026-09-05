import json
import shutil
import pytest
import inklet
from inklet.core import DiagramError


def figure():
    f=inklet.figure(width=50)
    f.add(inklet.box('Review',width=25,height=10))
    return f


def test_export_failure_preserves_existing_bundle(tmp_path,monkeypatch):
    import inklet.render.bundle as bundle
    target=tmp_path/'out';target.mkdir()
    previous=target/'figure.svg';previous.write_text('original')
    def fail(*args,**kwargs):raise DiagramError('renderer unavailable')
    monkeypatch.setattr(bundle,'svg_png',fail)
    with pytest.raises(DiagramError,match='renderer unavailable'):figure().export(target)
    assert previous.read_text()=='original'
    assert list(target.iterdir())==[previous]
    assert sorted(p.name for p in tmp_path.iterdir())==['out']


@pytest.mark.parametrize('kwargs',[{'dpi':0},{'dpi':float('nan')},{'name':'../figure'},{'text':'names'}])
def test_export_rejects_invalid_options_before_creating_files(tmp_path,kwargs):
    target=tmp_path/'out'
    with pytest.raises(ValueError):figure().export(target,**kwargs)
    assert not target.exists()


def test_export_bundle_renders_matching_physical_pages(tmp_path):
    Image=pytest.importorskip('PIL.Image')
    if not shutil.which('pdftoppm') or not any(shutil.which(n) for n in ('google-chrome','chromium','chromium-browser')):
        pytest.skip('Chromium and Poppler required')
    result=figure().export(tmp_path,name='review',dpi=100)
    assert all(p.exists() for p in result.values())
    metadata=json.loads(result['manifest'].read_text())
    with Image.open(result['png']) as a,Image.open(result['pdf_png']) as b:
        assert abs(a.width-b.width)<=1 and abs(a.height-b.height)<=1
        assert a.width==round(metadata['width_mm']*100/25.4)
    page=result['review'].read_text()
    assert 'review.svg' in page and 'review-pdf.png' in page
    assert '<h2>Diagnostics</h2>' in page

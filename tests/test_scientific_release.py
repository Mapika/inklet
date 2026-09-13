import json
import pytest
import inklet as i
from inklet.core import PathPrim,Rect


def test_batched_matrix_is_vector_and_keeps_exact_colors_and_bounds():
    values=[[0,1,None],[.3,.3,.8]];ramp=i.ramp(['white','#087f8c'])
    cells=i.panel(60,40).matrix(values,ramp=ramp,scale=i.linear((0,1)),raster=False,overlap=0,missing='#ddd').build()
    batch=i.panel(60,40).matrix(values,ramp=ramp,scale=i.linear((0,1)),vector='batched',missing='#ddd').build()
    assert cells.bbox==batch.bbox
    colors=lambda node:{p.style.fill for p in i.resolve(node).values() if p.diagram.kind=='mark'}
    assert colors(cells)==colors(batch)
    assert '<image' not in i.to_svg(batch,text='embed')
    assert sum(len(n.prim.subpaths) for n in batch.walk() if isinstance(n.prim,PathPrim))==6
    with pytest.raises(ValueError,match='boundaries'):i.panel(10,10).matrix([[1]],ramp=ramp,vector='batched',overlap=.1)
    with pytest.raises(ValueError,match='raster'):i.panel(10,10).matrix([[1]],ramp=ramp,vector='batched',raster=True)


def test_dense_matrix_reduces_vector_node_and_file_size():
    values=[[float((r+c)%2) for c in range(50)] for r in range(50)];ramp=i.ramp(['white','black'])
    cell=i.panel(50,50).matrix(values,ramp=ramp,raster=False,overlap=0).build()
    batch=i.panel(50,50).matrix(values,ramp=ramp,vector='batched').build()
    assert len(list(batch.walk()))<len(list(cell.walk()))/20
    assert len(i.to_svg(batch))<len(i.to_svg(cell))*.5


def test_graph_readability_floors_are_opt_in_and_recorded():
    g=i.graph({'a':i.tag('a'),'b':i.tag('b')},[('a','b',{'stroke_width':.01,'arrow_size':.1})])
    assert g.build().notes['graph_readability']['clamped_edges']==0
    out=g.build(min_arrow_size=1.2,min_stroke_width=.15)
    assert out.notes['graph_readability']['clamped_edges']==1
    assert g.edges[0].options['stroke_width']==.01
    with pytest.raises(ValueError):g.build(min_arrow_size=-1)


def test_review_exports_all_findings_without_changing_art(tmp_path):
    art=i.text('small',size=1).translated(20,20)
    review=i.review_figure(art,page=Rect(0,0,10,10),rules=['TINY_TEXT','OFF_CANVAS'],max_highlights=1)
    assert len(review.findings)>=2 and review.highlighted==1
    svg,report=review.save(tmp_path/'review')
    assert svg.exists() and json.loads(report.read_text())['count']==len(review.findings)
    assert 'figure_review' not in art.notes

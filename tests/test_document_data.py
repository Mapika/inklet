import pytest
import inklet as i
from inklet.core import DiagramError


def test_derived_data_tracks_nested_inputs_and_snapshots_literals():
    data=i.dataset({'x':[1,2],'y':[3,4]},name='measurements')
    offset=[10]
    summed=i.derive(lambda columns,bias:[x+y+bias[0] for x,y in zip(*columns)],
                    (data.column('x'),data.column('y')),offset)
    offset[0]=100
    assert summed.evaluate()==(14,16)
    old=summed.dependency_key
    data.update(y=[6,8])
    assert summed.dependency_key!=old and summed.evaluate()==(17,20)
    p=i.plot_spec(x=(0,3),y=(0,25)).line(i.derive(lambda xs,ys:tuple(zip(xs,ys)),data.column('x'),summed))
    doc=i.document(width=80);doc.add('derived',p)
    first=doc.compile()
    assert first.metadata['datasets'][0]['name']=='measurements'
    data.update(y=[7,9])
    assert doc.compile() is not first
    with pytest.raises(TypeError,match='callable'):i.derive(3,data.column('x'))


def test_shared_scale_updates_and_rejects_units():
    a=i.dataset({'x':[1,2],'y':[3,4]},units={'x':'s','y':'mV'})
    b=i.dataset({'y':[5,8]},units={'y':'mV'})
    scale=i.shared_scale(a.column('y'),b.column('y'),padding=0)
    assert scale.evaluate().domain==(3,8)
    b.update(y=[10,12]);assert scale.evaluate().domain==(3,12)
    with pytest.raises(DiagramError,match='units'):i.shared_scale(a.column('x'),b.column('y'))
    with pytest.raises(DiagramError):a.update(y=[1])
    assert a.columns['y']==(3,4) and a.revision==0


def test_series_bounds_legend_and_provenance(tmp_path):
    path=tmp_path/'source.csv';path.write_text('x,y\n0,1\n1,2\n')
    data=i.dataset({'x':[0,1],'y':[1,2],'lo':[.5,1.5],'hi':[1.5,2.5]},
                   source=i.Source('Example measurements',path=str(path)))
    series=i.Series('Measured',data.column('x'),data.column('y'),'#246',data.column('lo'),data.column('hi'))
    p=i.plot_spec(x=(0,1),y=(0,3)).legend().series(series).axes()
    d=i.document(width=100);d.add('plot',p)
    compiled=d.compile()
    assert 'Measured' in compiled.to_svg()
    source=compiled.metadata['datasets'][0]['source']
    assert source['method']=='measured' and len(source['sha256'])==64
    data.update(lo=[3,3])
    with pytest.raises(DiagramError,match='lower <= upper'):d.compile()


def test_log_shared_scale_validation():
    data=i.dataset({'x':[1,100]})
    scale=i.shared_scale(data.column('x'),kind='log',padding=0)
    assert scale.evaluate().domain==(1.,pytest.approx(100.))
    data.update(x=[0,1])
    with pytest.raises(DiagramError,match='positive'):scale.evaluate()


def test_missing_matrix_values_keep_valid_provenance():
    data=i.dataset({'row':[[1,float('nan')],[.2,.4]]})
    p=i.plot_spec().matrix(data.column('row'),ramp=i.ramp(['white','#246']),missing='#ddd')
    d=i.document(width=80);d.add('matrix',p)
    compiled=d.compile()
    assert len(compiled.metadata['datasets'][0]['data_sha256'])==64
    assert compiled.to_pdf().startswith(b'%PDF')

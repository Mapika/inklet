"""Local table typing, provenance, errors and live plot integration."""
import hashlib
from pathlib import Path
import pytest
import inklet as i


def test_typed_csv_preserves_identifiers_strings_and_source_bytes(tmp_path):
    path=tmp_path/'table.csv'
    raw='\ufeffid,group,value\r\n9007199254740993,"east, north",2.5\r\n2,"line\nname",3e2\r\n'.encode()
    path.write_bytes(raw)
    data=i.read_csv(path,types={'id':int,'value':float},units={'value':'ms'},name='timings',method='simulated')
    assert data.columns['id']==(9007199254740993,2)
    assert data.columns['group']==('east, north','line\nname')
    assert data.columns['value']==(2.5,300)
    assert data.source.sha256==hashlib.sha256(raw).hexdigest()
    assert data.source.path==str(path.resolve()) and data.source.method=='simulated'
    path.write_text('edited')
    assert data.columns['value']==(2.5,300)


@pytest.mark.parametrize('text,types,match',[
    ('a,a\n1,2',{},'unique'),('a,\n1,2',{},'headers'),('',{},'headers'),
    ('a,b\n1',{},'expected 2 fields'),('a\n1,2',{},'expected 1 fields'),
    ('a\n1\n\n',{},'expected 1 fields'),('a\n1',{'missing':int},'unknown columns'),
    ('a\n1.5',{'a':int},"line 2, column 'a'"),('a,b\n,1',{'a':float},'finite float'),
    ('a\nnan',{'a':float},'finite float'),('a\ninf',{'a':float},'finite float'),
    ('a\n"unterminated',{},'CSV line'),
])
def test_csv_refuses_ambiguous_headers_and_bad_rows(tmp_path,text,types,match):
    path=tmp_path/'bad.csv';path.write_text(text)
    with pytest.raises(i.DiagramError,match=match):i.read_csv(path,types=types)


def test_csv_types_are_explicit_and_string_columns_keep_empty_values(tmp_path):
    path=tmp_path/'data.tsv';path.write_text('id\tname\n001\t\n')
    data=i.read_csv(path,types={},delimiter='\t')
    assert data.columns['id']==('001',) and data.columns['name']==('',)
    for types in (None,[],{'id':bool},{'id':lambda x:x}):
        with pytest.raises(ValueError,match='types'):i.read_csv(path,types=types)


def test_csv_dataset_updates_recompile_plots_without_optional_dependencies(tmp_path):
    path=tmp_path/'data.csv';path.write_text('x,y\n0,1\n1,2\n2,3\n')
    data=i.read_csv(path,types={'x':float,'y':float},citation='Illustrative measurements',method='simulated')
    p=i.plot_spec(x=(0,2),y=i.shared_scale(data.column('y')))
    p.line(data.points('x','y'),name='Signal').axes().legend()
    doc=i.document(width=100);doc.add('signal',p)
    before=doc.compile();data.update(y=[2,3,7]);after=doc.compile()
    assert before.to_svg()!=after.to_svg()
    assert after.metadata['datasets'][0]['revision']==1

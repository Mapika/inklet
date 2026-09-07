"""Analytic values, coverage and identity contracts for intensity tables."""
import csv
import io
from pathlib import Path
import re
import pytest
np=pytest.importorskip('numpy')
from inklet.experimental.volume import Volume
from inklet.experimental.sections import Plane,SampledSection
from inklet.experimental.regions import BoxRegion
from inklet.experimental.measurements import measure_labels


def volume(data,spacing=(2,3,4),origin=(0,0,0)):
    return Volume(np.asarray(data),spacing,'um',origin,source_id='analytic')


def section(data,kind='intensity',valid=None):
    data=np.asarray(data)
    plane=Plane((0,0,0),(1,0,0),(0,1,0),data.shape,(3,4),'um')
    return SampledSection(plane,volume(data[None]),kind,data,
                          np.ones(data.shape,dtype=bool) if valid is None else np.asarray(valid,dtype=bool))


def test_native_statistics_exact_ids_and_serialization():
    large=2**63+17
    labels=volume(np.array([[[large,large,0,7]]],dtype='uint64'))
    table=measure_labels(labels,{'signal':volume([[[2.,6.,99.,-3.]]])},label_ids=[large,7,0,19])
    a,b,background,absent=table.rows
    assert a['label']==large and a['label_id']==str(large)
    assert (a['count'],a['mean'],a['std'],a['minimum'],a['maximum'],a['sum'],a['measure'],a['integral'])==(2,4,2,2,6,8,48,192)
    assert b['sum']==-3 and b['std']==0 and background['mean']==99
    assert absent['count']==0 and absent['mean'] is None and absent['coverage_fraction'] is None
    assert absent['sum']==absent['integral']==absent['measure']==0
    rows=list(csv.DictReader(io.StringIO(table.to_csv())))
    assert rows[0]['label_id']==str(large) and rows[3]['mean']==''
    altered=table.report();altered['rows'][0]['mean']=0
    assert table.rows[0]['mean']==4
    assert [r['label'] for r in measure_labels(labels,{'s':volume([[[1,2,3,4]]])}).rows]==[7,large]


def test_section_coverage_excludes_missing_values_and_keeps_denominators():
    labels=section([[1,1,1,0]],'labels',[[1,1,1,0]])
    a=section([[2,6,100,99]],valid=[[1,1,0,1]])
    b=section([[10,20,30,99]],valid=[[1,0,1,1]])
    strict=measure_labels(labels,{'a':a,'b':b})
    assert [(r['count'],r['mean'],r['measure']) for r in strict.rows]==[(1,2,12),(1,10,12)]
    own=measure_labels(labels,{'a':a,'b':b},coverage='per-channel')
    assert [(r['count'],r['mean'],r['std']) for r in own.rows]==[(2,4,2),(2,20,10)]
    assert all(r['selected_count']==3 and r['excluded_count']==1 and r['coverage_fraction']==2/3 for r in own.rows)
    empty=measure_labels(labels,{'a':section([[0,0,0,0]],valid=[[0,0,0,0]])}).rows[0]
    assert empty['mean'] is None and empty['count']==0 and empty['coverage_fraction']==0
    no_labels=measure_labels(section([[0]],'labels',[[0]]),{'a':section([[3]])},label_ids=[0,1])
    assert all(r['selected_count']==0 for r in no_labels.rows)


def test_regions_select_centres_half_open_in_native_and_section_grids():
    labels=volume([[[1,1,1,1]]],origin=(10,20,30))
    values=volume([[[2,4,8,16]]],origin=(10,20,30))
    region=BoxRegion('roi',(14,19,29),(22,21,31),'um')
    row=measure_labels(labels,{'s':values},region=region).rows[0]
    assert row['count']==2 and row['sum']==12 and row['measure']==48
    labels=section([[1,1,1,1]],'labels')
    region=BoxRegion('roi',(-2,-1,-1),(6,1,1),'um')
    row=measure_labels(labels,{'s':section([[2,4,8,16]])},region=region).rows[0]
    assert row['count']==2 and row['sum']==12 and row['measure']==24
    away=BoxRegion('away',(100,100,100),(101,101,101),'um')
    assert measure_labels(labels,{'s':section([[2,4,8,16]])},region=away).rows==()


@pytest.mark.parametrize('ids',[[True],[-1],[1,1],[1.0]])
def test_invalid_requested_labels(ids):
    with pytest.raises(ValueError):measure_labels(volume([[[1]]]),{'s':volume([[[1]]])},label_ids=ids)


def test_measurements_reject_incompatible_grids_and_display_objects():
    labels=volume([[[1,1]]])
    for channels in ({},{'':labels},{'s':volume([[[1,1]]],origin=(1,0,0))},{'s':section([[1,1]])}):
        with pytest.raises(ValueError):measure_labels(labels,channels)
    with pytest.raises(ValueError):measure_labels(volume([[[1.5]]]),{'s':volume([[[1]]])})
    with pytest.raises(ValueError):measure_labels(volume([[[-1]]]),{'s':volume([[[1]]])})
    with pytest.raises(ValueError):measure_labels(labels,{'s':labels},coverage='union')
    with pytest.raises(ValueError):measure_labels(section([[1,1]],'labels'),{'s':section([[1,1]],'labels')})
    with pytest.raises(ValueError):measure_labels(labels,{'s':labels},region=BoxRegion('r',(0,0,0),(1,1,1),'nm'))


def test_large_offsets_retain_small_population_spread():
    row=measure_labels(volume([[[1,1,1]]]),{'s':volume([[[1e12-1,1e12,1e12+1]]])}).rows[0]
    assert row['std']==pytest.approx((2/3)**.5)
    with pytest.raises(ValueError,match='finite'):
        measure_labels(volume([[[1,1]]]),{'s':volume([[[1e308,1e308]]])})


def test_documented_measurement_workflow():
    path=Path(__file__).resolve().parents[1]/'docs/label-measurements.md'
    namespace={}
    for source in re.findall(r'```python\n(.*?)```',path.read_text(),re.S):
        exec(compile(source,str(path),'exec'),namespace)
    assert namespace['table'].rows[0]['mean']==4

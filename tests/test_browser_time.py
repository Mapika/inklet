"""Explicit calendar axes preserve source identity and elapsed-time geometry."""
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone, timedelta
import html
import json
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

import pytest

from inklet.experimental.browser import (
    BarView, BrowserFigure, FacetView, LineView, RevisionOption, ScatterView, TimeAxis,
)
from inklet.experimental.selection import KeyedTable, SelectionState


def data(times, values=None, **columns):
    return KeyedTable('time', dict(id=list('abcdefghijkl')[:len(times)], when=times,
                                  value=values if values is not None else list(range(len(times))),
                                  **columns))


def dates(reverse=False):
    domain=('2024-02-28', '2024-03-02')
    return TimeAxis(domain[::-1] if reverse else domain)


def line(table, domain=None, **kwargs):
    return BrowserFigure(table, [LineView('trend', 'when', 'value', domain or dates(), (-2, 12), **kwargs)])


def segments(figure):
    return [mark['ids'] for mark in figure.payload()['layers'][0]['marks']]


def test_date_domain_snapshot_leap_day_and_pre_epoch():
    endpoints=[date(1969, 12, 31), '1970-01-02']
    axis=TimeAxis(endpoints); endpoints[0]='2000-01-01'
    assert axis.mode=='date'
    assert axis.domain==('1969-12-31', '1970-01-02')
    assert axis.seconds==(-86400,86400)
    assert dates().seconds[1]-dates().seconds[0]==3*86400
    assert dates(True).seconds==dates().seconds[::-1]
    with pytest.raises(FrozenInstanceError): axis.mode='utc'


@pytest.mark.parametrize('limit,retained', [(1.001,True),(1.0009,False),(1.002,True)])
def test_decimal_second_gap_limits_do_not_round_below_exact_millisecond(limit,retained):
    table=data(['2024-01-01T00:00:00Z','2024-01-01T00:00:01.001Z'])
    axis=TimeAxis(('2024-01-01T00:00:00Z','2024-01-01T00:00:02Z'),mode='utc')
    assert bool(segments(line(table,axis,max_gap_seconds=limit))) is retained


def test_utc_domain_offset_normalization_exact_milliseconds():
    axis=TimeAxis(('1969-12-31T23:59:59.999000Z',
                   datetime(1970,1,1,2,0,0,1000,tzinfo=timezone(timedelta(hours=2)))), mode='utc')
    assert axis.seconds==pytest.approx((-.001,.001),abs=1e-12)
    assert all(isinstance(value,str) and value.endswith('Z') for value in axis.domain)
    parsed=tuple(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp() for value in axis.domain)
    assert parsed==pytest.approx(axis.seconds,abs=1e-12)
    assert TimeAxis(axis.domain, mode='utc')==axis


@pytest.mark.parametrize('domain,mode', [
    (('2024-02-30','2024-03-01'),'date'),
    (('2024-2-01','2024-03-01'),'date'),
    (('20240201','2024-03-01'),'date'),
    (('2024-02-01T00:00:00Z','2024-03-01'),'date'),
    ((datetime(2024,2,1),date(2024,3,1)),'date'),
    ((0,86400),'date'), ((True,False),'date'),
    (('2024-02-01','2024-02-01'),'date'),
    (('2024-02-01T00:00:00','2024-03-01T00:00:00Z'),'utc'),
    ((datetime(2024,2,1),datetime(2024,3,1,tzinfo=timezone.utc)),'utc'),
    (('2024-02-01','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01T00:00Z','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01 00:00:00Z','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01T00:00:00.0001Z','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01T00:00:00.123000001Z','2024-03-01T00:00:00Z'),'utc'),
    ((datetime(2024,2,1,microsecond=1,tzinfo=timezone.utc),'2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01T00:00:00+01:00','2024-01-31T23:00:00Z'),'utc'),
    (('2024-02-01T00:00:00+24:00','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01T00:00:60Z','2024-03-01T00:00:00Z'),'utc'),
    (('2024-02-01','2024-03-01'),'local'),
    (('2024-02-01',),'date'),
    (('2024-02-01','2024-03-01','2024-04-01'),'date'),
    ('2024-02-01','date'),
])
def test_invalid_temporal_domains(domain,mode):
    with pytest.raises((ValueError,TypeError)): TimeAxis(domain,mode=mode)


@pytest.mark.parametrize('reverse',[False,True])
def test_leap_day_geometry_uses_elapsed_days_and_source_strings(reverse):
    table=data(['2024-02-28','2024-02-29','2024-03-01','2024-03-02'])
    figure=line(table,dates(reverse)); payload=figure.payload(); layer=payload['layers'][0]
    assert payload['columns']['when']==list(table.columns['when'])
    assert payload['data_digest']==table.digest
    assert layer['time_axes']=={'x':dict(mode='date',domain=list(dates(reverse).domain),unit='seconds')}
    left,top,width,height=layer['clip']
    for n,point in enumerate(layer['points']):
        fraction=1-n/3 if reverse else n/3
        assert point[1]==pytest.approx(left+width*fraction,abs=1e-6)
    assert segments(figure)==[['a','b'],['b','c'],['c','d']]


def test_explicit_dst_offsets_and_equivalent_instant_coordinates():
    times=['2024-03-31T01:30:00+01:00','2024-03-31T03:30:00+02:00',
           '2024-03-31T01:30:00Z','2024-03-31T02:30:00Z']
    axis=TimeAxis(('2024-03-31T00:30:00Z','2024-03-31T02:30:00Z'),mode='utc')
    figure=line(data(times),axis); layer=figure.payload()['layers'][0]
    left,top,width,height=layer['clip']
    assert [p[1] for p in layer['points']]==pytest.approx([left,left+width/2,left+width/2,left+width],abs=1e-6)
    assert figure.payload()['columns']['when']==times
    assert layer['time_axes']['x']==dict(mode='utc',domain=list(axis.domain),unit='seconds')


def test_two_temporal_scatter_axes_and_reversed_y():
    table=KeyedTable('paired',dict(id=['a','b'],start=['2024-02-28','2024-03-02'],end=['2024-03-02','2024-02-28']))
    figure=BrowserFigure(table,[ScatterView('pairs','start','end',dates(),dates(True))])
    layer=figure.payload()['layers'][0]; left,top,width,height=layer['clip']
    assert set(layer['time_axes'])=={'x','y'}
    assert layer['points'][0][1:]==pytest.approx([left,top+height],abs=1e-6)
    assert layer['points'][1][1:]==pytest.approx([left+width,top],abs=1e-6)


@pytest.mark.parametrize('value,mode', [
    (1709251200,'date'),(True,'date'),('2024-2-29','date'),('2024-02-30','date'),
    ('2024-02-29T00:00:00Z','date'),('2024-02-29','utc'),
    ('2024-02-29T00:00:00','utc'),('2024-02-29T00:00:00.1234Z','utc'),
])
def test_temporal_table_cells_require_declared_string_format(value,mode):
    axis=dates() if mode=='date' else TimeAxis(('2024-02-28T00:00:00Z','2024-03-02T00:00:00Z'),mode='utc')
    with pytest.raises(ValueError): line(data([value]),axis)


def test_numeric_axes_do_not_infer_dates_or_acquire_metadata():
    with pytest.raises(ValueError): line(data(['2024-02-29']),(0,3))
    plain=line(data([0,1]),(0,3)).payload()['layers'][0]
    assert 'time_axes' not in plain and 'max_gap_seconds' not in plain


@pytest.mark.parametrize('gap',[0,-1,float('inf'),float('nan'),True,'86400'])
def test_invalid_max_gap(gap):
    with pytest.raises((ValueError,TypeError)):
        LineView('trend','when','value',dates(),(0,2),max_gap_seconds=gap)


def test_gap_requires_temporal_x_and_keyword_only_argument():
    with pytest.raises(ValueError): LineView('trend','when','value',(0,4),(0,2),max_gap_seconds=1)
    with pytest.raises(ValueError): LineView('trend','when','value',(0,4),dates(),max_gap_seconds=1)
    with pytest.raises(TypeError): LineView('trend','when','value',dates(),(0,2),'','',.45,'#34786b',86400)


def test_gap_threshold_inclusive_reverse_source_order_nulls_and_duplicates():
    table=data(['2024-02-28','2024-02-29','2024-03-02','2024-03-01',None,'2024-02-28','2024-02-28'])
    figure=line(table,max_gap_seconds=86400)
    assert segments(figure)==[['a','b'],['c','d'],['f','g']]
    assert figure.payload()['layers'][0]['missing']==1
    assert segments(line(table))==[['a','b'],['b','c'],['c','d'],['f','g']]
    assert segments(line(table,max_gap_seconds=86399))==[['f','g']]


def test_gap_uses_elapsed_utc_seconds_across_offset_change():
    times=['2024-03-31T01:30:00+01:00','2024-03-31T03:30:00+02:00','2024-03-31T05:30:00+02:00']
    axis=TimeAxis(('2024-03-31T00:00:00Z','2024-03-31T04:00:00Z'),mode='utc')
    assert segments(line(data(times),axis,max_gap_seconds=3600))==[['a','b']]


@pytest.mark.parametrize('orientation',['vertical','horizontal'])
def test_temporal_bar_position_width_is_seconds_and_value_axis_rejected(orientation):
    table=data(['2024-02-29','2024-03-01'],[4,-2]); vertical=orientation=='vertical'
    args=('when','value',dates(),(-3,5)) if vertical else ('value','when',(-3,5),dates())
    figure=BrowserFigure(table,[BarView('bars',*args,bar_width=86400,orientation=orientation)])
    layer=figure.payload()['layers'][0]
    dimension=2 if vertical else 3
    assert [mark['geometry'][dimension] for mark in layer['marks']]==pytest.approx([layer['clip'][dimension]/3]*2,abs=2e-6)
    assert list(layer['time_axes'])==['x' if vertical else 'y']
    invalid=('value','when',(-3,5),dates()) if vertical else ('when','value',dates(),(-3,5))
    with pytest.raises(ValueError): BarView('bad',*invalid,orientation=orientation)


def test_facets_apply_gaps_within_category_and_replacement_preserves_source_identity():
    table=data(['2024-02-28','2024-02-28','2024-02-29','2024-03-02'],group=['north','south','north','south'])
    view=FacetView(LineView('trend','when','value',dates(),(-2,12),max_gap_seconds=86400),'group',('north','south','empty'))
    figure=BrowserFigure(table,[view],width=240,columns=3)
    layers=figure.payload()['layers']
    assert [[mark['ids'] for mark in layer['marks']] for layer in layers]==[[['a','c']],[],[]]
    assert all(layer['time_axes']==layers[0]['time_axes'] for layer in layers)
    revised=data(['2024-02-28','2024-02-28','2024-03-02','2024-02-29'],group=['north','south','north','south'])
    state=figure.state(SelectionState.for_table(table,selected=['a','d'],visible=['a','c']))
    result=figure.replace_data(revised,state=state)
    assert result.report()['changed_ids']==['c','d']
    assert result.state()['selection']==state['selection'] | {'data_digest':revised.digest}
    assert [[m['ids'] for m in layer['marks']] for layer in result.figure.payload()['layers']]==[[],[['b','d']],[]]
    assert figure.payload()['layers']==layers
    invalid=data(['2024-02-28','bad date','2024-02-29','2024-03-02'],group=['north','south','north','south'])
    with pytest.raises(ValueError): figure.replace_data(invalid,state=state)
    assert figure.payload()['layers']==layers


BROWSER_CHECKS=r'''
(async()=>{
 await inkletDocument.ready;
 const ok=(c,m)=>{if(!c)throw Error(m);}, exports=[];
 for(const backend of ['svg','canvas','hybrid']){
  inklet.setBackend(backend);
  for(const visible of [null,['a','c','d'],[]]){
   inklet.setVisible(visible);inklet.select(['b','d']);
   inklet.setViewport([2,3,inklet.scene.width/1.2,inklet.scene.height/1.2]);
   exports.push({state:inklet.state(),svg:inklet.exportSVG()});
  }
 }
 inklet.setVisible(['a','c','d']);inklet.select(['b','d']);
 await inkletDocument.switchRevision(1);
 ok(inklet.selected.has('b')&&inklet.selected.has('d'),'selection lost');
 ok(inklet.scene.layers[0].marks.map(m=>m.ids.join('')).join(',')==='ab,bc','revised gaps incorrect');
 ok(inklet.scene.columns.when[2]==='2024-02-29','raw date lost');
 return {exports,revised:{state:inklet.state(),svg:inklet.exportSVG()}};
})().then(result=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify(result);document.body.append(e);})
.catch(error=>{const e=document.createElement('pre');e.id='test-result';e.textContent=JSON.stringify({error:error.message});document.body.append(e);});
'''


def mark_geometry(svg):
    root=ET.fromstring(svg); result=[]
    for group in (root[1],root[-1]):
        for element in group.iter():
            tag=element.tag.rsplit('}',1)[-1]
            if tag not in ('line','rect') or ('fill' not in element.attrib and 'stroke' not in element.attrib): continue
            attrs={}
            for key,value in element.attrib.items():
                try: attrs[key]=float(value)
                except ValueError: attrs[key]=value
            result.append((tag,attrs))
    return root.attrib['viewBox'].split(),result


def test_temporal_browser_filter_gap_revision_and_svg_export(tmp_path):
    browser=next((p for name in ('google-chrome','chromium','chromium-browser') if (p:=shutil.which(name))),None)
    if browser is None: pytest.skip('Chrome/Chromium not installed')
    original=line(data(['2024-02-28','2024-02-29','2024-03-02','2024-03-02']),max_gap_seconds=86400)
    # A same-day first pair changes source coordinates without reconnecting gaps.
    revised=original.replace_data(data(['2024-02-28','2024-02-28','2024-02-29','2024-03-02'])).figure
    page=tmp_path/'index.html'
    page.write_text(original.to_html(revisions=[RevisionOption('Revised',revised,'Simulated dates')])
                    .replace('</html>','<script>'+BROWSER_CHECKS+'</script></html>'),encoding='utf-8')
    result=subprocess.run([browser,'--headless','--no-sandbox','--disable-gpu','--dump-dom',
        '--virtual-time-budget=5000',f'--user-data-dir={tmp_path}/profile',page.as_uri()],
        capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stderr[-2000:]
    match=re.search(r'<pre id="test-result">(.*?)</pre>',result.stdout,re.S)
    assert match,result.stdout[-3000:]
    report=json.loads(html.unescape(match[1])); assert 'error' not in report,report
    assert len(report['exports'])==9
    for exported in report['exports']:
        assert mark_geometry(original.to_svg(exported['state']))==mark_geometry(exported['svg'])
    assert mark_geometry(revised.to_svg(report['revised']['state']))==mark_geometry(report['revised']['svg'])
    # The filter removes both a-b and b-c; a-c must never appear in its place.
    filtered=original.to_svg(original.state(SelectionState.for_table(original.table,visible=['a','c','d'])))
    assert sum(tag=='line' for tag,attrs in mark_geometry(filtered)[1])==1


@pytest.mark.parametrize('year',[1970,2024,9999])
def test_millisecond_spacing_and_gap_threshold_are_exact(year):
    prefix=f'{year:04d}-01-01T00:00:00.'
    axis=TimeAxis((prefix+'000Z',prefix+'011Z'),mode='utc')
    table=data([prefix+f'{n:03d}Z' for n in range(12)])
    figure=line(table,axis,max_gap_seconds=.001)
    assert segments(figure)==[[a,b] for a,b in zip(table.row_ids,table.row_ids[1:])]
    layer=figure.payload()['layers'][0]; left,top,width,height=layer['clip']
    assert [p[1] for p in layer['points']]==pytest.approx([left+n/11*width for n in range(12)],abs=1e-6)


@pytest.mark.parametrize('endpoints',[
    ('1969-12-31T23:59:59.998Z','1969-12-31T23:59:59.999Z'),
    ('2024-02-29T23:59:59.998Z','2024-02-29T23:59:59.999Z'),
    ('9999-12-31T23:59:59.998Z','9999-12-31T23:59:59.999Z'),
])
def test_millisecond_ticks_stay_on_exact_instants_within_domain(endpoints):
    axis=TimeAxis(endpoints,mode='utc'); scale=axis.scale(); ticks=scale.ticks()
    low,high=[datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=None) for value in endpoints]
    assert ticks
    assert all(tick.microsecond%1000==0 and low<=tick<=high for tick in ticks)
    assert all(-1e-12<=scale.map(tick)<=1+1e-12 for tick in ticks)
    assert len(set(scale.tick_labels(ticks)))==len(ticks)


def test_date_ticks_are_calendar_days_and_year_crossing_labels_disambiguate():
    scale=TimeAxis(('2023-12-30','2024-01-02')).scale(); ticks=scale.ticks()
    assert all(t.hour==t.minute==t.second==t.microsecond==0 for t in ticks)
    labels=scale.tick_labels(ticks)
    assert len(set(labels))==len(labels)
    assert any('2023' in label for label in labels) and any('2024' in label for label in labels)

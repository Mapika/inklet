"""Identity/state contract checks for the first 4.0 prototype."""
import json
import pytest
import inklet as i
from inklet.experimental.selection import KeyedTable, SelectionState


def table(ids=('a', 'b', 'c'), values=(1, 2, 3)):
    return KeyedTable('observations', {'id': ids, 'value': values})


def test_selection_roundtrip_uses_ids_after_reordering_and_value_replacement():
    original = table()
    state = SelectionState.for_table(original, selected=['b'], visible=['a', 'b'])
    restored = SelectionState.from_json(state.to_json())
    assert restored == state
    revised = table(('c', 'b', 'a'), (30, 20, 10))
    with pytest.raises(ValueError, match='rebase'): restored.validate(revised)
    rebound = restored.rebase(revised)
    assert rebound.removed_selected == rebound.removed_visible == ()
    assert rebound.state.visible(revised) == {'id': ('b', 'a'), 'value': (20, 10)}
    assert rebound.state.selected_ids == ('b',)
    assert state.data_digest == original.digest


def test_removed_ids_require_explicit_resolution_and_are_reported():
    original = table()
    state = SelectionState.for_table(original, selected=['c'], visible=['a', 'c'])
    revised = table(('a', 'b'), (1, 2))
    with pytest.raises(ValueError, match='removed'): state.rebase(revised)
    result = state.rebase(revised, missing='drop')
    assert result.removed_selected == result.removed_visible == ('c',)
    assert result.state.selected_ids == () and result.state.visible_ids == ('a',)
    with pytest.raises(ValueError, match='different table'):
        state.rebase(KeyedTable('other', dict(original.columns)))


def test_all_empty_and_hidden_selection_are_distinct():
    t = table()
    all_rows = SelectionState.for_table(t, selected=['c'])
    empty = SelectionState.for_table(t, selected=['c'], visible=[])
    assert len(all_rows.visible(t)['id']) == 3
    assert empty.visible(t) == {'id': (), 'value': ()}
    assert empty.selected_ids == ('c',)
    revised = table(('a', 'b', 'c', 'd'), (1, 2, 3, 4))
    assert len(all_rows.rebase(revised).state.visible(revised)['id']) == 4
    assert empty.rebase(revised).state.visible(revised)['id'] == ()
    assert SelectionState.for_table(table((), ())).visible(table((), ()))['id'] == ()


def test_table_snapshots_input_and_rejects_positional_identity():
    ids = ['a', 'b']; values = [1, 2]
    t = table(ids, values)
    ids[0] = 'renamed'; values[0] = 99
    assert t.row_ids == ('a', 'b') and t.columns['value'] == (1, 2)
    with pytest.raises(TypeError): t.columns['value'] = ()
    with pytest.raises(ValueError, match='unknown'): t.subset(['removed'])
    assert table().digest == table().digest
    assert table(values=(1, 99, 3)).digest != table().digest


@pytest.mark.parametrize('ids,values', [
    (('a', 'a'), (1, 2)), ((1, 2), (1, 2)), (('a', ''), (1, 2)),
    (('a', 'b'), (1,)), (('a',), (float('nan'),)), (('a',), (float('inf'),)),
    (('a',), (2**53,)), (('a',), ([1],)),
])
def test_invalid_table_inputs_fail(ids, values):
    with pytest.raises(ValueError): table(ids, values)


@pytest.mark.parametrize('change', [
    {'schema': 'inklet.selection/9'}, {'unexpected': 1}, {'selected_ids': 'a'},
    {'selected_ids': ['a', 'a']}, {'visible_ids': {}}, {'data_digest': 'bad'},
])
def test_invalid_saved_states_fail(change):
    value = json.loads(SelectionState.for_table(table()).to_json()); value.update(change)
    with pytest.raises(ValueError): SelectionState.from_json(json.dumps(value))


def test_unknown_ids_and_duplicate_json_fields_are_rejected():
    t = table()
    with pytest.raises(ValueError, match='unknown'):
        SelectionState.for_table(t, selected=['absent'])
    raw = SelectionState.for_table(t).to_json().replace('"table":', '"table":"first", "table":')
    with pytest.raises(ValueError, match='duplicate'): SelectionState.from_json(raw)


@pytest.mark.parametrize('strided', [False, True])
def test_dataset_array_rows_do_not_change_without_update(strided):
    np = pytest.importorskip('numpy')
    original = np.arange(16., dtype='float64').reshape(4, 4)
    values = original[::2, ::2] if strided else original[:2, :2]
    data = i.dataset({'row': values})
    p = i.plot_spec().matrix(data.column('row'), ramp=i.ramp(['white', '#246']),
                            scale=i.linear((0, 100)), raster=False)
    doc = i.document(width=100); doc.add('image', p)
    before = doc.compile(); svg = before.to_svg()
    original[:] = 99
    assert data.columns['row'][0][0] == 0
    assert doc.compile() is before
    fresh = i.document(width=100); fresh.add('image', p)
    assert fresh.compile().to_svg() == svg
    data.update(row=values)
    assert doc.compile().to_svg() != svg and before.to_svg() == svg
    original[:] = 25
    assert data.columns['row'][0][0] == 99


def test_dataset_snapshots_arrays_inside_mapping_cells():
    np = pytest.importorskip('numpy')
    values = np.array([1, 2])
    data = i.dataset({'row': [{'nested': values}]})
    values[:] = 9
    assert data.columns['row'][0]['nested'] == (1, 2)
    with pytest.raises(TypeError): data.columns['row'][0]['nested'] = ()


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('kind', ['line', 'scatter', 'bars'])
def test_everyday_data_revisions_match_clean_builds(reverse, kind):
    values = i.dataset({'x': [0, 1, 2], 'y': [2, 4, 3]})
    def make():
        p = i.plot_spec(x=(2.5, -.5) if reverse else (-.5, 2.5), y=(-5, 5))
        if kind == 'bars': p.bars(values.column('x'), values.column('y'))
        else: getattr(p, kind)(values.points('x', 'y'))
        p.axes()
        inner = i.subfigure(); inner.add('plot', p)
        doc = i.document(width=120); doc.add('nested', inner)
        return doc
    doc = make()
    for next_values in ([0, 0, 0], [-3, 2, -1], [4, 4, 4], [2, 4, 3]):
        before = doc.compile(); old_svg = before.to_svg()
        values.update(y=next_values)
        revised = doc.compile()
        assert revised.to_svg() == make().compile().to_svg()
        assert before.to_svg() == old_svg and doc.compile() is revised
        width = doc.width; doc.width += 20; doc.compile(); doc.width = width
        assert doc.compile().to_svg() == revised.to_svg()


def test_compiler_stage_measurements_are_nonnegative_and_preserve_cached_snapshot():
    doc = i.document(width=100); doc.add('text', i.component(i.text, 'Measured'))
    compiled = doc.compile(); stats = compiled.stats
    stages = ('dependency_seconds', 'fitting_seconds', 'paint_seconds',
              'diagnostics_seconds', 'metadata_seconds')
    assert all(stats[name] >= 0 for name in stages)
    assert sum(stats[name] for name in stages) == pytest.approx(stats['build_seconds'], abs=.005)
    assert doc.compile() is compiled


@pytest.mark.parametrize('orient', ['v', 'h'])
@pytest.mark.parametrize('grouped', [False, True])
def test_all_baseline_bars_keep_legend_and_paint_no_rectangles(orient, grouped):
    p = i.panel(70, 50, x=['a', 'b'] if orient=='v' else (0, 10),
                y=(0, 10) if orient=='v' else ['a', 'b'])
    p.bars(['a', 'b'], [[5, 5], [5, 5]] if grouped else [5, 5], baseline=5,
           orient=orient, names=['A', 'B'] if grouped else ['A'])
    p.axes().legend()
    doc=i.document(width=120);doc.add('bars',p)
    figure=doc.compile()
    assert not any(d.severity=='error' for d in figure.diagnostics)
    assert 'A' in figure.to_svg()
    assert not p._content  # No phantom geometry or zero-height painted marks.


def test_reference_fixtures_have_independently_checkable_measurements():
    import csv
    import math
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]/'examples/v4/fixtures'
    manifest=json.loads((root/'manifest.json').read_text())
    assert all((root/name).is_file() for name in manifest['files'])
    with (root/'regions.csv').open() as stream: rows=list(csv.DictReader(stream))
    regions=json.loads((root/'regions.geojson').read_text())
    assert {row['id'] for row in rows} == {feature['id'] for feature in regions['features']}
    assert sum(float(row['revenue']) for row in rows)==200
    assert sum(float(row['cost']) for row in rows)==120
    assembly=json.loads((root/'assembly.json').read_text())
    bounds=[[(c['center'][n]-c['size'][n]/2,c['center'][n]+c['size'][n]/2) for n in range(3)] for c in assembly['components']]
    spans=[max(b[n][1] for b in bounds)-min(b[n][0] for b in bounds) for n in range(3)]
    assert spans==[*assembly['expected']['footprint_mm'],assembly['expected']['height_mm']]
    centers={c['id']:c['center'] for c in assembly['components']}
    assert math.dist(centers['sensor'],centers['support'])==pytest.approx(assembly['expected']['sensor_center_distance_from_support_mm'])
    sample=json.loads((root/'measurement.json').read_text())
    for region in sample['regions']:
        values=[value for ys,ls in zip(sample['intensity'],sample['labels']) for value,label in zip(ys,ls) if label==region['label']]
        expected=sample['expected'][region['id']]
        assert len(values)==expected['pixels']
        assert sum(values)/len(values)==expected['mean_intensity']
        assert len(values)*math.prod(sample['spacing_yx'])==expected['area_um2']


def test_offline_states_rebuild_to_identical_python_svg(tmp_path):
    from pathlib import Path
    import runpy
    recipe=runpy.run_path(str(Path(__file__).resolve().parents[1]/'examples/v4/linked_selection.py'))
    table=recipe['load_table']()
    path=tmp_path/'index.html'
    assert recipe['build_html'](table,path)==20
    payload=path.read_text().split('<script id="states" type="application/json">',1)[1].split('</script>',1)[0]
    states=json.loads(payload)
    for candidate in states:
        state=SelectionState.from_json(json.dumps(candidate['state']))
        assert recipe['make_document'](table,state).compile().to_svg()==candidate['svg']
        assert dict(state.visible(table))=={k:tuple(v) for k,v in candidate['rows'].items()}


def test_html_data_cannot_close_its_script_element(tmp_path):
    from pathlib import Path
    import runpy
    recipe=runpy.run_path(str(Path(__file__).resolve().parents[1]/'examples/v4/linked_selection.py'))
    original=recipe['load_table']()
    columns=dict(original.columns);columns['label']=('</script>',*columns['label'][1:])
    table=KeyedTable(original.name,columns)
    page=tmp_path/'index.html';recipe['build_html'](table,page)
    payload=page.read_text().split('<script id="states" type="application/json">',1)[1].split('</script>',1)[0]
    assert '<' not in payload
    assert json.loads(payload)[0]['rows']['label'][0]=='</script>'


def test_zero_stacked_contributions_do_not_draw_at_a_nonzero_baseline():
    p=i.panel(70,50,x=['a','b'],y=(0,10))
    p.bars(['a','b'],[[0,0],[0,0]],stacked=True,baseline=5,names=['A','B']).axes().legend()
    doc=i.document(width=120);doc.add('bars',p)
    figure=doc.compile()
    assert not p._content and not any(d.severity=='error' for d in figure.diagnostics)

"""Regressions discovered while independently auditing the 3.1 release."""
import pytest
import inklet as i
from inklet.core import resolve
from inklet.draw.coords import as_drawn


@pytest.mark.parametrize('nesting', [0, 1, 3])
@pytest.mark.parametrize('edit', ['marks', 'inset', 'twin'])
def test_legacy_panel_edits_reach_cached_parent_figures(nesting, edit):
    panel = i.panel(40, 30, x=(0, 2), y=(0, 2)).line([(0, 0), (1, 1)])
    if edit == 'inset':
        target = i.panel(15, 12, x=(0, 2), y=(0, 2)).line([(0, 0), (1, 1)])
        panel.inset(target, side='right', width=None)
    elif edit == 'twin':
        target = panel.twin_y((0, 2))
    else:
        target = panel
    child = panel
    for _ in range(nesting):
        group = i.subfigure(); group.add('plot', child)
        child = group
    doc = i.document(width=120); doc.add('content', child)
    before = doc.compile(); original = before.to_svg()
    assert doc.compile() is before
    target.line([(0, 2), (2, 0)], stroke='#ab2345')
    after = doc.compile()
    assert after is not before
    assert '#ab2345' in after.to_svg() and '#ab2345' not in original
    assert before.to_svg() == original
    assert doc.compile() is after


@pytest.mark.parametrize('dtype', ['int32', 'int64', 'uint64', 'float32', 'float64'])
@pytest.mark.parametrize('grouped', [False, True])
def test_numpy_bar_arrays_have_the_same_geometry_as_python_lists(dtype, grouped):
    np = pytest.importorskip('numpy')
    data = [[2, 4, 6], [1, 3, 5]] if grouped else [2, 4, 6]
    def geometry(values):
        p = i.panel(60, 40, x=['a', 'b', 'c'], y=(0, 8))
        p.bars(['a', 'b', 'c'], values, names=['A', 'B'] if grouped else ['A'])
        p.legend()
        return [(n.diagram.kind, n.bbox) for n in resolve(as_drawn(p.build())).values()
                if n.diagram.prim is not None]
    assert geometry(np.array(data, dtype=dtype)) == geometry(data)


@pytest.mark.parametrize('side', ['n', 's', 'e', 'w'])
@pytest.mark.parametrize('reverse', [False, True])
def test_automatic_brackets_clear_marks_for_either_endpoint_order(side, reverse):
    horizontal = side in ('e', 'w')
    values = [6, 8, 5] if side in ('n', 'e') else [-6, -8, -5]
    cats = ['c', 'b', 'a'] if reverse else ['a', 'b', 'c']
    opts = dict(x=(-10, 10), y=cats) if horizontal else dict(x=cats, y=(-10, 10))
    p = i.panel(60, 40, **opts).bars(['a', 'b', 'c'], values,
                                    orient='h' if horizontal else 'v')
    from inklet.plot.inset import panel_bracket, _drawn_boxes
    first = as_drawn(panel_bracket(p, 'a', 'c', side=side, clear=2)).bbox
    second = as_drawn(panel_bracket(p, 'c', 'a', side=side, clear=2)).bbox
    assert first == second
    marks = _drawn_boxes(p)
    if side == 'e': assert first.x0 > max(b.x1 for b in marks)
    if side == 'w': assert first.x1 < min(b.x0 for b in marks)
    if side == 'n': assert first.y1 < min(b.y0 for b in marks)
    if side == 's': assert first.y0 > max(b.y1 for b in marks)


def test_nested_polar_panel_mutation_invalidates_parent_snapshot():
    p = i.polar(20, r=(0, 1)).line([(0, .2), (90, .4)])
    inner = i.subfigure(); inner.add('polar', p)
    doc = i.document(width=100); doc.add('inner', inner)
    before = doc.compile(); svg = before.to_svg()
    p.line([(0, .8), (180, .8)], stroke='#ab2345')
    after = doc.compile()
    assert after is not before and after.to_svg() != svg
    assert '#ab2345' in after.to_svg()
    assert before.to_svg() == svg
    assert doc.compile() is after


@pytest.mark.parametrize('strided', [False, True])
def test_large_array_replacement_is_visible_without_resizing(strided):
    np = pytest.importorskip('numpy')
    storage = np.column_stack((np.linspace(0, 1, 4002), np.zeros(4002)))
    points = storage[::2] if strided else storage[:2001].copy()
    plot = i.plot_spec(x=(0, 1), y=(0, 1)).line(points, key='curve')
    doc = i.document(width=100); doc.add('curve', plot)
    before = doc.compile(); svg = before.to_svg()
    changed = points.copy(); changed[1000, 1] = 1
    assert repr(points) == repr(changed)  # The old cache key missed this edit.
    plot.replace('curve', changed)
    after = doc.compile()
    fresh = i.document(width=100); fresh.add('curve', plot)
    assert after is not before and after.to_svg() != svg
    assert after.to_svg() == fresh.compile().to_svg()
    assert before.to_svg() == svg and doc.compile() is after


def test_array_inputs_are_snapshotted_before_first_compilation():
    np = pytest.importorskip('numpy')
    points = np.array([[0., 0.], [1., 0.]])
    plot = i.plot_spec(x=(0, 1), y=(0, 1)).line(points)
    points[1, 1] = 1
    reference = i.plot_spec(x=(0, 1), y=(0, 1)).line([[0., 0.], [1., 0.]])
    a = i.document(width=100); a.add('curve', plot)
    b = i.document(width=100); b.add('curve', reference)
    assert a.compile().to_svg() == b.compile().to_svg()


def test_component_array_configuration_preserves_type_and_invalidates_cache():
    np = pytest.importorskip('numpy')
    values = np.zeros(2001, dtype=np.float32)
    def summary(array):
        assert isinstance(array, np.ndarray) and array.dtype == np.float32
        assert array.shape == (2001,)
        return i.text(f'Total: {array.sum():.1f}')
    component = i.component(summary, array=values)
    doc = i.document(width=100); doc.add('total', component)
    before = doc.compile(); svg = before.to_svg()
    values[1000] = 7
    component.configure(array=values)
    after = doc.compile()
    assert after is not before and after.to_svg() != svg
    assert 'Total: 7.0' in after.to_svg()
    assert before.to_svg() == svg and doc.compile() is after


def test_object_array_snapshot_copies_nested_mutable_values():
    np = pytest.importorskip('numpy')
    from inklet.document.spec import freeze, fingerprint
    values = np.empty(1, dtype=object); values[0] = {'value': [2]}
    snapshot = freeze(values); original = fingerprint(snapshot)
    values[0]['value'][0] = 5
    assert snapshot[0]['value'] == [2]
    assert fingerprint(snapshot) == original
    assert fingerprint(values) != original

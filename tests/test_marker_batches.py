"""Packed markers agree with separately authored geometry in both backends."""
from dataclasses import replace
from io import BytesIO
import math
import shutil
import subprocess

import pytest
import inklet as i
from inklet.core import Affine, Diagram, EllipsePrim, MarkerBatchPrim, Rect, Style, Vec2
from inklet.core.batch import RECORD
from inklet.draw.coords import as_drawn
from inklet.figure import apply_theme
from inklet.plot.scatter_batch import scatter_batch
from inklet.render.bounds import painted_bounds

MARKERS = ('circle', 'square', 'diamond', 'triangle', 'star', 'cross', 'plus')


def pair(marker, clipping, *, fill_opacity=.4, opacity=.65):
    p = i.panel(30, 20, x=(0, 10), y=(0, 10))
    data = [(-1, 4), (0, 5), (1, 5), (5, 5), (5.2, 5.1),
            (6, 5.4), (9, 9), (10, 2), (11, 6)]
    sizes = [1.5 + k*.24 for k in range(len(data))]
    fills = ['#c75f39', '#245b8a', None]*3
    style = dict(fill='#69a68d', stroke='#332244', stroke_width=.35,
                 stroke_dash=(.7, .3), stroke_linejoin='round',
                 stroke_linecap='square', corner_radius=.3,
                 opacity=opacity, fill_opacity=fill_opacity, stroke_opacity=.8)
    batch = scatter_batch(p, data, sizes, fills, marker, dict(style))
    ordinary = i.place([(p.point(*point), i.marker(marker, size).styled(fill=fill))
                        for point, size, fill in zip(data, sizes, fills)], **style)
    def finish(node):
        node = as_drawn(node)
        if clipping == 'geometric': node = i.clip(node, p.area)
        if clipping == 'strict': node = i.clip(node, p.area, strict=True)
        if clipping == 'window': node = i.window(node, p.area)
        # Non-uniform transform exercises bounds, marker stroke and dash sizes.
        node = node.scaled(1.2, .8).rotated(17)
        return apply_theme(node, i.theme())
    return finish(batch), finish(ordinary)


def pixels(node, backend, tmp_path):
    Image = pytest.importorskip('PIL.Image')
    scene = i.compile_scene(node)
    if backend == 'svg':
        return Image.open(BytesIO(scene.to_png(dpi=254, margin=3, background='white'))).convert('RGB')
    if not shutil.which('pdftoppm'): pytest.skip('Poppler not installed')
    (tmp_path/'figure.pdf').write_bytes(scene.to_pdf(margin=3, background='white', precision=6))
    subprocess.run(['pdftoppm', '-r', '254', '-png', '-singlefile',
                    str(tmp_path/'figure.pdf'), str(tmp_path/'figure')], check=True, capture_output=True)
    return Image.open(tmp_path/'figure.png').convert('RGB')


@pytest.mark.parametrize('marker', MARKERS)
@pytest.mark.parametrize('clipping', ['none', 'geometric', 'strict', 'window'])
@pytest.mark.parametrize('backend', ['svg', 'pdf'])
def test_batch_matches_individual_paints(tmp_path, marker, clipping, backend):
    a, b = pair(marker, clipping)
    assert tuple(vars_rect(a.bbox)) == pytest.approx(tuple(vars_rect(b.bbox)), abs=1e-9)
    actual, expected = pixels(a, backend, tmp_path), pixels(b, backend, tmp_path)
    assert actual.size == expected.size
    errors = [abs(x-y) for x, y in zip(actual.tobytes(), expected.tobytes())]
    assert sum(errors)/len(errors) < .12


def vars_rect(box):
    return box.x0, box.y0, box.x1, box.y1


def test_dense_scatter_uses_one_buffer_and_reuses_geometry():
    p = i.panel(50, 30, x=(0, 1), y=(0, 1), clip=False)
    p.scatter(((k/10000, .5) for k in range(10000)), size=.3, color='blue')
    root = p.build()
    batches = [n for n in root.walk() if isinstance(n.prim, MarkerBatchPrim)]
    assert len(batches) == 1
    batch = batches[0].prim
    assert len(batch) == 10000 and len(batch.data) == 360000
    assert len(list(root.walk())) < 20
    before = i.compile_scene(root)
    after = i.compile_scene(root.styled(fill_opacity=.2), previous=before)
    assert after.stats['new_geometry'] == 0
    assert before.to_svg() != after.to_svg()
    assert b'/Subtype /Image' not in before.to_pdf(compress=False)
    assert 'data-source-index="9999"' in before.to_svg()


def test_clipping_preserves_source_indices_without_reordering():
    data = b''.join(RECORD.pack(x, 0, 1, 0, source)
                    for source, x in enumerate([-20, -2, 20, 0, 2]))
    root = Diagram(prim=MarkerBatchPrim(EllipsePrim(.5,.5), data))
    clipped = i.clip(root, Rect(-3,-1,3,1))
    records = [record for n in clipped.walk() if isinstance(n.prim, MarkerBatchPrim)
               for record in n.prim.records()]
    assert [r[-1] for r in records] == [1,3,4]
    assert [r[-1] for r in root.prim.records()] == list(range(5))


def test_support_and_trace_match_expanded_markers():
    a, b = pair('circle', 'none', opacity=1)
    for angle in range(0,360,23):
        direction = Vec2(math.cos(math.radians(angle)), math.sin(math.radians(angle)))
        assert a.envelope.extent(direction) == pytest.approx(b.envelope.extent(direction))
        assert a.trace.hits(Vec2(0,0),direction) == pytest.approx(b.trace.hits(Vec2(0,0),direction))


@pytest.mark.parametrize('record', [RECORD.pack(math.nan,0,1,0,0), RECORD.pack(0,0,-1,0,0),
                                   RECORD.pack(0,0,1,1,0), b'bad'])
def test_invalid_buffers_are_rejected(record):
    with pytest.raises(ValueError): MarkerBatchPrim(EllipsePrim(.5,.5), record)


def test_buffer_copies_mutable_input():
    data = bytearray(RECORD.pack(1,2,3,0,8))
    batch = MarkerBatchPrim(EllipsePrim(.5,.5), data)
    data[:] = b'\0'*len(data)
    assert list(batch.records()) == [(1,2,3,0,8)]


def test_palette_diagnostics_count_records_not_batch_nodes():
    from types import SimpleNamespace
    from inklet.diagnostics.key_rules import _paints
    data = b''.join(RECORD.pack(k,0,1,k%2,k) for k in range(6))
    batch = MarkerBatchPrim(EllipsePrim(.5,.5), data, ('red', None))
    item = SimpleNamespace(is_text=False, prim=batch, node=SimpleNamespace(kind='mark'),
                           style=Style(fill='blue', stroke='none'))
    assert _paints([item], fills_only=True) == {'#ff0000': 3, '#0000ff': 3}


def test_scene_reports_placed_instances_and_unique_buffer_bytes():
    batch = MarkerBatchPrim(EllipsePrim(.5,.5), RECORD.pack(0,0,1,0,5))
    recoloured = replace(batch, palette=('red',))
    root = Diagram(children=(Diagram(prim=batch), Diagram(prim=batch).translated(3,0),
                             Diagram(prim=recoloured).translated(6,0)))
    scene = i.compile_scene(root)
    assert scene.stats['marker_instances'] == 3
    assert scene.stats['marker_buffer_bytes'] == RECORD.size


@pytest.mark.parametrize('label_x, expected', [(0, False), (12, True)])
def test_overlap_diagnostics_distinguish_empty_space_and_actual_markers(label_x, expected):
    batch = MarkerBatchPrim(EllipsePrim(.5,.5),
                           RECORD.pack(-10,0,4,0,0)+RECORD.pack(10,0,4,0,1))
    root = Diagram(children=(Diagram(prim=batch, kind='mark'),
                             i.text('Label', size=3).translated(label_x, 1.5)))
    fig = i.figure(); fig.add(root)
    overlap = [d for d in fig.lint() if d.code=='OVERLAP']
    assert bool(overlap) is expected


def test_crowding_does_not_treat_cloud_extent_as_a_solid_rectangle():
    batch = MarkerBatchPrim(EllipsePrim(.5,.5),
                           RECORD.pack(-10,0,4,0,0)+RECORD.pack(10,0,4,0,1))
    root = Diagram(children=(Diagram(prim=batch, kind='mark'),
                             i.text('Label', size=3).translated(0, 3.5)))
    fig = i.figure(); fig.add(root)
    assert not [d for d in fig.lint() if d.code in ('OVERLAP','CROWDING')]


def test_clipping_batch_primitive_keeps_ordinary_child_content():
    batch = MarkerBatchPrim(EllipsePrim(.5,.5), RECORD.pack(20,0,1,0,0))
    child = Diagram(prim=EllipsePrim(1,1))
    clipped = i.clip(Diagram(prim=batch, children=(child,)), Rect(-2,-2,2,2))
    assert any(n.id==child.id for n in clipped.walk())
    assert not any(isinstance(n.prim, MarkerBatchPrim) for n in clipped.walk())


def test_empty_template_has_no_extent_or_ink():
    from inklet.core import PathPrim
    batch = MarkerBatchPrim(PathPrim(()), RECORD.pack(1,2,1,0,0))
    assert batch.envelope().is_empty and batch.trace().is_empty
    assert i.compile_scene(Diagram(prim=batch)).to_pdf().startswith(b'%PDF')

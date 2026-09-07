"""Diagram label clearance, bounded modules and dense obstacle routing."""
import random

import pytest
import inklet as i
from inklet.core import Rect, TextPrim, Vec2, group, resolve
from inklet.document.compiler import BuildContext
from inklet.links import link, route_all
from inklet.links.link import _area, _covers, _drop_contained, _label_rect, _run_inside, _shaft_segments


def render(spec):
    return BuildContext(i.theme('nature'), {}).build(spec)


def test_module_wraps_at_maximum_width_without_scaling_and_keeps_ports():
    spec = i.module('Process incoming requests and validate their contents',
                    max_width=34, text_style={'size':3})
    node = render(spec)
    assert node.width <= 34+1e-7
    assert node.height > 12
    assert {n.prim.font_size for n in node.walk() if isinstance(n.prim,TextPrim)} == {3}
    assert node.anchor_point('out') == Vec2(node.width,node.height/2)
    spec.configure('Ready')
    assert render(spec).height == 12


@pytest.mark.parametrize('offset', [(8,5),(-8,-5),(8,-5),(-8,5)])
def test_module_offsets_keep_label_inside_padded_frame(offset):
    node = render(i.module('Offset label',label_offset=offset))
    body = node.children[1].bbox
    assert body.x0 >= 3-1e-7 and body.y0 >= 3-1e-7
    assert body.x1 <= node.width-3+1e-7 and body.y1 <= node.height-3+1e-7


@pytest.mark.parametrize('label', ['UnbreakableLabelThatExceedsTheWidth', i.box(width=60,height=10)])
def test_module_rejects_overflow_instead_of_clipping_or_scaling(label):
    with pytest.raises(i.LayoutError,match='maximum width'):
        render(i.module(label,max_width=25))


def test_module_wrap_respects_height_and_explicit_text_width():
    label = 'Process incoming requests and validate their contents'
    with pytest.raises(i.LayoutError,match='maximum height'):
        render(i.module(label,max_width=25,max_height=12))
    node = render(i.module(label,max_width=45,text_style={'width':15}))
    assert node.width <= 21+1e-7
    with pytest.raises(i.LayoutError,match='no room'):
        render(i.module('X',max_width=20,pad=10))


@pytest.mark.parametrize('width',[float('nan'),float('inf'),-1,19])
def test_module_rejects_invalid_maximum_width(width):
    with pytest.raises(ValueError):i.module('X',max_width=width)


def test_parallel_connector_labels_reserve_distinct_space():
    a,b = i.box('A'),i.box('B').translated(80,0)
    placements = resolve(group([a,b]))
    links = [link(a,b,label=i.text(label),kind='line',route='straight')
             for label in ['request','response','status']]
    routed = route_all(links,placements)
    plates = [_label_rect(node) for node in routed.children]
    assert all(plate is not None for plate in plates)
    for j,plate in enumerate(plates):
        assert all(plate.overlap(other) is None for other in plates[j+1:])
    assert plates == [_label_rect(node) for node in route_all(links,placements).children]


@pytest.mark.parametrize('vertical',[False,True])
def test_containment_sweep_matches_exact_pairwise_rule(vertical):
    rng = random.Random(29)
    boxes = []
    for k in range(160):
        x,y = rng.uniform(-80,80),rng.uniform(-15,15)
        w,h = rng.uniform(1,15),rng.uniform(1,8)
        if vertical:x,y,w,h=y,x,h,w
        outer = Rect(x,y,x+w,y+h)
        boxes.extend([outer,outer.pad(-min(w,h)/4)])
    boxes.extend(boxes[:8])
    # Include near-coincident leading edges within the containment tolerance.
    boxes.extend([Rect(0,0,10,10),Rect(1e-9,1e-9,10+1e-9,10+1e-9)])
    rng.shuffle(boxes)
    expected = [b for k,b in enumerate(boxes)
                if not any(j != k and _covers(other,b) and (_area(other)>_area(b) or j<k)
                           for j,other in enumerate(boxes))]
    assert _drop_contained(boxes) == expected


def test_dense_nested_obstacles_still_prune_above_old_limit():
    boxes = [Rect(x*20,y*20,x*20+12,y*20+12) for x in range(15) for y in range(15)]
    nested = [b.pad(-2) for b in boxes]
    assert _drop_contained(boxes+nested) == boxes


def test_crowded_channels_clear_later_shafts_and_other_label_plates():
    from examples.diagram_review import channels
    root,_ = channels().build()
    routed = next(n for n in root.walk() if n.kind=='links')
    for index,node in enumerate(routed.children):
        plate = _label_rect(node)
        for other in routed.children[index+1:]:
            assert plate.overlap(_label_rect(other)) is None
        for other in routed.children:
            assert all(_run_inside(plate,a,b) <= 1e-7 for a,b in _shaft_segments(other))


def test_dense_graph_routes_without_avoidance_fallback():
    from tools.benchmark_diagrams import measure
    result = measure()
    assert result['route_flags'] == []


def test_diagram_review_has_no_diagnostics():
    from examples.diagram_review import make_document
    assert make_document().compile().diagnostics == ()

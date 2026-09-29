import pytest
import inklet as i


def plot(height=24):
    return (i.plot_spec(40, height, x=(0, 3), y=(0, 4))
            .line([(0, 1), (1, 3), (2, 2), (3, 4)]).axes(x='Time', y='Value'))


def page(pack, **options):
    doc = i.document(width=160, columns=3, margin=2, gap=4, pack=pack, **options)
    doc.letters(start='a', anchor='cell')
    doc.add('art', i.box('tall drawing', width=40, height=80), row=0, column=0, rowspan=2)
    doc.add('one', plot(), row=0, column=1)
    doc.add('two', plot(), row=0, column=2)
    doc.add('three', plot(), row=1, column=1, colspan=2)
    return doc.compile()


def overlaps(a, b):
    return a.x0 < b.x1-1e-6 and b.x0 < a.x1-1e-6 and a.y0 < b.y1-1e-6 and b.y0 < a.y1-1e-6


def test_packing_sets_plots_beside_a_tall_drawing_in_reading_order():
    grid, packed = page(False), page(True)
    assert packed.metadata['height_mm'] <= grid.metadata['height_mm']+.1
    layout = packed.metadata['layout']
    # Beside the drawing, one plot spans over the other two.
    assert layout['packing'] == '(art | (one / (two | three)))'
    boxes = packed.cells
    names = list(boxes)
    assert all(not overlaps(boxes[a], boxes[b]) for n, a in enumerate(names) for b in names[n+1:])
    assert all(2-1e-6 <= box.x0 and box.x1 <= 158+1e-6 for box in boxes.values())
    assert packed.layout_report().splitlines()[0] == 'packed  (art | (one / (two | three)))'
    assert boxes['one'].x0 == boxes['two'].x0 and boxes['one'].y1 < boxes['two'].y0


def test_a_packed_page_is_shorter_than_one_stack():
    doc = i.document(width=160, margin=0, gap=4, pack=True)
    for name in ('p', 'q', 'r', 's'):
        doc.add(name, plot())
    packed = doc.compile()
    stacked = i.document(width=160, margin=0, gap=4)
    for name in ('p', 'q', 'r', 's'):
        stacked.add(name, plot())
    assert packed.metadata['height_mm'] < stacked.compile().metadata['height_mm']/2+1


def test_packing_chooses_among_alternatives_and_checks_its_option():
    wide = i.component(i.box, 'wide', width=150, height=10)
    doc = i.document(width=100, margin=0, gap=4, pack=True)
    doc.add('first', i.choose(too_wide=wide, plot=plot()))
    doc.add('second', plot())
    assert doc.compile().metadata['layout']['choices'] == {'first': 'plot'}
    with pytest.raises(ValueError):
        i.document(pack='yes')


def test_packing_that_cannot_fit_the_width_says_so():
    doc = i.document(width=60, margin=0, pack=True)
    doc.add('wide', i.box('wide', width=90, height=10))
    with pytest.raises(i.LayoutError, match='wider than the page'):
        doc.compile()


def test_a_fixed_height_gives_packed_plots_the_extra_room_or_refuses():
    natural = page(True).metadata['height_mm']
    taller = page(True, height=natural+20)
    assert taller.metadata['height_mm'] == pytest.approx(natural+20)
    assert max(box.y1 for box in taller.cells.values()) == pytest.approx(natural+18)
    with pytest.raises(i.LayoutError, match='need'):
        page(True, height=natural-10)


def test_packing_needs_no_optional_dependencies():
    # numpy is optional; a core install must still pack.
    import subprocess, sys, textwrap
    script = textwrap.dedent('''
        import sys
        sys.modules['numpy'] = None
        import inklet as i
        doc = i.document(width=100, margin=0, gap=4, pack=True)
        doc.add('a', i.box('a', width=30, height=20))
        doc.add('b', i.box('b', width=30, height=20))
        print(doc.compile().metadata['layout']['packing'])
    ''')
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '(a | b)'


def test_a_coarse_gap_rounded_down_never_overruns_the_page():
    # Four cells of 20 steps with 7-step gaps need 101 of 100 steps; the
    # coarse grid rounds each gap down to 5 steps and would set all four side
    # by side.
    from inklet.document.packing import _INF, _leaves, _solve
    heights = [_INF]*20 + [10.]*81
    profiles = [(heights, [0.]*101, [0]*101, None) for _ in range(4)]
    tree = _solve(profiles, 100, 7, 2., .5, 50.)

    def width(node):
        if node[0] == 'cell':
            return node[3]
        a, b = width(node[1]), width(node[2])
        return a+7+b if node[0] == 'beside' else max(a, b)
    assert width(tree) <= 100
    assert all(leaf[3] >= 20 for leaf in _leaves(tree))


def test_packed_responsive_content_is_offered_its_box_height():
    offered = []

    def art(*, width, height, grow):
        offered.append(height)
        # Taller than offered when `grow`: the build must be refused.
        tall = height is not None and height > 20
        return i.box('art', width=width, height=(height+5 if grow else height) if tall else 10)

    def page(grow):
        doc = i.document(width=100, margin=0, gap=4, pack=True)
        doc.add('tall', i.box('tall', width=48, height=60))
        doc.add('art', i.component(art, grow=grow, responsive=True), min_width=48)
        return doc.compile()
    unused = lambda figure: figure.metadata['layout']['cells']['art']['unused_height']
    assert unused(page(False)) < 1 and offered[-1] is not None
    assert unused(page(True)) == pytest.approx(50)

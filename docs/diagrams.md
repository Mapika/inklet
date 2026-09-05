# Diagrams and measured connections

Use `composition()` when positions should depend on measured component sizes.
Use `document()` or `subfigure()` for grids. The direct combinators remain
useful for simple rows, stacks and fixed diagrams.

## A measured architecture

```python
import inklet as i

art = i.composition(150, 45)
art.add('input', i.module('Observations'), x=5, y=12)
x, _ = art.point('input', 'out')
art.add('model', i.module('Encoder'), x=x + 10, y=12)
x, _ = art.point('model', 'out')
art.add('output', i.module('Prediction'), x=x + 10, y=12)
art.link('input:out', 'model:in')
art.link('model:out', 'output:in')
art.constrain(art.page_width - art.point('output', 'e')[0], minimum=5,
              message='Increase the page width for the output module')

doc = i.document(width=160, height=55)
doc.add('architecture', art)
first = doc.compile()
art['model'].configure(label='Shared encoder')
second = doc.compile()
assert first.to_svg() != second.to_svg()
second.save('architecture.svg', 'architecture.pdf')
```

Modules grow from shaped text, padding and minimum sizes. Since downstream x
positions refer to ports, changing the encoder label moves its output and the
following module. Links resolve after placement. Unsatisfied constraints and
cyclic measurements raise a named layout error.

## Ports and placement

`module()` has default `in` and `out` ports. Supply a mapping such as
`ports={'input': (0, .5), 'upper': (1, .25), 'lower': (1, .75)}` for custom
fractional box positions. Compass anchors such as `n`, `e` and `center` are
also available. See [diagram components](diagram-components.md) for the ports
provided by databases, sequences and feature matrices.

Composition coordinates default to millimetres. With `anchor=None`, a child's
local coordinate frame is retained. For explicit alignment, use
`anchor='nw'`, `'center'`, a registered port, or `'area-nw'` for a plot area.
Use `point(name, anchor)`, `measure(name, 'width')`, `page_width` and
`page_height` in arithmetic expressions. Forward references are allowed if
they do not form a cycle.

`route='orthogonal'` creates right-angle routes. Explicit `waypoints` can use
measured expressions too. The composition frame is not a clipping mask;
outlying artwork remains visible to diagnostics.

## A direct flow diagram

```python
acquire = i.box('Acquire', width=25)
analyse = i.box('Analyse', width=25)
fig = i.figure(width=100)
fig.add(i.hstack([acquire, analyse], gap=12))
fig.link(acquire, analyse, label='observations')
fig.save('flow.svg')
assert not any(d.severity == 'error' for d in fig.lint())
```

Keep handles to the original children when linking through direct combinators.
The combinators wrap them, so anchors resolve after layout. If a direct drawing
is placed twice, copy it first. Document cells handle independent copies for you.

## Graph layout

```python
graph = i.graph(
    {name: i.box(name, width=22) for name in ('Input', 'Model', 'Result')},
    [('Input', 'Model'), ('Model', 'Result')],
    layout='layered', direction='right',
)
graph_figure = i.figure(width=120)
graph.add_to(graph_figure)
graph_figure.save('graph.svg')
assert not any(d.severity == 'error' for d in graph_figure.lint())
```

`graph()` returns both a laid-out diagram and links. `add_to()` adds both to a
Figure; `.diagram` alone does not include the routed connections. Available
layouts are `layered`, `tree`, `force` and `circular`. Edge crossings can remain
in dense graphs and are reported for review.

For branches, loops, explicit routing and diagram annotations, use the
[tested cookbook](cookbook.md). For a graph inside a responsive document
component, see `network()` in the [stress example](../examples/stress20.py).

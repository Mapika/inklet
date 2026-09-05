"""The same simulated plots, diagram, table and native 3D content in any preset.

Build with `inklet build examples/presets.py --output out/preset-example`.
Use `python tools/preset_gallery.py` to compare all the built-in styles.
"""
import inklet as i


def architecture():
    theme = i.current_theme()
    return i.vstack([
        i.title('Workflow'),
        i.hstack([i.box('Data'), i.text('→'), i.box('Model')], gap=theme.gap('s')),
        i.text('Shared inputs', size=theme.font_size_small),
    ], gap=theme.gap('m'))


def model_and_table():
    theme = i.current_theme()
    model = i.solid('cube', width=theme.font_size*9, style='shaded',
                    color=theme.accent, view='isometric')
    table = i.grid([
        i.text('Metric', weight='bold'), i.text('Value', weight='bold'),
        i.text('Trials'), i.text('24'),
        i.text('Response'), i.text('6.2'),
    ], cols=2, gap=theme.gap('m'))
    return i.vstack([model, table], gap=theme.gap('m'))


def caption(content, *, width, height):
    return i.text(content, width=width, size=i.current_theme().font_size_small)


def make_document(style='scientific.general'):
    selected = i.preset(style)
    # Auto-height lets this comparison retain all its content in every style.
    doc = selected.document(columns=2, height=None)
    data = i.dataset({'time': [0, 1, 2, 3, 4, 5],
                      'response': [1, 1.8, 2.9, 4.1, 5.5, 6.2],
                      'control': [1, 1.4, 1.8, 2.2, 2.4, 2.7]},
                     name='preset demonstration',
                     source=i.Source('Inklet preset gallery', method='simulated'))
    response = i.plot_spec(height=selected.theme.font_size*14, x=(0, 5), y=(0, 8))
    response.line(data.points('time', 'response'), name='Response')
    response.line(data.points('time', 'control'), name='Control', stroke_dash=(1.2, .7))
    response.axes(x='Time / s', y='Signal / a.u.').legend()
    bars = i.plot_spec(height=selected.theme.font_size*14,
                       x=i.band(['A', 'B', 'C']), y=(0, 8))
    bars.bars(['A', 'B', 'C'], [3.1, 4.8, 6.2])
    bars.axes(x='Condition', y='Outcome / a.u.')
    panels = i.subfigure(columns=2, margin=0, gap=selected.gap).letters()
    panels.add('response', response, row=0, column=0)
    panels.add('outcomes', bars, row=0, column=1)
    panels.add('workflow', i.component(architecture), row=1, column=0)
    panels.add('model', i.component(model_and_table), row=1, column=1)
    doc.add('heading', i.component(i.title, 'One figure, different audiences'), colspan=2)
    doc.add('panels', panels, colspan=2)
    doc.add('caption', i.component(caption,
            'Simulated data. Colours, type and layout inherit the selected preset.',
            responsive=True), colspan=2)
    return doc


if __name__ == '__main__':
    make_document().save('preset.svg', 'preset.pdf')
